"""Compare layouts on a shared natural-terrain panel with a fixed replay budget."""

import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import sys
import threading
import time

from ultra_low_hut.layouts.placement import PlacementWorker, read_layouts, write_json

from ultra_low_hut import ROOT
from ultra_low_hut.search.reference.native import Context
from ultra_low_hut.layouts.bindings import room_geometry, mineshaft_clearing_masks


def occupied_columns(snapshot, width):
    raw = Path(snapshot).read_bytes()
    if len(raw) != 16 * 16 * 384:
        raise ValueError("Natural snapshots contain 16 by 16 by 384 blocks")
    columns = []
    for column in range(63):
        x, z = column % width, column // width
        data = raw[(z * 16 + x) * 384 : (z * 16 + x + 1) * 384]
        columns.append(sum(1 << y for y, block in enumerate(data) if block))
    return columns


def optimistic_height_sum(occupied, clearing):
    return sum(
        (blocks & ~mask).bit_length() - 64 for blocks, mask in zip(occupied, clearing)
    )


def raw_height_bound(clearing, target=-59):
    maximum_drop = 0
    for mask in clearing:
        lower = -54
        while lower > -64 and mask & (1 << (lower + 63)):
            lower -= 1
        maximum_drop += max(0, mask.bit_length() - 64 - lower)
    return int((target * 63 + maximum_drop) / 63)


def measure(
    layouts, panel_path, output, configuration, java="java", draws=256, workers=4
):
    output = output.resolve()
    panel = json.loads(panel_path.read_text())
    metadata = json.loads(panel_path.with_name("configuration.json").read_text())
    screened_cells = set(metadata.get("screened_cells", []))
    trials = metadata["seed_position_trials"]
    if not panel or trials <= 0 or draws <= 0:
        raise ValueError(
            "A natural panel, positive trial count and replay budget are required"
        )
    output.mkdir(parents=True, exist_ok=True)
    # The original biome source accompanies every captured terrain field.
    for row in panel:
        row["natural_biomes"] = True
        snapshot = Path(row["snapshot_file"])
        row["snapshot_file"] = str((panel_path.parent / snapshot).resolve())
    runtime_panel = output / "terrain-panel.json"
    write_json(runtime_panel, panel)
    write_json(output / "configuration.json", metadata)
    cells = []
    occupied = {}
    origins = [0, 12582912, 20000000]
    for layout in layouts:
        for region in range(9):
            if not layout["coordinate_regions_mask"] & (1 << region):
                continue
            origin = [origins[region // 3], origins[region % 3]]
            geometry = room_geometry(
                int(layout["target"]),
                *origin,
                layout["width"],
                layout["relx"],
                layout["relz"],
            )
            masks = mineshaft_clearing_masks(
                int(layout["target"]),
                *origin,
                layout["width"],
                layout["relx"],
                layout["relz"],
            )
            cutoff = raw_height_bound(masks)
            if cutoff > metadata["raw_height_max"]:
                raise ValueError("Panel height range does not cover this layout")
            cells.append(
                (
                    dict(layout, test_origin=origin, test_region=region),
                    geometry,
                    masks,
                    cutoff,
                )
            )
            if layout["width"] not in occupied:
                occupied[layout["width"]] = [
                    (
                        occupied_columns(row["snapshot_file"], layout["width"])
                        if Path(row["snapshot_file"]).exists()
                        else None
                    )
                    for row in panel
                ]
    local = threading.local()
    services = []
    lock = threading.Lock()

    def cell(job):
        layout, geometry, masks, cutoff = job
        counts = [0] * len(panel)
        for i, row in enumerate(panel):
            key = f"{layout['target']}:{layout['test_region']}"
            if key in screened_cells:
                passed = key in row["passing_cells"]
            else:
                with Context(int(row["seed"]), "1.21", -1) as context:
                    passed = context.room_budget(
                        row["x"], row["z"], geometry, metadata["gate_budget"]
                    )["passed"]
            # Skipped cells have exactly zero chance under the measured pipeline
            # or under an optimistic clearing of the full mineshaft footprint.
            if passed and occupied[layout["width"]][i] is None:
                raise ValueError(
                    "A gate-eligible terrain is missing its natural snapshot"
                )
            if (
                passed
                and optimistic_height_sum(occupied[layout["width"]][i], masks)
                <= -59 * 63
            ):
                counts[i] = draws
        probability = 0.0
        positive_fields = placements = hits = 0
        field_hits = []
        for i, n in enumerate(counts):
            if not n:
                continue
            if not hasattr(local, "worker"):
                local.worker = PlacementWorker(
                    configuration, runtime_panel, java, output
                )
                with lock:
                    services.append(local.worker)
            # Matched decoration streams across every layout and precision class.
            seed = int.from_bytes(
                hashlib.sha256(
                    f"natural-layout-yield-v1:{panel[i]['seed']}:{panel[i]['x']}:{panel[i]['z']}".encode()
                ).digest()[:7],
                "little",
            )
            allocation = [0] * len(panel)
            allocation[i] = draws
            request = dict(
                layout=layout,
                region=layout["test_region"],
                counts=allocation,
                n=draws,
                sampling_seed=seed,
            )
            service = local.worker
            service.process.stdin.write(json.dumps(request) + "\n")
            service.process.stdin.flush()
            result = service.receive()
            if result["n"] != draws or result["target"] != layout["target"]:
                raise RuntimeError("Placement response differs from request")
            k = result["hits59"]
            weight = panel[i].get(
                "trial_weight", 1 / panel[i].get("balance_exposure", trials)
            )
            contribution = k / draws * weight
            raw_y = panel[i].get("raw_y", panel[i].get("reference", {}).get("y"))
            if raw_y <= metadata["reference_max_y"]:
                probability += contribution
                hits += k
                positive_fields += k > 0
            placements += draws
            field_hits.append(dict(terrain=panel[i]["id"], hits59=k))
        return dict(
            layout_seed=layout["target"],
            excavation=sum(
                10 - (((1 << 10) - 1) & ~mask).bit_length() for mask in masks
            ),
            expected59_per_trillion_trials=probability * 1e12,
            region=layout["test_region"],
            test_origin=layout["test_origin"],
            natural_terrains=len(panel),
            decoration_draws=draws,
            replayed_placements=placements,
            positive_terrains=positive_fields,
            hits59=hits,
            derived_raw_height_max=cutoff,
            field_hits=field_hits,
        )

    started = time.monotonic()
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            results = list(executor.map(cell, cells))
    finally:
        for service in services:
            service.close()
    results.sort(
        key=lambda row: (
            -row["expected59_per_trillion_trials"],
            -row["excavation"],
            int(row["layout_seed"]),
            row["region"],
        )
    )
    details = output / "details"
    details.mkdir(exist_ok=True)
    with (output / "results.jsonl").open("w") as stream:
        for row in results:
            write_json(details / f"{row['layout_seed']}-{row['region']}.json", row)
            record = {key: value for key, value in row.items() if key != "field_hits"}
            record["expected59_per_trillion_trials"] = round(
                record["expected59_per_trillion_trials"], 6
            )
            stream.write(json.dumps(record) + "\n")
    write_json(
        output / "summary.json",
        dict(
            method="shared-natural-fixed-budget-v1",
            version="1.21",
            terrain_panel="terrain-panel.json",
            terrain_configuration="configuration.json",
            layouts=len(layouts),
            sampling_method=metadata.get("method", "unconditional-fixed-budget"),
            decoration_seed_scheme="sha256(source-seed,x,z)",
            layout_regions=len(results),
            natural_terrains=len(panel),
            seed_position_trials=trials,
            decoration_draws=draws,
            replayed_placements=sum(r["replayed_placements"] for r in results),
            elapsed_seconds=round(time.monotonic() - started, 3),
        ),
    )
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layouts", type=Path, required=True)
    parser.add_argument("--terrain-panel", type=Path, required=True)
    parser.add_argument("--worker-config", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--java", default="java")
    parser.add_argument("--draws", type=int, default=256)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.workers < 1 or args.draws < 1:
        parser.error("--workers and --draws must be positive")
    if args.worker_config:
        configuration = json.loads(args.worker_config.read_text())
    else:
        from ultra_low_hut.layouts.prepare_yield import build

        configuration = build(args.java)
    measure(
        read_layouts(args.layouts),
        args.terrain_panel.resolve(),
        args.output,
        configuration,
        args.java,
        args.draws,
        args.workers,
    )


if __name__ == "__main__":
    main()
