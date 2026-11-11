"""Export verified low huts as JSON or append-only JSONL."""

import argparse
import json
import os
from pathlib import Path
import time
import sys

from ultra_low_hut.verification.loading_orders import LOADING_FIELDS, normalize_verification_mode
from ultra_low_hut.world_types import config_world


def result_key(row):
    return (row["seed"], *row["coordinates"], row["height"], row["excavation"],
            row.get("world_type", "normal"), row.get("biome"))


def export_results(root, since=0, include_metrics=False):
    source = root / "low-huts.jsonl"
    results = {}
    if not source.exists():
        return []
    config_path = root / "config.json"
    configured_world = config_world(json.loads(config_path.read_text())) if config_path.exists() else dict(world_type="normal")
    with source.open() as stream:
        for line in stream:
            if not line.endswith("\n"):
                break
            row = json.loads(line)
            if normalize_verification_mode(row.get("verification_mode", "on")) == "off":
                continue
            if row.get("verified_at", 0) < since:
                continue
            world = config_world(row) if "world_type" in row else configured_world
            if world != configured_world:
                raise ValueError("Result world configuration differs from its run")
            key = (str(row["seed"]), row["x"], row["z"], row["HPos"], row["excavation"],
                   world["world_type"], world.get("biome"))
            if key not in results:
                results[key] = dict(
                    seed=key[0],
                    coordinates=[key[1], key[2]],
                    height=key[3],
                    excavation=key[4],
                    versions=[],
                    **world,
                )
                if include_metrics:
                    results[key]["verified_at"] = row["verified_at"]
                    results[key]["metrics"] = row["metrics"]
            if "verification_mode" in row:
                results[key]["verification_mode"] = normalize_verification_mode(row["verification_mode"])
            versions = row.get("versions", [row["version"]] if "version" in row else [])
            for field in LOADING_FIELDS:
                if field not in row:
                    continue
                if field in ("loading_order_heights", "min_hpos_approaches"):
                    results[key].setdefault(field, {}).update(row[field])
                elif field == "loading_order_affected":
                    results[key][field] = results[key].get(field, False) or row[field]
                else:
                    results[key][field] = row[field]
            results[key]["versions"] = sorted(
                set(results[key]["versions"]) | set(versions),
                key=lambda version: tuple(map(int, version.split("."))),
            )
    return list(results.values())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--follow", action="store_true")
    parser.add_argument("--format", choices=("json", "jsonl"), default="json")
    parser.add_argument(
        "--since",
        type=float,
        default=0,
        help="Include discoveries verified at or after this Unix timestamp",
    )
    parser.add_argument(
        "--metrics",
        action="store_true",
        help="Include discovery-time timing and screening counters",
    )
    options = parser.parse_args()
    options.output.parent.mkdir(parents=True, exist_ok=True)
    previous = None
    started_at = time.time()
    emitted = set()
    if options.format == "jsonl":
        options.output.touch(exist_ok=True)
        for line in options.output.read_text().splitlines():
            emitted.add(result_key(json.loads(line)))
    try:
        while True:
            results = export_results(options.root, options.since, options.metrics)
            if options.format == "jsonl":
                with options.output.open("a") as stream:
                    for row in results:
                        key = result_key(row)
                        if key not in emitted:
                            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                            stream.flush()
                            os.fsync(stream.fileno())
                            emitted.add(key)
            else:
                payload = json.dumps(results, ensure_ascii=False, indent=2) + "\n"
                if payload != previous:
                    temporary = options.output.with_suffix(
                        options.output.suffix + ".tmp"
                    )
                    temporary.write_text(payload)
                    temporary.replace(options.output)
                    previous = payload
            if not options.follow:
                break
            stopped = options.root / "STOPPED.json"
            if stopped.exists() and stopped.stat().st_mtime >= started_at:
                break
            time.sleep(1)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
