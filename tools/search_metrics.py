"""Capture search counters at verification time from small progress records."""

from collections import Counter
import json
from pathlib import Path
import time


def read_json(path, default=None):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return default


class SearchMetrics:
    def __init__(self, root, started_at, record_height, versions):
        self.root = Path(root)
        self.started_at = started_at
        self.record_height = record_height
        self.versions = versions
        self.finished = {}
        self.offsets = {}
        self.queried = set()
        self.completed = set()
        self.passed = {v: set() for v in versions}
        self.confirmed = {v: set() for v in versions}
        self.heights = set()

    def runs(self):
        state = read_json(self.root / "state.json", {})
        if "phases" in state:
            return [self.root / p["directory"] / "run" for p in state["phases"]]
        return [self.root]

    @staticmethod
    def key(candidate):
        return str(candidate["seed"]), candidate["x"], candidate["z"]

    def query(self, candidate):
        self.queried.add(self.key(candidate))

    def result(self, candidate, grouped):
        key = self.key(candidate)
        self.queried.add(key)
        self.completed.add(key)
        for height, versions in grouped.items():
            self.heights.add((*key, height))
            for version in versions:
                self.confirmed.setdefault(version, set()).add(key)
            if height <= self.record_height:
                for version in versions:
                    self.passed.setdefault(version, set()).add(key)

    def history(self, run):
        for name in ("verified-huts.jsonl", "validation.jsonl"):
            path = run / name
            if not path.exists():
                continue
            with path.open() as stream:
                stream.seek(self.offsets.get(path, 0))
                while True:
                    line = stream.readline()
                    if not line.endswith("\n"):
                        break
                    self.offsets[path] = stream.tell()
                    row = json.loads(line)
                    key = self.key(row)
                    if name == "verified-huts.jsonl":
                        self.heights.add((*key, row["HPos"]))
                    if row.get("verified_at", 0) < self.started_at:
                        continue
                    self.queried.add(key)
                    self.completed.add(key)
                    if name == "verified-huts.jsonl":
                        for version in row.get("versions", [row.get("version")]):
                            if version:
                                self.confirmed.setdefault(version, set()).add(key)
                                if row["HPos"] <= self.record_height:
                                    self.passed.setdefault(version, set()).add(key)

    def snapshot(self, current_run, current_trials, now=None):
        now = time.time() if now is None else now
        counts = Counter()
        stages = Counter()
        inverse = Counter()
        cumulative_trials = 0
        for run in self.runs():
            progress = read_json(run / "progress.json", {})
            stopped = read_json(run / "STOPPED.json", {})
            cumulative_trials += (
                current_trials
                if run.resolve() == Path(current_run).resolve()
                else max(
                    progress.get("seed_position_trials", 0),
                    stopped.get("seed_position_trials", 0),
                )
            )
            self.history(run)
            for directory in run.glob("gpu*/search*"):
                if not directory.is_dir():
                    continue
                data = self.finished.get(directory)
                if data is None:
                    data = read_json(directory / "summary.json")
                    if data is not None:
                        self.finished[directory] = data
                    else:
                        data = read_json(directory / "live-progress.json", {})
                if data.get("started_at", 0) < self.started_at:
                    continue
                for name in (
                    "completed_low48_positions",
                    "upper16_trials",
                    "noise_passed",
                    "room_passed",
                    "shortlisted",
                    "gpu_and_transfer_worker_seconds",
                    "reference_worker_seconds",
                ):
                    counts[name] += data.get(name, 0)
                stages.update(data.get("screen_counts", {}))
            for gpu in run.glob("gpu*"):
                if not gpu.is_dir():
                    continue
                jobs = []
                for path in gpu.glob("done*.json"):
                    cache_key = (path, "inverse")
                    if cache_key not in self.finished:
                        self.finished[cache_key] = read_json(path, {})
                    jobs.append(self.finished[cache_key].get("job", {}))
                active = read_json(gpu / "active.json", {})
                if active:
                    jobs.append(active.get("job", {}))
                pending = read_json(gpu / "inverse-progress.json", {})
                if pending:
                    jobs.append(pending)
                seen_jobs = set()
                for job in jobs:
                    epoch = job.get("inverse_started_at", job.get("started_at", 0))
                    if epoch < self.started_at or epoch in seen_jobs:
                        continue
                    seen_jobs.add(epoch)
                    for name in (
                        "inverse_preparation_seconds",
                        "inverse_prepare_wall_seconds",
                        "inverse_calls",
                    ):
                        inverse[name] += job.get(name, 0)
        config = read_json(self.root / "config.json", {})
        return dict(
            started_at=self.started_at,
            session_started_at=self.started_at,
            elapsed_seconds=max(0, now - self.started_at),
            campaign_elapsed_seconds=max(
                0, now - config.get("started_at", self.started_at)
            ),
            seed_position_trials=cumulative_trials,
            campaign_seed_position_trials=cumulative_trials,
            session_seed_position_trials=counts["upper16_trials"],
            completed_low48_hut_positions=counts["completed_low48_positions"],
            campaign_completed_low48_hut_positions=cumulative_trials // 65536,
            noise_passed=counts["noise_passed"],
            room_passed=counts["room_passed"],
            reference_shortlisted=counts["shortlisted"],
            vanilla_candidates_queried=len(self.queried),
            vanilla_candidates_completed=len(self.completed),
            vanilla_verified_candidates=len(self.completed),
            vanilla_confirmed_by_version={
                v: len(keys) for v, keys in self.confirmed.items()
            },
            vanilla_passed_by_version={v: len(keys) for v, keys in self.passed.items()},
            huts_by_height=dict(
                sorted(Counter(str(row[3]) for row in self.heights).items())
            ),
            screen_counts=dict(stages),
            gpu_and_transfer_worker_seconds=counts["gpu_and_transfer_worker_seconds"],
            reference_worker_seconds=counts["reference_worker_seconds"],
            **inverse,
            stage_count_scope="Search batches started since started_at; vanilla counters since started_at; height counts and campaign trials cumulative",
            count_units=dict(
                completed_low48_hut_positions="Structure-seed and candidate-position combinations",
                seed_position_trials="Full-seed and position attempts",
            ),
        )
