"""Build the GPU inversion and terrain-screening libraries for a game version."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mcsearch.hut_versions import catalog, resolve_hunt

NOISE_MACROS = {
    "erosion_min": "EROSION_MIN",
    "temperature_min": "TEMPERATURE_MIN",
    "temperature_max": "TEMPERATURE_MAX",
    "continentalness_min": "CONTINENTALNESS_MIN",
    "ridge_abs_max": "RIDGE_ABS_MAX",
    "ridge_outer_min": "RIDGE_OUTER_MIN",
    "ridge_outer_absolute": "RIDGE_ABSOLUTE",
    "surface_depth_min": "SURFACE_DEPTH_MIN",
    "floodedness_max": "FLOODEDNESS_MAX",
    "entrance_max": "ENTRANCE_MAX",
    "cheese_max": "CHEESE_MAX",
}
SOURCES = {
    "noise_cascade26.cu": "libnoise.so",
    "mine_inverse_qualified.cu": "libqualified.so",
}


def profile_header(config, policy):
    screen = config["screen"]
    terrain = config["coordinate_layouts"]
    flags = ["NC_SURFACE_GATE", "NC_FIXED_SEED", "NC_REUSE_WORKSPACE"]
    for key, macro in {
        "interval_erosion": "NC_INTERVAL_EROSION",
        "coordinate_erosion_bounds": "NC_COORDINATE_EROSION_BOUNDS",
        "compact_temperature": "NC_COMPACT_TEMPERATURE",
        "shared_permutations": "NC_SHARED_PERMUTATIONS",
    }.items():
        if terrain.get(key):
            flags.append(macro)
    values = {
        "HUT_SALT": str(screen["hut_salt"]) + "ULL",
        "HUT_SPACING": screen["hut_spacing_chunks"],
        "HUT_SEPARATION": screen["hut_separation_chunks"],
        "HUNT_ROOM_MAX_Y": screen["room_y_max"],
        "ANISO_X_MIN": policy["x_min"],
        "ANISO_X_MAX": policy["x_max"],
    }
    if "unshifted_erosion_min" in terrain:
        flags.append("NC_FAST_ER")
        values["NC_FAST_ER_MIN"] = terrain["unshifted_erosion_min"]
    octaves = terrain.get("unshifted_erosion_octaves")
    if octaves is not None:
        if not 1 <= octaves <= 8:
            raise ValueError("unshifted_erosion_octaves must be in 1..8")
        values["NC_FAST_ER_PREFIX_OCTAVES"] = octaves
    if terrain.get("compact_erosion_threads"):
        flags.append("NC_COMPACT_FAST_ER")
        values["NC_THREADS"] = terrain["compact_erosion_threads"]
    trial = screen.get("trial_placement")
    if trial and terrain.get("trial_exclusion_l1_radius"):
        values.update(
            {
                "HUNT_TRIAL_L1_RADIUS": terrain["trial_exclusion_l1_radius"],
                "HUNT_TRIAL_SALT": str(trial["salt"]) + "ULL",
                "HUNT_TRIAL_SPACING": trial["spacing"],
                "HUNT_TRIAL_SPREAD": trial["spacing"] - trial["separation"],
                "HUNT_TRIAL_HEIGHT_SPAN": trial["start_height_span"],
                "HUNT_TRIAL_HALF_SIZE": trial["start_half_size"],
            }
        )
    for key, macro in NOISE_MACROS.items():
        value = screen["noise_gates"][key]
        values["NC_" + macro] = int(value) if isinstance(value, bool) else value
    return "".join(f"#define {flag}\n" for flag in flags) + "".join(
        f"#define {name} {value}\n" for name, value in values.items()
    )


def build(version, nvcc, architecture):
    config = resolve_hunt(version, -62, True)
    config["build_profile"] += "-qualified"
    policy = json.loads((ROOT / "data/search/qualified-room.json").read_text())
    config["qualified_search"] = policy
    directory = ROOT / "runs/hut-build" / config["build_profile"]
    directory.mkdir(parents=True, exist_ok=True)
    header = directory / "profile.h"
    text = profile_header(config, policy)
    header.write_text(text)
    source_hash = hashlib.sha256()
    for path in sorted((ROOT / "native").iterdir()):
        if path.suffix in (".cu", ".cuh", ".h"):
            source_hash.update(path.name.encode())
            source_hash.update(path.read_bytes())
    source_digest = source_hash.hexdigest()
    compiler = subprocess.check_output([nvcc, "--version"], text=True)
    key = hashlib.sha256(
        (text + architecture + compiler + source_digest).encode()
    ).hexdigest()
    cache = ROOT / "runs/hut-build/cache" / key
    cache.mkdir(parents=True, exist_ok=True)
    for source, name in SOURCES.items():
        artifact = cache / name
        if not artifact.exists():
            temporary = cache / (name + ".tmp")
            subprocess.run(
                [
                    nvcc,
                    "-O3",
                    "-std=c++17",
                    "-arch=" + architecture,
                    "--fmad=false",
                    "-include",
                    str(header),
                    "-Xcompiler",
                    "-fPIC",
                    "-shared",
                    str(ROOT / "native" / source),
                    "-o",
                    str(temporary),
                ],
                check=True,
            )
            temporary.replace(artifact)
        pending = directory / (name + ".tmp")
        shutil.copyfile(artifact, pending)
        pending.replace(directory / name)
    config["build"] = dict(
        arch=architecture,
        source_sha256=source_digest,
        cache_key=key,
        sha256={
            name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
            for name in [*SOURCES.values(), "profile.h"]
        },
    )
    (directory / "config.json").write_text(json.dumps(config, indent=2) + "\n")
    print(
        json.dumps(dict(interval=config["id"], build=str(directory.relative_to(ROOT))))
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--version")
    selection.add_argument("--all", action="store_true")
    parser.add_argument("--nvcc", default="nvcc")
    parser.add_argument("--arch", default="sm_80")
    options = parser.parse_args()
    versions = (
        [row["representative"] for row in catalog()["intervals"]]
        if options.all
        else [options.version]
    )
    for version in versions:
        build(version, options.nvcc, options.arch)


if __name__ == "__main__":
    main()
