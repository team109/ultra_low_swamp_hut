"""Counters and progress journals for persistent GPU screening."""

import json
import time


class SearchProgress:
    """Cumulative observations consumed by this search process."""

    def __init__(self):
        self.started_at = time.time()
        self.started_clock = time.perf_counter()
        self.values = dict(
            layouts=0,
            upper16_trials=0,
            noise_candidates=0,
            room_rejected=0,
            shortlisted=0,
            gpu_and_transfer_worker_seconds=0.0,
            reference_worker_seconds=0.0,
            screen_counts={},
            room_gate_stages={},
        )

    def add(self, row, low):
        v = self.values
        v["layouts"] += 1
        for field in ("noise_candidates", "room_rejected"):
            v[field] += row[field]
        v["shortlisted"] += len(low)
        v["gpu_and_transfer_worker_seconds"] += row["gpu_and_transfer_seconds"]
        v["reference_worker_seconds"] += row["reference_seconds"]
        for screen in row["screens"]:
            for stage, count in screen["counts"].items():
                v["screen_counts"][stage] = v["screen_counts"].get(stage, 0) + count
            v["upper16_trials"] += screen["counts"]["upper16"]
        for stage, count in row["room_gate_stages"].items():
            v["room_gate_stages"][stage] = v["room_gate_stages"].get(stage, 0) + count

    def snapshot(self, status, errors):
        return dict(
            self.values,
            schema_version=1,
            started_at=self.started_at,
            updated_at=time.time(),
            status=status,
            completed_low48_positions=self.values["layouts"],
            noise_passed=self.values["noise_candidates"],
            room_passed=self.values["noise_candidates"] - self.values["room_rejected"],
            wall_seconds=time.perf_counter() - self.started_clock,
            errors=errors,
        )


def write_progress_atomic(path, report):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, indent=2))
    temporary.replace(path)
