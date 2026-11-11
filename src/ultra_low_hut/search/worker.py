"""Single-GPU inverse mapping and batched upper-16-bit screening."""

import argparse
import ctypes
import json
import signal
import sys
import time
from pathlib import Path

from ultra_low_hut import ROOT as PROJECT_ROOT
from ultra_low_hut.search.gpu.inverse import (
    Template as MineshaftTemplate,
    Mapped as MappedHutCandidate,
)
from ultra_low_hut.layouts.structure_seed import mineshaft_seed


def write_json_atomic(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value))
    temporary.replace(path)


def coordinate_region(x, z):
    def precision(anchor):
        magnitude = anchor if anchor >= 0 else -anchor - 1
        return 0 if magnitude < (1 << 23) else 1 if magnitude < (1 << 24) else 2

    return precision(x) * 3 + precision(z)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--device", type=int, required=True)
    options = parser.parse_args()
    config = json.loads((options.root / "config.json").read_text())
    policy = config["qualified_search"]
    worker_index = config["devices"].index(options.device)
    worker_count = len(config["devices"])
    build_dir = PROJECT_ROOT / config["build_dir"]
    output_dir = options.root / f"gpu{options.device}"
    output_dir.mkdir(exist_ok=True)
    pipeline = None
    batch_index = 0
    state = json.loads((output_dir / "resume-state.json").read_text())
    batch_index = state["next_round"]
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))

    def screen_root_batch(path, job):
        nonlocal batch_index, pipeline
        batch_dir = output_dir / f"search{batch_index:06d}"
        write_json_atomic(
            output_dir / "active.json",
            dict(round=batch_index, geometry=str(path), job=job, started=time.time()),
        )
        run_persistent_batch(path, batch_dir, job)
        write_json_atomic(
            output_dir / f"done{batch_index:06d}.json",
            dict(
                job=job,
                finished=time.time(),
                summary=json.loads((batch_dir / "summary.json").read_text()),
            ),
        )
        path.unlink(missing_ok=True)
        batch_index += 1

    def run_persistent_batch(path, batch_dir, job):
        nonlocal pipeline
        if pipeline is None:
            from ultra_low_hut.search.pipeline import ScreeningPipeline

            sampler = None
            if policy.get("terrain_sampling"):
                from ultra_low_hut.layouts.terrain_samples import NaturalTerrainSampler

                sampling = policy["terrain_sampling"]
                sampler = NaturalTerrainSampler(
                    options.root / sampling["directory"] / f"gpu{options.device}",
                    config["version"],
                    sampling["raw_height_max"],
                    sampling["trials_per_gpu"],
                )
            pipeline = ScreeningPipeline(
                options.device,
                config["version"],
                policy["room_budget"],
                build_dir / "libnoise.so",
                PROJECT_ROOT / config.get("cpu_library", "build-cpu-worlds/libmcsearch.so" if (PROJECT_ROOT / "build-cpu-worlds/libmcsearch.so").exists() else "build-cpu/libmcsearch.so"),
                policy["upper16_batch"],
                terrain_sampler=sampler,
                world_type=config.get("world_type", "normal"),
                biome=config.get("biome"),
            )
        pipeline.run_job(path, batch_dir, job.get("resume_skip"))

    try:
        if state.get("unfinished"):
            screen_root_batch(
                Path(state["unfinished"]["geometry"]), state["unfinished"]["job"]
            )
        template_config = policy["template"]
        templates = (MineshaftTemplate * 1)(
            MineshaftTemplate(
                int(template_config["original"]),
                int(template_config["target"]),
                *[
                    template_config[s]
                    for s in [
                        "relx",
                        "relz",
                        "width",
                        "g53",
                        "g54",
                        "covered",
                        "pieces",
                    ]
                ],
            )
        )
        inverse_library = ctypes.CDLL(str(build_dir / "libqualified.so"))
        if "coordinate_regions_mask" in template_config:
            region_masks = (ctypes.c_uint16 * 1)(
                template_config["coordinate_regions_mask"]
            )
            set_regions = inverse_library.mine_set_coordinate_regions
            set_regions.argtypes = [
                ctypes.c_int,
                ctypes.c_void_p,
                ctypes.c_int,
                ctypes.c_void_p,
            ]
            set_regions.restype = ctypes.c_int
            status = set_regions(options.device, templates, 1, region_masks)
            if status:
                raise RuntimeError(f"Coordinate-region configuration failed: {status}")
        map_candidate_ranges = inverse_library.mine_map_hutfirst_strided
        map_candidate_ranges.argtypes = [
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_uint64,
            ctypes.c_uint64,
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_uint64,
            ctypes.c_int,
        ]
        map_candidate_ranges.restype = ctypes.c_int
        count_inverse_cases = inverse_library.mine_general_cases
        count_inverse_cases.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
        ]
        count_inverse_cases.restype = ctypes.c_uint64
        mapped_buffer = (MappedHutCandidate * 131072)()
        mapped_count = ctypes.c_int()
        cases_per_range = policy["inverse_chunk"]
        for coordinate_shift in range(state["resume_k"], policy["last_k"] - 1, -1):
            radius = (policy["world_limit"] // 16) // (1 << coordinate_shift)
            total = count_inverse_cases(templates, 1, coordinate_shift, radius)
            candidate_roots = []
            reserved_ranges = []
            begin = (
                state["resume_begin"]
                if coordinate_shift == state["resume_k"]
                else worker_index * cases_per_range
            )
            last_progress = 0.0
            preparation_started_at = time.time()
            preparation_started_clock = time.perf_counter()
            inverse_seconds = 0.0
            inverse_calls = 0

            def inverse_metrics():
                return dict(
                    started_at=preparation_started_at,
                    inverse_started_at=preparation_started_at,
                    inverse_preparation_seconds=inverse_seconds,
                    inverse_prepare_wall_seconds=time.perf_counter()
                    - preparation_started_clock,
                    inverse_calls=inverse_calls,
                    generated_roots=len(candidate_roots),
                    total_cases=total,
                    coordinate_radius=radius,
                    worker_stride=worker_count * cases_per_range,
                )

            while begin < total:
                range_count = min(
                    policy["ranges_per_call"],
                    max(
                        0,
                        1
                        + (total - cases_per_range - begin)
                        // (worker_count * cases_per_range),
                    ),
                )
                range_count = max(1, range_count)
                range_size = min(cases_per_range, total - begin)
                mapping_started_at = time.perf_counter()
                exit_code = map_candidate_ranges(
                    options.device,
                    templates,
                    1,
                    coordinate_shift,
                    radius,
                    begin,
                    range_size,
                    mapped_buffer,
                    len(mapped_buffer),
                    ctypes.byref(mapped_count),
                    worker_count * cases_per_range,
                    range_count,
                )
                mapping_seconds = time.perf_counter() - mapping_started_at
                inverse_seconds += mapping_seconds
                inverse_calls += 1
                if exit_code:
                    raise RuntimeError(
                        f"Mineshaft inversion failed: CUDA status {exit_code}"
                    )
                mapped_candidates = mapped_buffer[: mapped_count.value]
                for mapped_candidate in mapped_candidates[:3]:
                    assert mineshaft_seed(
                        mapped_candidate.seed, mapped_candidate.cx, mapped_candidate.cz
                    ) == int(template_config["target"])
                for mapped_candidate in mapped_candidates:
                    region = coordinate_region(mapped_candidate.x, mapped_candidate.z)
                    coordinate_metrics = template_config.get(
                        "coordinate_metrics", {}
                    ).get(str(region), {})
                    root = dict(
                        low48=str(mapped_candidate.seed),
                        mineChunkX=mapped_candidate.cx,
                        mineChunkZ=mapped_candidate.cz,
                        template=template_config,
                        geometryOnly=True,
                        pieceCount=mapped_candidate.pieces,
                        hutCandidates=[
                            dict(
                                hutChunkX=mapped_candidate.x // 16,
                                hutChunkZ=mapped_candidate.z // 16,
                                width=mapped_candidate.width,
                                depth=63 // mapped_candidate.width,
                                optimisticGainFromMinus53=coordinate_metrics.get(
                                    "g53", mapped_candidate.g53
                                ),
                                optimisticGainFromMinus54=coordinate_metrics.get(
                                    "g54", mapped_candidate.g54
                                ),
                                coveredColumns=coordinate_metrics.get(
                                    "covered", mapped_candidate.covered
                                ),
                            )
                        ],
                    )
                    candidate_roots.append(root)
                reserved_ranges.extend(
                    [
                        [begin + j * worker_count * cases_per_range, range_size]
                        for j in range(range_count)
                    ]
                )
                if (
                    time.monotonic() - last_progress >= 1
                    or len(candidate_roots) >= policy["roots_per_batch"]
                ):
                    write_json_atomic(
                        output_dir / "inverse-progress.json",
                        dict(
                            **inverse_metrics(),
                            k=coordinate_shift,
                            total=total,
                            last_begin=begin
                            + (range_count - 1) * worker_count * cases_per_range,
                            last_cases=range_size,
                            merged_ranges=range_count,
                            mapped_buffer=len(candidate_roots),
                            last_seconds=time.perf_counter() - mapping_started_at,
                            last_mapping_seconds=mapping_seconds,
                            updated=time.time(),
                            updated_at=time.time(),
                        ),
                    )
                    last_progress = time.monotonic()
                begin += range_count * worker_count * cases_per_range
                if len(candidate_roots) >= policy["roots_per_batch"]:
                    path = output_dir / f"geometry{batch_index:06d}.json"
                    write_json_atomic(path, candidate_roots)
                    screen_root_batch(
                        path,
                        dict(
                            **inverse_metrics(),
                            type="inverse",
                            k=coordinate_shift,
                            ranges=reserved_ranges,
                        ),
                    )
                    candidate_roots = []
                    reserved_ranges = []
                    preparation_started_at = time.time()
                    preparation_started_clock = time.perf_counter()
                    inverse_seconds = 0.0
                    inverse_calls = 0
            if candidate_roots:
                path = output_dir / f"geometry{batch_index:06d}.json"
                write_json_atomic(path, candidate_roots)
                screen_root_batch(
                    path,
                    dict(
                        **inverse_metrics(),
                        type="inverse",
                        k=coordinate_shift,
                        ranges=reserved_ranges,
                    ),
                )
        write_json_atomic(output_dir / "EXHAUSTED.json", dict(at=time.time()))
    finally:
        if pipeline:
            pipeline.close()
        write_json_atomic(
            output_dir / "STOPPED.json",
            dict(at=time.time(), completed_rounds=batch_index),
        )


if __name__ == "__main__":
    main()
