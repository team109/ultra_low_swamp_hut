"""Search a qualified mineshaft layout with one pipeline per GPU."""

import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from ultra_low_hut import ROOT
from ultra_low_hut.versions import resolve_hunt
from ultra_low_hut.world_types import WORLD_TYPES, config_world, world_config, world_build_profile, world_has_witch_huts
from ultra_low_hut.search.reference.native import LIB as CPU_LIBRARY
from ultra_low_hut.layouts.catalog import require_natural_template, require_layout_version
from ultra_low_hut.verification.service import start
from ultra_low_hut.verification.client import (
    VerificationGroup,
    excavation_fields,
    loading_order_fields,
    verification_options,
)
from ultra_low_hut.verification.loading_orders import LOADING_FIELDS, get_order_spec, normalize_verification_mode
from ultra_low_hut.search.metrics import SearchMetrics
from ultra_low_hut.search.log import SearchLog


def atomic(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2))
    temporary.replace(path)


def append(path, value):
    with path.open("a") as stream:
        stream.write(json.dumps(value) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def rows(path):
    if path.exists():
        with path.open() as stream:
            for line in stream:
                if line.endswith("\n"):
                    yield json.loads(line)


def completed_record_count(path):
    """Count committed JSONL records without decoding millions of saved rows."""
    with path.open("rb") as stream:
        return sum(
            chunk.count(b"\n") for chunk in iter(lambda: stream.read(8 << 20), b"")
        )


def resume_worker(directory, slot, shards, policy):
    directory.mkdir(exist_ok=True)
    done = [
        (int(p.stem[4:]), json.loads(p.read_text()))
        for p in directory.glob("done*.json")
    ]
    active = (
        json.loads((directory / "active.json").read_text())
        if (directory / "active.json").exists()
        else None
    )
    last = max(done, default=None, key=lambda item: item[0])
    job = last[1]["job"] if last else None
    unfinished = None
    if active and (last is None or active["round"] > last[0]):
        source = directory / f"search{active['round']:06d}"
        indices = [row["index"] for row in rows(source / "completed.jsonl")]
        # A resumed job may itself be interrupted. Carry its previous skips forward.
        previous = active["job"].get("resume_skip")
        if previous:
            indices.extend(json.loads(Path(previous).read_text()))
        skip = directory / f"resume-skip-{active['round']:06d}.json"
        atomic(skip, sorted(set(indices)))
        job = dict(active["job"], resume_skip=str(skip))
        unfinished = dict(geometry=active["geometry"], job=job)
    next_round = 1 + max([n for n, _ in done] + ([active["round"]] if active else [-1]))
    state = dict(
        next_round=next_round,
        unfinished=unfinished,
        resume_k=job["k"] if job else policy["first_k"],
        resume_begin=(
            job["ranges"][-1][0] + shards * policy["inverse_chunk"]
            if job
            else slot * policy["inverse_chunk"]
        ),
    )
    atomic(directory / "resume-state.json", state)


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


def load_layout_template(path):
    payload = path.read_bytes()
    document = json.loads(payload)
    if isinstance(document, list):
        if len(document) != 1:
            raise ValueError("--layout-template requires exactly one template")
        document = document[0]
    if not isinstance(document, dict) or any(
        field not in document for field in TEMPLATE_FIELDS
    ):
        raise ValueError("Layout template must contain " + ", ".join(TEMPLATE_FIELDS))
    row = dict(document)
    for field in TEMPLATE_FIELDS:
        value = row[field]
        if isinstance(value, bool) or not isinstance(value, (str, int)):
            raise ValueError(f"Layout template field {field} must be an integer")
        try:
            integer = int(value)
        except ValueError as error:
            raise ValueError(
                f"Layout template field {field} must be an integer"
            ) from error
        if str(integer) != str(value):
            raise ValueError(
                f"Layout template field {field} must be a canonical integer"
            )
        row[field] = integer
    for field in ("original", "target"):
        if not 0 <= row[field] < 1 << 48:
            raise ValueError(f"Layout template {field} must fit low48")
        row[field] = str(row[field])
    for field in TEMPLATE_FIELDS[2:]:
        if not -(1 << 31) <= row[field] < 1 << 31:
            raise ValueError(
                f"Layout template field {field} must fit a signed32-bit integer"
            )
    if row["width"] not in (7, 9) or row["relx"] % 16 or row["relz"] % 16:
        raise ValueError(
            "Layout template requires width7/9 and chunk-aligned hut offsets"
        )
    if (
        row["g53"] < 0
        or row["g54"] < 0
        or not 0 <= row["covered"] <= 63
        or row["pieces"] < 1
    ):
        raise ValueError("Layout template gains, coverage or piece count are invalid")
    if "coordinate_regions_mask" in row:
        mask = row["coordinate_regions_mask"]
        if type(mask) is not int or not 1 <= mask <= 511:
            raise ValueError(
                "Coordinate-region mask must select one or more of the nine regions"
            )
    require_natural_template(row)
    return row


def template_identity(row):
    return tuple(int(row[field]) for field in TEMPLATE_FIELDS) + (
        row.get("coordinate_regions_mask", 511),
    )


def verification_mode(root, saved=None, requested=None):
    """Resume an existing mode; changing populated runs requires a new root."""
    previous = normalize_verification_mode((saved or {}).get("verification_mode", "on"))
    selected = normalize_verification_mode(requested or (previous if saved is not None else "on"))
    if saved is not None and selected != previous:
        records = [*root.glob("*.jsonl"), *root.glob("gpu*/**/completed.jsonl"),
                   *root.glob("gpu*/**/shortlist.jsonl")]
        if any(p.stat().st_size for p in records) or any(root.glob("gpu*/active.json")) or any(root.glob("gpu*/done*.json")):
            raise ValueError("Saved run has data from a different verification mode; create a new run root")
    return selected


def native_record(candidate, config, trials):
    """Retain the native estimate without manufacturing vanilla measurements."""
    reference = candidate.get("reference", {})
    if not reference.get("accepted") or type(reference.get("y")) is not int:
        raise ValueError("Native shortlist candidate has no accepted reference height")
    record = dict(candidate)
    for field in ("HPos", "verified_at", "versions", "responses", "response", "verification", *LOADING_FIELDS):
        record.pop(field, None)
    record.update(**config_world(config), version=config["version"],
                  requested_version=config["version"], verification_mode="off",
                  native_y=reference["y"], candidate_at=time.time(),
                  campaign_trials_observed_at_screening=trials)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--version", default="1.21")
    parser.add_argument("--world-type", choices=WORLD_TYPES)
    parser.add_argument("--biome")
    parser.add_argument("--devices", default="0,1,2,3,4,5,6,7")
    parser.add_argument("--java", default="java")
    parser.add_argument("--verification", choices=("off", "on"),
                        help="Vanilla verification mode (default: on; resume keeps saved mode)")
    parser.add_argument("--verify-version", action="append")
    parser.add_argument("--verify-java", action="append", metavar="VERSION=JAVA")
    parser.add_argument("--verify-workers", type=int, help="Parallel vanilla JVM workers per verification version (default: 4)")
    parser.add_argument("--metrics-started-at", type=float)
    parser.add_argument("--metrics-root", type=Path)
    parser.add_argument("--record-height", type=int, default=-55)
    parser.add_argument("--target-height", type=int, default=-59)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--exhaust",
        action="store_true",
        help="Continue through the entire configured inverse domain after reaching the target height",
    )
    parser.add_argument(
        "--layout-template",
        type=Path,
        help="Externally qualified single template JSON object or one-row array",
    )
    parser.add_argument("--accept-eula", action="store_true")
    args = parser.parse_args()
    if args.verify_workers is not None and args.verify_workers < 1:
        parser.error("--verify-workers must be positive")
    if not args.resume and args.verification != "off" and not args.accept_eula:
        parser.error("Read the Minecraft EULA and supply --accept-eula")
    selected_template = None
    if args.layout_template:
        try:
            selected_template = load_layout_template(
                args.layout_template
            )
        except (ValueError, OSError) as error:
            parser.error(str(error))
    root = args.root.resolve()
    if args.resume:
        config = json.loads((root / "config.json").read_text())
        saved_world = config_world(config)
        if args.world_type is not None or args.biome is not None:
            selected_type = args.world_type or saved_world["world_type"]
            selected_biome = args.biome if args.biome is not None else (saved_world.get("biome") if selected_type == "single_biome" else None)
            selected_world = world_config(selected_type, selected_biome)
            if selected_world != saved_world:
                parser.error("Saved run uses a different world configuration")
        config.update(saved_world)
        try:
            config["verification_mode"] = verification_mode(root, config, args.verification)
        except ValueError as error:
            parser.error(str(error))
        require_natural_template(config["qualified_search"]["template"])
        if selected_template is not None and template_identity(
            selected_template
        ) != template_identity(config["qualified_search"]["template"]):
            parser.error(
                "Saved run uses a different layout template; create a new run root"
            )
    else:
        try:
            selected_world = world_config(args.world_type or "normal", args.biome)
        except ValueError as error:
            parser.error(str(error))
        devices = list(map(int, args.devices.split(",")))
        if (
            not devices
            or len(set(devices)) != len(devices)
            or not set(devices) <= set(range(8))
        ):
            parser.error("GPU IDs must be distinct values in 0..7")
        profile = resolve_hunt(args.version, -62, True)
        build = ROOT / "runs/hut-build" / world_build_profile(profile["build_profile"] + "-qualified", selected_world["world_type"])
        built = json.loads((build / "config.json").read_text())
        if built["screen"] != profile["screen"]:
            raise RuntimeError("Rebuild the selected version profile")
        if config_world(built)["world_type"] != selected_world["world_type"]:
            raise RuntimeError("Rebuild the selected world type profile")
        qualified_search = dict(built["qualified_search"])
        if selected_template is not None:
            qualified_search["template"] = selected_template
        require_layout_version(qualified_search["template"], profile["requested_version"])
        root.mkdir(parents=True, exist_ok=False)
        config = dict(
            **selected_world,
            cpu_library=str(CPU_LIBRARY),
            version=args.version,
            verification_mode=args.verification or "on",
            devices=devices,
            started_at=time.time(),
            record_height=args.record_height,
            target_height=args.target_height,
            stop_on_target=not args.exhaust,
            build_dir=str(build.relative_to(ROOT)),
            qualified_search=qualified_search,
        )
    mode = config["verification_mode"]
    if mode != "off" and not args.accept_eula:
        parser.error("Read the Minecraft EULA and supply --accept-eula")
    require_layout_version(config["qualified_search"]["template"], config["version"])
    config.setdefault("cpu_library", str(CPU_LIBRARY))
    verify_versions, verify_java = verification_options(
        config["version"],
        args.verify_version or config.get("verify_versions"),
        args.verify_java,
    )
    if (
        args.resume
        and args.verify_version
        and verify_versions != config.get("verify_versions", [config["version"]])
    ):
        parser.error("Saved run uses different verification versions")
    config["verify_versions"] = verify_versions
    loading_policy = get_order_spec(mode)["id"] if mode != "off" else None
    if args.resume and mode != "off" and config.get("verification_loading_policy") != loading_policy and any(p.exists() and p.stat().st_size for p in [root / "validation.jsonl", root / "verified-huts.jsonl"]):
        parser.error("This run uses a different verification policy; start a new run root")
    if mode != "off":
        config["verification_loading_policy"] = loading_policy
    else:
        config.pop("verification_loading_policy", None)
    config["verify_workers"] = args.verify_workers or config.get("verify_workers", 4)
    if args.exhaust:
        config["stop_on_target"] = False
    config["verify_java"] = dict(config.get("verify_java", {}), **verify_java)
    lock = (root / "search.lock").open("a")
    fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    atomic(root / "config.json", config)
    policy = config["qualified_search"]
    for name in (("shortlist.jsonl", "low-huts.jsonl", "first-hits.jsonl") if mode == "off"
                 else ("verified-huts.jsonl", "low-huts.jsonl", "first-hits.jsonl")):
        (root / name).touch()
    for slot, device in enumerate(config["devices"]):
        resume_worker(root / f"gpu{device}", slot, len(config["devices"]), policy)
    native_rows = list(rows(root / "shortlist.jsonl")) if mode == "off" else []
    verified_rows = list(rows(root / "verified-huts.jsonl")) if mode != "off" else []
    validations = list(rows(root / "validation.jsonl"))
    if any(config_world(row) != config_world(config) for row in verified_rows + validations + native_rows):
        parser.error("Saved results contain a different world configuration")
    seen = {(row["seed"], row["x"], row["z"]) for row in verified_rows + native_rows}
    seen.update((row["seed"], row["x"], row["z"]) for row in validations)
    height_field = "native_y" if mode == "off" else "HPos"
    first = {str(row[height_field]): row for row in rows(root / "first-hits.jsonl")}
    if config.get("stop_on_target", True) and any(
        row[height_field] <= config["target_height"] for row in verified_rows + native_rows
    ):
        print("The saved run already reached its target height.")
        lock.close()
        return
    trials = 65536 * sum(
        completed_record_count(path)
        for path in root.glob("gpu*/search*/completed.jsonl")
    )
    trials += sum(
        json.loads(path.read_text())["seed_position_trials"]
        for path in root.glob("gpu*/search*/archived-progress.json")
    )
    verified = len(seen) if mode != "off" else 0
    offsets = {
        str(path): path.stat().st_size
        for path in root.glob("gpu*/search*/completed.jsonl")
    }
    pending, active, workers, services = [], None, [], []
    stop, reason = False, "interrupted"
    resumed_at, initial_trials = time.time(), trials
    public_log = SearchLog(root, config["started_at"]) if mode != "off" else None
    if public_log:
        for row in rows(root / "low-huts.jsonl"):
            public_log.discovery(row)
    metrics_started_at = (
        args.metrics_started_at if args.metrics_started_at is not None else resumed_at
    )
    metrics = SearchMetrics(
        args.metrics_root or root,
        metrics_started_at,
        config["record_height"],
        verify_versions,
    )
    atomic(
        root / "metrics-session.json",
        dict(started_at=metrics_started_at, controller_started_at=resumed_at),
    )
    session = f"verifier-{time.time_ns()}"
    verifier = root / session
    directories = {v: verifier / v for v in verify_versions}
    verification = (VerificationGroup(verify_versions, directories, verification_mode=mode, **config_world(config))
                    if mode != "off" else None)

    def interrupted(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupted)

    def new_rows(path):
        with path.open() as stream:
            stream.seek(offsets.get(str(path), 0))
            while True:
                line = stream.readline()
                if not line or not line.endswith("\n"):
                    break
                offsets[str(path)] = stream.tell()
                yield json.loads(line)

    def collect():
        nonlocal trials, verified, active, stop, reason
        for path in root.glob("gpu*/search*/completed.jsonl"):
            trials += sum(65536 for _ in new_rows(path))
        for path in root.glob("gpu*/search*/shortlist.jsonl"):
            for row in new_rows(path):
                key = row["seed"], row["x"], row["z"]
                if key not in seen:
                    seen.add(key)
                    row["discovery"]["campaign_trials_observed_at_enqueue"] = trials
                    if mode == "off":
                        record = native_record(row, config, trials)
                        append(root / "shortlist.jsonl", record)
                        height = record["native_y"]
                        if height <= config["record_height"]:
                            append(root / "low-huts.jsonl", record)
                        if str(height) not in first:
                            first[str(height)] = record
                            append(root / "first-hits.jsonl", record)
                        if height <= config["target_height"]:
                            atomic(root / "NATIVE_TARGET_REACHED.json", record)
                            if config.get("stop_on_target", True):
                                stop, reason = True, "native-target-height"
                    else:
                        pending.append(row)
        if any(service.poll() is not None for service in services):
            raise RuntimeError("Vanilla generation service exited")
        if active:
            completed = verification.collect(active)
            if completed is not None:
                candidate, active = active[1], None
                grouped, responses = completed
                verified += 1
                metrics.result(candidate, grouped)
                metrics_snapshot = metrics.snapshot(root, trials)
                response_paths = {
                    version: str(item["response"].relative_to(root))
                    for version, item in responses.items()
                }
                for height, versions in grouped.items():
                    row = dict(
                        **config_world(config),
                        version=versions[0],
                        versions=versions,
                        requested_version=config["version"],
                        seed=candidate["seed"],
                        x=candidate["x"],
                        z=candidate["z"],
                        HPos=height,
                        discovery=candidate["discovery"],
                        verified_at=time.time(),
                        campaign_trials_observed_at_verification=trials,
                        verification="vanilla in-memory generation service",
                        verification_mode=mode,
                        response=next(
                            response_paths[v]
                            for v, item in responses.items()
                            if item["result"].get("version", v) == versions[0]
                        ),
                        responses=response_paths,
                        metrics=metrics_snapshot,
                        **excavation_fields(candidate),
                        **loading_order_fields(responses, versions),
                    )
                    append(root / "verified-huts.jsonl", row)
                    if height <= config["record_height"]:
                        append(root / "low-huts.jsonl", row)
                        public_log.discovery(row)
                    if str(height) not in first:
                        first[str(height)] = row
                        append(root / "first-hits.jsonl", row)
                    if height <= config["target_height"]:
                        atomic(root / "TARGET_REACHED.json", row)
                        if config.get("stop_on_target", True):
                            stop, reason = True, "verified-target-height"
                append(
                    root / "validation.jsonl",
                    dict(
                        **config_world(config),
                        seed=candidate["seed"],
                        x=candidate["x"],
                        z=candidate["z"],
                        verified_at=time.time(),
                        verification_mode=mode,
                        responses=response_paths,
                        metrics=metrics_snapshot,
                        versions={
                            v: {
                                "heights": item["result"].get("heights", []),
                                **{f: item["result"][f] for f in LOADING_FIELDS if f in item["result"]},
                                **(
                                    {"error": item["result"]["error"]}
                                    if "error" in item["result"]
                                    else {}
                                ),
                            }
                            for v, item in responses.items()
                        },
                        **excavation_fields(candidate),
                    ),
                )
        if verification is not None and active is None and pending and not stop and verification.ready():
            active = verification.submit(pending.pop(0), atomic)
            metrics.query(active[1])
        elapsed = time.time() - resumed_at
        if public_log:
            public_log.progress(
                trials,
                verified,
                len(pending) + bool(active),
                [device for device, proc in workers if proc.poll() is None],
                trials_per_second=(trials - initial_trials) / max(1, elapsed),
            )
        atomic(
            root / "progress.json",
            dict(
                started_at=config["started_at"],
                deadline_at=None,
                seed_position_trials=trials,
                verified=verified,
                pending=len(pending) + bool(active),
                verification_mode=mode,
                native_candidates=len(seen) if mode == "off" else 0,
                **{("first_native_y" if mode == "off" else "first_exact_HPos"): first},
                running_gpus=[
                    device for device, proc in workers if proc.poll() is None
                ],
                metrics=metrics.snapshot(root, trials),
                metrics_started_at=metrics_started_at,
                session_elapsed_seconds=elapsed,
                session_trials_per_second=(trials - initial_trials) / max(1, elapsed),
            ),
        )

    try:
        records = {}
        if mode != "off":
            verifier.mkdir()
            for version in verify_versions:
                service, record = start(
                    version,
                    directories[version],
                    config["verify_java"].get(version, args.java),
                    workers=config["verify_workers"],
                )
                services.append(service)
                records[version] = record
            deadline = time.monotonic() + 120
            while True:
                if any(service.poll() is not None for service in services):
                    raise RuntimeError("Vanilla generation service exited before verifier readiness")
                if verification.ready():
                    break
                if time.monotonic() >= deadline:
                    raise TimeoutError("Vanilla verification readiness timed out")
                time.sleep(0.05)
        if not world_has_witch_huts(config):
            stop, reason = True, "world-has-no-witch-huts"
            atomic(root / "WORLD_HAS_NO_WITCH_HUTS.json", dict(
                **config_world(config), versions=verify_versions,
                hut_biomes=["minecraft:swamp"], registry_validated=mode != "off",
                verification_mode=mode,
                reason=reason, finished_at=time.time(),
            ))
            return
        for device in config["devices"]:
            with (root / f"gpu{device}-session.log").open("w") as log:
                proc = subprocess.Popen(
                    [
                        sys.executable,
                        str(ROOT / "scripts/search/worker.py"),
                        "--root",
                        str(root),
                        "--device",
                        str(device),
                    ],
                    cwd=ROOT,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            workers.append((device, proc))
        atomic(
            root / "processes.json",
            dict(
                supervisor=os.getpid(),
                workers=[p.pid for _, p in workers],
                verifier=next(iter(records.values()), None),
                verification_mode=mode,
                verifiers=records,
            ),
        )
        while not stop:
            collect()
            worker_status = [(device, proc.poll()) for device, proc in workers]
            failed = [
                device for device, status in worker_status if status not in (None, 0)
            ]
            if failed:
                raise RuntimeError("GPU workers failed: " + str(failed))
            if not stop and all(status is not None for _, status in worker_status):
                # Workers can publish their final shortlist after the collection
                # above. Once all have exited, no writer remains: drain again
                # and keep the services alive until every candidate is verified.
                collect()
                if not stop and not pending and active is None:
                    reason = "coordinate-domain-exhausted"
                    break
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    except BaseException as error:
        reason = "error"
        atomic(root / "ERROR.json", dict(at=time.time(), error=repr(error)))
        raise
    finally:
        for _, proc in workers:
            terminate(proc)
        if (
            (mode == "off" or services)
            and all(service.poll() is None for service in services)
            and reason != "error"
        ):
            collect()
        for service in services:
            terminate(service)
        atomic(
            root / "STOPPED.json",
            dict(
                stopped_at=time.time(),
                seed_position_trials=trials,
                verified=verified,
                verification_mode=mode,
                native_candidates=len(seen) if mode == "off" else 0,
                pending=len(pending) + bool(active),
                reason=reason,
            ),
        )
        if public_log:
            public_log.progress(
                trials, verified, len(pending) + bool(active), [], reason, force=True
            )
        lock.close()


def terminate(process):
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()


if __name__ == "__main__":
    main()
