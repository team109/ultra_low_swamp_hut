"""Enumerate natural mineshaft constructor states and save potential -59 layouts."""

import argparse
import concurrent.futures
import ctypes as C
import json
from pathlib import Path
import subprocess
import time

from ultra_low_hut.layouts.catalog import LayoutCandidate, template

from ultra_low_hut import ROOT
STATE_COUNT = 1125902188544
BATCH_SIZE = 1 << 22
QUALIFICATION_BATCH = 262144


def atomic_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def build(directory, nvcc, architecture):
    directory.mkdir(parents=True, exist_ok=True)
    for name in ["layout_seed_enumerator", "layout_candidates"]:
        subprocess.run(
            [
                nvcc,
                "-O3",
                "-std=c++17",
                "-arch=" + architecture,
                "--fmad=false",
                "-DMINE26_CAP=1024",
                "-Xcompiler=-fPIC",
                "-shared",
                "-I",
                str(ROOT / "src/ultra_low_hut/layouts"),
                str(ROOT / "src/ultra_low_hut/layouts" / (name + ".cu")),
                "-o",
                str(directory / (name + ".so")),
            ],
            check=True,
        )


def enumerate_shard(device, slot, shards, directory, libraries):
    start, end = STATE_COUNT * slot // shards, STATE_COUNT * (slot + 1) // shards
    checkpoint = directory / f"device-{device}.json"
    records = directory / f"device-{device}.jsonl"
    state = (
        json.loads(checkpoint.read_text())
        if checkpoint.exists()
        else dict(
            device=device,
            start=start,
            end=end,
            next_index=start,
            candidate_bytes=0,
            candidates=0,
            capacity_overflows=0,
        )
    )
    if (state["start"], state["end"]) != (start, end):
        raise ValueError("Saved enumeration uses different device shards")
    records.touch(exist_ok=True)
    with records.open("r+b") as stream:
        stream.truncate(state["candidate_bytes"])
    scanner = C.CDLL(str(libraries / "layout_seed_enumerator.so"))
    qualifier = C.CDLL(str(libraries / "layout_candidates.so"))
    scanner.scan_open.argtypes = [C.c_int, C.c_uint32, C.c_void_p]
    scanner.scan_step.argtypes = [
        C.c_void_p,
        C.c_uint64,
        C.c_uint32,
        C.c_int,
        C.c_void_p,
        C.c_void_p,
    ]
    scanner.scan_close.argtypes = [C.c_void_p]
    qualifier.qualify_layout_targets.argtypes = [
        C.c_int,
        C.c_void_p,
        C.c_int,
        C.c_int,
        C.c_int,
        C.c_void_p,
        C.c_int,
        C.c_void_p,
    ]
    qualifier.release_layout_qualification.argtypes = [C.c_int]
    handle = C.c_void_p()
    status = scanner.scan_open(device, BATCH_SIZE, C.byref(handle))
    if status:
        raise RuntimeError(f"CUDA scanner initialization failed: {status}")
    inputs = (C.c_uint64 * BATCH_SIZE)()
    found = C.c_uint32()
    candidates = (LayoutCandidate * QUALIFICATION_BATCH)()
    counts = (C.c_int * 4)()
    try:
        with records.open("a") as stream:
            while state["next_index"] < end:
                begin = state["next_index"]
                amount = min(BATCH_SIZE, end - begin)
                status = scanner.scan_step(
                    handle, begin, amount, 0, inputs, C.byref(found)
                )
                if status:
                    raise RuntimeError(f"CUDA enumeration failed: {status}")
                for offset in range(0, found.value, QUALIFICATION_BATCH):
                    size = min(QUALIFICATION_BATCH, found.value - offset)
                    status = qualifier.qualify_layout_targets(
                        device,
                        C.byref(inputs, offset * 8),
                        size,
                        315,
                        -1000000,
                        candidates,
                        len(candidates),
                        counts,
                    )
                    if status:
                        raise RuntimeError(
                            f"CUDA layout qualification failed: {status}"
                        )
                    if counts[3]:
                        raise RuntimeError(
                            "Layout capacity exceeded; increase MINE26_CAP and resume"
                        )
                    for index in range(counts[2]):
                        row = template(candidates[index], "exhaustive-natural-height")
                        stream.write(json.dumps(row) + "\n")
                    state["candidates"] += counts[2]
                stream.flush()
                state.update(
                    next_index=begin + amount,
                    candidate_bytes=stream.tell(),
                    updated_at=time.time(),
                )
                atomic_json(checkpoint, state)
        state["complete"] = True
        atomic_json(checkpoint, state)
    finally:
        scanner.scan_close(handle)
        qualifier.release_layout_qualification(device)
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--devices", default="0,1,2,3,4,5,6,7")
    parser.add_argument("--nvcc", default="nvcc")
    parser.add_argument(
        "--build-directory", type=Path, default=ROOT / "build/layout-enumeration"
    )
    parser.add_argument("--arch", default="sm_80")
    args = parser.parse_args()
    devices = list(map(int, args.devices.split(",")))
    if not devices or len(devices) != len(set(devices)):
        parser.error("GPU IDs must be nonempty and distinct")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    directory = args.output.parent / "enumeration"
    directory.mkdir(exist_ok=True)
    build(args.build_directory.resolve(), args.nvcc, args.arch)
    with concurrent.futures.ProcessPoolExecutor(max_workers=len(devices)) as pool:
        futures = [
            pool.submit(
                enumerate_shard,
                device,
                slot,
                len(devices),
                directory,
                args.build_directory.resolve(),
            )
            for slot, device in enumerate(devices)
        ]
        started = time.monotonic()
        while not all(future.done() for future in futures):
            concurrent.futures.wait(futures, timeout=5)
            states = [
                json.loads(path.read_text()) for path in directory.glob("device-*.json")
            ]
            visited = sum(state["next_index"] - state["start"] for state in states)
            elapsed = time.monotonic() - started
            atomic_json(
                directory / "progress.json",
                dict(
                    states=visited,
                    total_states=STATE_COUNT,
                    layouts=sum(state["candidates"] for state in states),
                    elapsed_seconds=round(elapsed, 1),
                ),
            )
        paths = [future.result() for future in futures]
    rows = {}
    for path in paths:
        for line in path.read_text().splitlines():
            row = json.loads(line)
            rows[row["target"]] = row
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text("".join(json.dumps(row) + "\n" for row in rows.values()))
    temporary.replace(args.output)
    atomic_json(
        directory / "complete.json", dict(states=STATE_COUNT, layouts=len(rows))
    )


if __name__ == "__main__":
    main()
