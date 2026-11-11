"""Search a durable queue of qualified layouts with the optimized GPU cascade."""

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from ultra_low_hut import ROOT
from ultra_low_hut.layouts.catalog import require_natural_template, require_layout_version
from ultra_low_hut.verification.client import verification_options
from ultra_low_hut.verification.loading_orders import LOADING_FIELDS, normalize_verification_mode
from ultra_low_hut.world_types import WORLD_TYPES, config_world, world_config

TEMPLATE_FIELDS = (
    "original",
    "target",
    "relx",
    "relz",
    "width",
    "g53",
    "g54",
    "covered",
    "pieces",
)


def atomic(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def append(path, value):
    with path.open("ab") as stream:
        offset = stream.tell()
        stream.write((json.dumps(value) + "\n").encode())
        stream.flush()
        os.fsync(stream.fileno())
    return offset


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def base_identity(row):
    return tuple(int(row[name]) for name in ("target", "relx", "relz", "width"))


def domain_identity(row):
    return (*base_identity(row), int(row["coordinate_regions_mask"]))


def normalize_template(row):
    result = dict(row)
    for name in TEMPLATE_FIELDS:
        value = result[name]
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, str))
            or str(int(value)) != str(value)
        ):
            raise ValueError(f"Layout field {name} must be a canonical integer")
        result[name] = int(value)
    for name in ("target", "original"):
        if not 0 <= result[name] < 1 << 48:
            raise ValueError(f"Layout {name} must fit low48")
        result[name] = str(result[name])
    if result["width"] not in (7, 9) or result["relx"] % 16 or result["relz"] % 16:
        raise ValueError("Layouts use width7/9 and chunk-aligned offsets")
    if (
        result["g53"] < 0
        or result["g54"] < 0
        or not 0 <= result["covered"] <= 63
        or result["pieces"] < 1
    ):
        raise ValueError("Layout gains, coverage or piece count are invalid")
    mask = int(result.get("coordinate_regions_mask", 511))
    if not 1 <= mask <= 511:
        raise ValueError(
            "Coordinate region mask must select at least one of nine regions"
        )
    result["coordinate_regions_mask"] = mask
    require_natural_template(result)
    return result


def rank(row):
    return (
        int(row.get("ordered_floor_gain", 0)),
        int(row.get("coordinate_gain54", row["g54"])),
        int(row.get("deep_corridor_gain", 0)),
        int(row.get("auxiliary_corridor_gain", 0)),
    )


def load_pool(path):
    payload = path.read_bytes()
    document = json.loads(payload)
    source_version = document.get("version") if isinstance(document, dict) else None
    rows = document.get("templates") if isinstance(document, dict) else document
    if not isinstance(rows, list):
        raise ValueError(
            "Pool must be a templates array or an object containing templates"
        )
    selected = {}
    for row in rows:
        if source_version:
            row = dict(row, version=row.get("version", source_version))
        normalized = normalize_template(row)
        key = base_identity(normalized)
        if key in selected and domain_identity(selected[key]) != domain_identity(
            normalized
        ):
            raise ValueError(f"Conflicting coordinate masks for layout {key}")
        if key not in selected or rank(normalized) > rank(selected[key]):
            selected[key] = normalized
    # Pool order can include original-placement qualification beyond geometry.
    return list(selected.values()), dict(
        sha256=hashlib.sha256(payload).hexdigest(),
        input_rows=len(rows),
        unique_rows=len(selected),
    )


def child_command(root, phase, config, java, accept_eula, metrics_started_at=None):
    folder = root / phase["directory"]
    command = [
        sys.executable,
        str(ROOT / "scripts/search.py"),
        "--root",
        str(folder / "run"),
        "--version",
        config["version"],
        "--verification",
        normalize_verification_mode(config.get("verification_mode", "on")),
        "--devices",
        ",".join(map(str, config["devices"])),
        "--java",
        java,
        "--record-height",
        str(config["record_height"]),
        "--target-height",
        str(config["target_height"]),
        "--layout-template",
        str(folder / "template.json"),
    ]
    if metrics_started_at is not None:
        command.extend(
            [
                "--metrics-root",
                str(root),
                "--metrics-started-at",
                str(metrics_started_at),
            ]
        )
    world = config_world(config)
    command.extend(["--world-type", world["world_type"]])
    if "biome" in world:
        command.extend(["--biome", world["biome"]])
    for version in config.get("verify_versions", [config["version"]]):
        command.extend(["--verify-version", version])
    command.extend(["--verify-workers", str(config.get("verify_workers", 4))])
    for version, executable in config.get("verify_java", {}).items():
        command.extend(["--verify-java", version + "=" + executable])
    if (folder / "run/config.json").exists():
        command.append("--resume")
    if accept_eula:
        command.append("--accept-eula")
    return command


def extend_queue(root, state, pool_path):
    templates, provenance = load_pool(pool_path)
    known = {tuple(phase["identity"][:4]): phase for phase in state["phases"]}
    added = 0
    for row in templates:
        key = base_identity(row)
        if key in known:
            if tuple(known[key]["identity"]) != domain_identity(row):
                raise ValueError(
                    f"Coordinate region mask changed for queued layout {key}"
                )
            continue
        index = len(state["phases"])
        directory = f"phases/phase{index:06d}"
        folder = root / directory
        folder.mkdir(parents=True, exist_ok=True)
        atomic(folder / "template.json", row)
        phase = dict(
            index=index,
            directory=directory,
            identity=list(domain_identity(row)),
            template_sha256=digest(folder / "template.json"),
            status="queued",
            seed_position_trials=0,
            verified_queries=0,
            verified_offset=0,
        )
        state["phases"].append(phase)
        known[key] = phase
        added += 1
    state["pool_source"] = str(pool_path.resolve())
    state["latest_pool"] = provenance
    state["updated_at"] = time.time()
    atomic(root / "state.json", state)
    return added


def check_phase(root, phase):
    folder = root / phase["directory"]
    if digest(folder / "template.json") != phase["template_sha256"]:
        raise ValueError(f"Frozen template changed in phase {phase['index']}")
    normalize_template(read_json(folder / "template.json"))
    child_config = folder / "run/config.json"
    if child_config.exists():
        saved = read_json(child_config)
        row = saved["qualified_search"]["template"]
        if domain_identity(normalize_template(row)) != tuple(phase["identity"]):
            raise ValueError(f"Saved child domain changed in phase {phase['index']}")
        # Verify legacy state before replacing its full-file fingerprint. This
        # runs before launching a resumed child, while its old config is intact.
        if "child_config_sha256" in phase:
            if phase["child_config_sha256"] != digest(child_config):
                raise ValueError(
                    f"Saved child configuration changed in phase {phase['index']}"
                )
        search_config = {key: value for key, value in saved.items()
                         if key not in ("verify_workers", "verify_java")}
        current_hash = hashlib.sha256(json.dumps(
            search_config, sort_keys=True, separators=(",", ":")
        ).encode()).hexdigest()
        if phase.get("child_search_sha256") not in (None, current_hash):
            raise ValueError(
                f"Saved child configuration changed in phase {phase['index']}"
            )
        phase["child_search_sha256"] = current_hash
        phase.pop("child_config_sha256", None)


def tail_records(path, offset):
    if not path.exists():
        return
    with path.open("rb") as stream:
        stream.seek(offset)
        while True:
            begin = stream.tell()
            line = stream.readline()
            if not line.endswith(b"\n"):
                return
            yield begin, stream.tell(), json.loads(line)


def result_key(row):
    return (
        str(row.get("requested_version", row.get("version", ""))),
        str(row["seed"]),
        row["x"],
        row["z"],
        row["native_y"] if normalize_verification_mode(row.get("verification_mode", "on")) == "off" else row["HPos"],
    )


def collect_native(root, state, config, seen, first):
    """Aggregate native candidates without creating vanilla result records."""
    target = None
    for phase in state["phases"]:
        if phase["status"] == "queued":
            continue
        run = root / phase["directory"] / "run"
        progress = read_json(run / "progress.json", {})
        stopped = read_json(run / "STOPPED.json", {})
        phase["seed_position_trials"] = max(phase["seed_position_trials"],
            progress.get("seed_position_trials", 0), stopped.get("seed_position_trials", 0))
        for offset, end, row in tail_records(run / "shortlist.jsonl", phase.get("candidate_offset", 0)):
            if normalize_verification_mode(row.get("verification_mode", "on")) != "off" or "HPos" in row:
                raise ValueError("Native campaign candidate has vanilla result fields")
            if config_world(row) != config_world(config):
                raise ValueError("Result world configuration differs from campaign")
            phase["candidate_offset"] = end
            key = result_key(row)
            if key in seen:
                continue
            seen.add(key)
            record = dict(row, phase=phase["index"], phase_identity=phase["identity"],
                          candidate_record=dict(file=str((run / "shortlist.jsonl").relative_to(root)), offset=offset))
            append(root / "shortlist.jsonl", record)
            height = row["native_y"]
            if height <= config["record_height"]:
                append(root / "low-huts.jsonl", record)
            if str(height) not in first:
                first[str(height)] = record
                append(root / "first-hits.jsonl", record)
            if height <= config["target_height"]:
                target = record
                atomic(root / "NATIVE_TARGET_REACHED.json", record)
    atomic(root / "state.json", state)
    atomic(root / "progress.json", dict(status=state["status"],
        verification_mode="off", active_phase=state.get("active_phase"),
        phases=len(state["phases"]),
        exhausted_phases=sum(p["status"] == "exhausted" for p in state["phases"]),
        seed_position_trials=sum(p["seed_position_trials"] for p in state["phases"]),
        verified_queries=0, native_candidates=len(seen), first_native_y=first,
        updated_at=time.time(),
        metrics_started_at=read_json(root / "metrics-session.json", {}).get("started_at")))
    return target


def collect(root, state, config, seen, first):
    if normalize_verification_mode(config.get("verification_mode", "on")) == "off":
        return collect_native(root, state, config, seen, first)
    target = None
    for phase in state["phases"]:
        if phase["status"] == "queued":
            continue
        run = root / phase["directory"] / "run"
        progress = read_json(run / "progress.json", {})
        stopped = read_json(run / "STOPPED.json", {})
        phase["seed_position_trials"] = max(
            phase["seed_position_trials"],
            progress.get("seed_position_trials", 0),
            stopped.get("seed_position_trials", 0),
        )
        phase["verified_queries"] = max(
            phase["verified_queries"],
            progress.get("verified", 0),
            stopped.get("verified", 0),
        )
        record_file = run / "verified-huts.jsonl"
        for offset, end, row in tail_records(record_file, phase["verified_offset"]):
            if config_world(row) != config_world(config):
                raise ValueError("Result world configuration differs from campaign")
            phase["verified_offset"] = end
            phase_trials = int(
                row.get(
                    "campaign_trials_observed_at_verification",
                    phase["seed_position_trials"],
                )
            )
            phase["seed_position_trials"] = max(
                phase["seed_position_trials"], phase_trials
            )
            key = result_key(row)
            if key in seen:
                continue
            seen.add(key)
            campaign_trials = (
                sum(
                    p["seed_position_trials"] for p in state["phases"] if p is not phase
                )
                + phase_trials
            )
            record = dict(
                **config_world(config),
                verification_mode=normalize_verification_mode(config.get("verification_mode", "on")),
                version=row.get("version"),
                requested_version=row.get("requested_version", config["version"]),
                seed=str(row["seed"]),
                x=row["x"],
                z=row["z"],
                HPos=row["HPos"],
                phase=phase["index"],
                phase_identity=phase["identity"],
                verification_record=dict(
                    file=str(record_file.relative_to(root)), offset=offset
                ),
                campaign_trials_observed_at_verification=campaign_trials,
            )
            for name in (
                "versions",
                "excavation",
                "excavation_from_minus53",
                "verified_at",
                "metrics",
                *LOADING_FIELDS,
            ):
                if name in row:
                    record[name] = row[name]
            if row.get("responses"):
                record["responses"] = {
                    v: str((run / path).relative_to(root))
                    for v, path in row["responses"].items()
                }
            if row.get("response"):
                record["response"] = str((run / row["response"]).relative_to(root))
            append(root / "verified-huts.jsonl", record)
            if row["HPos"] <= config["record_height"]:
                append(root / "low-huts.jsonl", record)
            if str(row["HPos"]) not in first:
                first[str(row["HPos"])] = record
                append(root / "first-hits.jsonl", record)
            if row["HPos"] <= config["target_height"]:
                target = record
                atomic(root / "TARGET_REACHED.json", record)
    atomic(root / "state.json", state)
    progress = dict(
        status=state["status"],
        verification_mode=normalize_verification_mode(config.get("verification_mode", "on")),
        active_phase=state.get("active_phase"),
        phases=len(state["phases"]),
        exhausted_phases=sum(p["status"] == "exhausted" for p in state["phases"]),
        seed_position_trials=sum(p["seed_position_trials"] for p in state["phases"]),
        verified_queries=sum(p["verified_queries"] for p in state["phases"]),
        recorded_huts=len(seen),
        first_exact_HPos=first,
        updated_at=time.time(),
        metrics_started_at=read_json(root / "metrics-session.json", {}).get(
            "started_at"
        ),
    )
    atomic(root / "progress.json", progress)
    return target


def archive_completed_indices(run):
    """Compact finished-phase index logs after its child has stopped."""
    for path in run.glob("gpu*/search*/completed.jsonl"):
        archive = path.parent / "archived-progress.json"
        if archive.exists():
            saved = read_json(archive)
            if saved.get("completed_file_sha256") != digest(path):
                raise ValueError(
                    f"Completed index log differs from its archive: {path}"
                )
        else:
            count = 0
            with path.open("rb") as stream:
                while chunk := stream.read(8 << 20):
                    count += chunk.count(b"\n")
            atomic(
                archive,
                dict(
                    seed_position_trials=count * 65536,
                    completed_roots=count,
                    completed_file_sha256=digest(path),
                    completed_file_bytes=path.stat().st_size,
                ),
            )
        path.unlink()


def process_identity(pid):
    try:
        fields = (
            Path(os.sep, "proc", str(pid), "stat").read_text().rsplit(")", 1)[1].split()
        )
        return dict(start_ticks=int(fields[19]), state=fields[0])
    except (FileNotFoundError, ProcessLookupError):
        return None


class ExistingChild:
    """Adopt a child surviving its campaign supervisor."""

    def __init__(self, record, run):
        self.pid = record["pid"]
        self.start_ticks = record["start_ticks"]
        self.run = run
        self.returncode = None

    def poll(self):
        identity = process_identity(self.pid)
        if (
            identity
            and identity["start_ticks"] == self.start_ticks
            and identity["state"] != "Z"
        ):
            return None
        stopped = read_json(self.run / "STOPPED.json", {})
        self.returncode = (
            0
            if stopped.get("reason")
            in ("coordinate-domain-exhausted", "verified-target-height", "native-target-height", "interrupted")
            else 1
        )
        return self.returncode

    def send_signal(self, number):
        if self.poll() is None:
            os.kill(self.pid, number)

    def wait(self, timeout):
        deadline = time.monotonic() + timeout
        while self.poll() is None:
            if time.monotonic() >= deadline:
                raise subprocess.TimeoutExpired(str(self.pid), timeout)
            time.sleep(0.1)
        return self.returncode


def surviving_child(folder):
    record = read_json(folder / "launch.json", {}).get("process")
    if not record:
        return None
    child = ExistingChild(record, folder / "run")
    if child.poll() is None:
        command = (
            Path(os.sep, "proc", str(child.pid), "cmdline").read_bytes().split(b"\0")
        )
        if str(folder / "run").encode() not in command:
            raise RuntimeError(
                "Saved child process identity differs from its run directory"
            )
        return child
    return None


def recover_results(root, config):
    native = normalize_verification_mode(config.get("verification_mode", "on")) == "off"
    name = "shortlist.jsonl" if native else "verified-huts.jsonl"
    height_field = "native_y" if native else "HPos"
    marker = "NATIVE_TARGET_REACHED.json" if native else "TARGET_REACHED.json"
    records = [row for _, _, row in tail_records(root / name, 0)]
    if any(config_world(row) != config_world(config) for row in records):
        raise ValueError("Saved results contain a different world configuration")
    seen = {result_key(row) for row in records}
    first = {str(row[height_field]): row
             for _, _, row in tail_records(root / "first-hits.jsonl", 0)}
    low = {result_key(row) for _, _, row in tail_records(root / "low-huts.jsonl", 0)}
    for row in records:
        height = row[height_field]
        if height <= config["record_height"] and result_key(row) not in low:
            append(root / "low-huts.jsonl", row)
            low.add(result_key(row))
        if str(height) not in first:
            append(root / "first-hits.jsonl", row)
            first[str(height)] = row
        if height <= config["target_height"] and not (root / marker).exists():
            atomic(root / marker, row)
    return seen, first


def phase_exhausted(run, config):
    stopped = read_json(run / "STOPPED.json", {})
    return stopped.get("reason") == "coordinate-domain-exhausted" and all(
        (run / f"gpu{device}" / "EXHAUSTED.json").exists()
        for device in config["devices"]
    )


def stop_child(process):
    if process and process.poll() is None:
        process.send_signal(signal.SIGTERM)
        try:
            process.wait(timeout=60)
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                "Search child did not finish its shutdown; its phase remains active"
            )


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--layout-pool", type=Path)
    parser.add_argument("--extend-pool", type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--version")
    parser.add_argument("--world-type", choices=WORLD_TYPES)
    parser.add_argument("--biome")
    parser.add_argument("--devices")
    parser.add_argument("--metrics-started-at", type=float)
    parser.add_argument("--record-height", type=int)
    parser.add_argument("--target-height", type=int)
    parser.add_argument("--java", default="java")
    parser.add_argument("--verification", choices=("off", "on"),
                        help="Vanilla verification mode (default: on; resume keeps saved mode)")
    parser.add_argument("--verify-version", action="append")
    parser.add_argument("--verify-java", action="append", metavar="VERSION=JAVA")
    parser.add_argument("--verify-workers", type=int)
    parser.add_argument("--accept-eula", action="store_true")
    parser.add_argument("--stop-when-pool-exhausted", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    parser.add_argument(
        "--archive-completed-indices",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    options = parser.parse_args()
    if options.poll_seconds <= 0:
        parser.error("Polling interval must be positive")
    if options.verify_workers is not None and options.verify_workers < 1:
        parser.error("--verify-workers must be positive")
    if not options.resume and not options.plan_only and options.verification != "off" and not options.accept_eula:
        parser.error("Supply --accept-eula when launching the vanilla query service")
    return options


def main():
    options = parse_args()
    metrics_started_at = (
        options.metrics_started_at
        if options.metrics_started_at is not None
        else time.time()
    )
    root = options.root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    lock = (root / "campaign.lock").open("a")
    fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    atomic(root / "metrics-session.json", dict(started_at=metrics_started_at))
    config_path = root / "config.json"
    if config_path.exists():
        config = read_json(config_path)
        saved_world = config_world(config)
        if options.world_type is not None or options.biome is not None:
            selected_type = options.world_type or saved_world["world_type"]
            selected_biome = options.biome if options.biome is not None else (saved_world.get("biome") if selected_type == "single_biome" else None)
            if world_config(selected_type, selected_biome) != saved_world:
                raise ValueError("Saved campaign uses a different world configuration")
        config.update(saved_world)
        for name in ("version", "record_height", "target_height"):
            selected = getattr(options, name)
            if selected is not None and selected != config[name]:
                raise ValueError(f"Saved campaign uses a different {name}")
        if (
            options.devices
            and list(map(int, options.devices.split(","))) != config["devices"]
        ):
            raise ValueError("Saved campaign uses different GPU IDs")
        if not options.resume and not options.plan_only:
            raise ValueError("Use --resume for the saved campaign")
        state = read_json(root / "state.json")
        previous = normalize_verification_mode(config.get("verification_mode", "on"))
        mode = normalize_verification_mode(options.verification or previous)
        if mode != previous:
            data_files = [*root.glob("*.jsonl"), *root.glob("phases/*/run/*.jsonl")]
            if any(p.stat().st_size for p in data_files) or any(p["status"] != "queued" for p in state["phases"]):
                raise ValueError("Saved campaign has data from a different verification mode; create a new run root")
        config["verification_mode"] = mode
    else:
        if not options.layout_pool:
            raise ValueError("New campaigns require --layout-pool")
        devices = list(map(int, (options.devices or "0,1,2,3,4,5,6,7").split(",")))
        if (
            not devices
            or len(set(devices)) != len(devices)
            or not set(devices) <= set(range(8))
        ):
            raise ValueError("GPU IDs must be distinct values in0..7")
        config = dict(
            **world_config(options.world_type or "normal", options.biome),
            schema_version=1,
            version=options.version or "1.21",
            verification_mode=options.verification or "on",
            devices=devices,
            record_height=(
                -55 if options.record_height is None else options.record_height
            ),
            target_height=(
                -59 if options.target_height is None else options.target_height
            ),
            started_at=time.time(),
        )
        state = dict(schema_version=1, status="planned", active_phase=None, phases=[])
        atomic(config_path, config)
        extend_queue(root, state, options.layout_pool)
    mode = config["verification_mode"]
    if mode not in ("off", "on"):
        raise ValueError("Verification mode must be on or off")
    target_marker = "NATIVE_TARGET_REACHED.json" if mode == "off" else "TARGET_REACHED.json"
    target_status = "native-target-height" if mode == "off" else "verified-target-height"
    if mode != "off" and not options.plan_only and not options.accept_eula:
        raise ValueError("Supply --accept-eula when launching the vanilla query service")
    versions, executables = verification_options(
        config["version"],
        options.verify_version or config.get("verify_versions"),
        options.verify_java,
    )
    if (
        config_path.exists()
        and options.verify_version
        and "verify_versions" in config
        and versions != config["verify_versions"]
    ):
        raise ValueError("Saved campaign uses different verification versions")
    config["verify_versions"] = versions
    config["verify_workers"] = options.verify_workers or config.get("verify_workers", 4)
    config["verify_java"] = dict(config.get("verify_java", {}), **executables)
    atomic(config_path, config)
    for path in (options.extend_pool, options.layout_pool):
        if path:
            extend_queue(root, state, path)
    for phase in state["phases"]:
        check_phase(root, phase)
        require_layout_version(
            read_json(root / phase["directory"] / "template.json"), config["version"]
        )
    if options.plan_only:
        plan = dict(
            config=config,
            phases=[
                dict(
                    index=p["index"],
                    identity=p["identity"],
                    status=p["status"],
                    command=child_command(
                        root, p, config, options.java, True, metrics_started_at
                    ),
                )
                for p in state["phases"]
            ],
        )
        atomic(root / "plan.json", plan)
        print(
            json.dumps(
                dict(
                    status="planned",
                    phases=len(state["phases"]),
                    plan=str(root / "plan.json"),
                )
            )
        )
        lock.close()
        return
    seen, first = recover_results(root, config)
    if state.get("status") == "world-has-no-witch-huts":
        lock.close()
        return
    process = None
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    try:
        if (
            collect(root, state, config, seen, first)
            or (root / target_marker).exists()
        ):
            state["status"] = target_status
            return
        while True:
            source = Path(state["pool_source"])
            if source.exists() and digest(source) != state["latest_pool"]["sha256"]:
                extend_queue(root, state, source)
            phase = next(
                (p for p in state["phases"] if p["status"] != "exhausted"), None
            )
            if phase is None:
                state["status"] = "awaiting-layouts"
                state["active_phase"] = None
                collect(root, state, config, seen, first)
                if options.stop_when_pool_exhausted:
                    break
                time.sleep(options.poll_seconds)
                continue
            state["status"] = "running"
            state["active_phase"] = phase["index"]
            phase["status"] = "running"
            check_phase(root, phase)
            atomic(root / "state.json", state)
            command = child_command(
                root,
                phase,
                config,
                options.java,
                options.accept_eula,
                metrics_started_at,
            )
            folder = root / phase["directory"]
            process = surviving_child(folder)
            if process is None and phase_exhausted(folder / "run", config):
                phase["status"] = "exhausted"
                phase["completed_at"] = time.time()
                if options.archive_completed_indices:
                    archive_completed_indices(folder / "run")
                state["active_phase"] = None
                atomic(root / "state.json", state)
                continue
            if process is None:
                with (folder / "supervisor.log").open("ab") as log:
                    process = subprocess.Popen(
                        command,
                        cwd=ROOT,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        start_new_session=True,
                    )
                identity = process_identity(process.pid)
                atomic(
                    folder / "launch.json",
                    dict(
                        command=command,
                        started_at=time.time(),
                        process=(
                            dict(pid=process.pid, start_ticks=identity["start_ticks"])
                            if identity
                            else None
                        ),
                    ),
                )
            while process.poll() is None:
                source = Path(state["pool_source"])
                if source.exists() and digest(source) != state["latest_pool"]["sha256"]:
                    extend_queue(root, state, source)
                check_phase(root, phase)
                if collect(root, state, config, seen, first):
                    stop_child(process)
                    state["status"] = target_status
                    return
                time.sleep(options.poll_seconds)
            collect(root, state, config, seen, first)
            if (root / target_marker).exists():
                state["status"] = target_status
                return
            stopped = read_json(folder / "run/STOPPED.json", {})
            if process.returncode == 0 and stopped.get("reason") == "world-has-no-witch-huts":
                state["status"] = "world-has-no-witch-huts"
                state["active_phase"] = None
                for queued in state["phases"]:
                    queued["status"] = "world-has-no-witch-huts"
                    queued["completed_at"] = time.time()
                atomic(root / "WORLD_HAS_NO_WITCH_HUTS.json", dict(
                    **config_world(config), versions=config["verify_versions"],
                    hut_biomes=["minecraft:swamp"], registry_validated=mode != "off",
                    verification_mode=mode,
                    reason=state["status"], phase=phase["index"], finished_at=time.time(),
                ))
                return
            if (
                process.returncode != 0
                or stopped.get("reason") != "coordinate-domain-exhausted"
            ):
                phase["status"] = (
                    "interrupted"
                    if stopped.get("reason") == "interrupted"
                    else "failed"
                )
                raise RuntimeError(
                    f"Phase {phase['index']} stopped: {stopped.get('reason', 'no shutdown record')}; exit {process.returncode}"
                )
            phase["status"] = "exhausted"
            phase["completed_at"] = time.time()
            if options.archive_completed_indices:
                archive_completed_indices(folder / "run")
            state["active_phase"] = None
            atomic(root / "state.json", state)
            process = None
    except KeyboardInterrupt:
        state["status"] = "interrupted"
    except Exception as error:
        state["status"] = "failed"
        atomic(root / "ERROR.json", dict(at=time.time(), error=str(error)))
        raise
    finally:
        stop_child(process)
        collect(root, state, config, seen, first)
        atomic(root / "state.json", state)
        atomic(
            root / "STOPPED.json",
            dict(
                reason=state["status"],
                stopped_at=time.time(),
                seed_position_trials=sum(
                    p["seed_position_trials"] for p in state["phases"]
                ),
            ),
        )
        lock.close()


if __name__ == "__main__":
    main()
