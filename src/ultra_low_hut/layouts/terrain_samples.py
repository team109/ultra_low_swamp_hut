"""Collect a fixed budget of terrain observations before layout filtering."""

import json
from pathlib import Path
import time


class NaturalTerrainSampler:
    def __init__(self, directory, version, max_y, trials):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.version, self.max_y, self.budget = version, max_y, trials
        if trials % 65536:
            raise ValueError("Terrain sampling uses complete upper-16-bit batches")
        self.manifest = self.directory / "jobs.json"
        self.jobs = (
            json.loads(self.manifest.read_text()) if self.manifest.exists() else []
        )
        self.trials = 0
        recovered = {}
        for job in self.jobs:
            journal = Path(job) / "completed.jsonl"
            if not journal.exists():
                continue
            with journal.open("rb") as stream:
                for line in stream:
                    if not line.endswith(b"\n"):
                        break
                    self.trials = min(self.budget, self.trials + 65536)
                    if b'"natural_samples"' in line:
                        for row in json.loads(line)["natural_samples"]:
                            recovered[row["seed"], row["x"], row["z"]] = row
        self.seen = set(recovered)
        self.stream = (self.directory / "samples.jsonl").open("w")
        for row in recovered.values():
            self.stream.write(json.dumps(row) + "\n")
        self.stream.flush()
        self.last_progress = 0.0
        self.progress()

    def register_job(self, output):
        path = str(Path(output).resolve())
        if self.trials < self.budget and path not in self.jobs:
            self.jobs.append(path)
            temporary = self.manifest.with_suffix(".tmp")
            temporary.write_text(json.dumps(self.jobs) + "\n")
            temporary.replace(self.manifest)

    def start_root(self):
        if self.trials >= self.budget:
            return False
        self.trials += 65536
        return True

    def observe(self, context, candidate):
        reference = context.screen_hut(candidate["x"], candidate["z"], self.max_y)
        if reference["accepted"]:
            return dict(
                seed=candidate["seed"],
                x=candidate["x"],
                z=candidate["z"],
                raw_y=reference["y"],
                version=self.version,
            )

    def commit(self, records):
        for row in records:
            key = row["seed"], row["x"], row["z"]
            if key not in self.seen:
                self.seen.add(key)
                self.stream.write(json.dumps(row) + "\n")
        if records:
            self.stream.flush()
        if time.monotonic() - self.last_progress >= 30:
            self.progress()

    def progress(self):
        temporary = self.directory / "progress.tmp"
        temporary.write_text(
            json.dumps(
                dict(
                    status="completed" if self.trials >= self.budget else "collecting",
                    seed_position_trials=self.trials,
                    trial_budget=self.budget,
                    terrain_samples=len(self.seen),
                    raw_height_max=self.max_y,
                ),
                indent=2,
            )
            + "\n"
        )
        temporary.replace(self.directory / "progress.json")
        self.last_progress = time.monotonic()

    def close(self):
        self.stream.close()
        self.progress()
