"""Compact, append-only public records for a swamp-hut search."""

import datetime
import json
import os
import time
from pathlib import Path


def timestamp(value):
    return datetime.datetime.fromtimestamp(value, datetime.timezone.utc).isoformat(
        timespec="seconds"
    )


class SearchLog:
    """Keep discoveries separate from periodic progress observations."""

    def __init__(self, root, started_at):
        self.root = Path(root)
        self.started_at = started_at
        self.last_progress = -float("inf")
        self.results = self.root / "results.jsonl"
        self.results.touch(exist_ok=True)
        self.seen = set()
        for line in self.results.read_text().splitlines():
            row = json.loads(line)
            self.seen.add(self.key(row))

    @staticmethod
    def key(row):
        return (row["seed"], row["x"], row["z"], row["spawn_y"], tuple(row["versions"]))

    @staticmethod
    def append(path, row):
        with path.open("a") as stream:
            stream.write(
                json.dumps(row, ensure_ascii=True, separators=(",", ":")) + "\n"
            )
            stream.flush()
            os.fsync(stream.fileno())

    def discovery(self, row):
        record = dict(
            time=timestamp(row["verified_at"]),
            seed=str(row["seed"]),
            x=row["x"],
            z=row["z"],
            spawn_y=row["HPos"],
            excavation=row.get("excavation"),
            versions=row["versions"],
            elapsed_seconds=round(row["verified_at"] - self.started_at),
            seed_position_trials=row["campaign_trials_observed_at_verification"],
        )
        key = self.key(record)
        if key not in self.seen:
            self.append(self.results, record)
            self.seen.add(key)

    def progress(
        self,
        trials,
        verified,
        pending,
        running_gpus,
        status="running",
        force=False,
        trials_per_second=None,
    ):
        now = time.time()
        if not force and now - self.last_progress < 30:
            return
        elapsed = max(0, now - self.started_at)
        self.append(
            self.root / "progress.jsonl",
            dict(
                time=timestamp(now),
                status=status,
                elapsed_seconds=round(elapsed),
                seed_position_trials=trials,
                trials_per_second=round(
                    trials / max(1, elapsed)
                    if trials_per_second is None
                    else trials_per_second
                ),
                verified_candidates=verified,
                pending_candidates=pending,
                low_huts=len(self.seen),
                running_gpus=running_gpus,
            ),
        )
        self.last_progress = now
