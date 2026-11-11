"""Rebuild a shared 1.21 natural-terrain panel from its published seed list."""

import argparse
import json
from pathlib import Path
import subprocess

from ultra_low_hut import ROOT
from ultra_low_hut.layouts.placement import write_json


def prepare(panel_path, configuration_path, output, worker, java="java"):
    panel = json.loads(panel_path.read_text())
    configuration = json.loads(configuration_path.read_text())
    if configuration.get("version", "1.21") != "1.21":
        raise ValueError("Terrain snapshot capture supports version 1.21")
    if not panel:
        raise ValueError("The terrain panel must contain samples")
    output = output.resolve()
    capture = []
    for index, row in enumerate(panel):
        if row["x"] % 16 or row["z"] % 16:
            raise ValueError("Terrain snapshot origins must be chunk aligned")
        relative = f"snapshots/{index:04d}.bin"
        row["snapshot_file"] = relative
        capture.append(dict(row, snapshot_file=str(output / relative)))
    existing_panel = output / "panel.json"
    existing_configuration = output / "configuration.json"
    if existing_panel.exists() != existing_configuration.exists():
        raise ValueError("Existing terrain panel and configuration must both be present")
    if existing_panel.exists():
        if (json.loads(existing_panel.read_text()) != panel
                or json.loads(existing_configuration.read_text()) != configuration):
            raise ValueError("Output directory contains a different terrain panel or configuration")
    elif any((output / "snapshots").glob("*.bin")):
        raise ValueError("Existing snapshots require their terrain panel and configuration")
    (output / "snapshots").mkdir(parents=True, exist_ok=True)
    write_json(output / "panel.json", panel)
    write_json(output / "configuration.json", configuration)
    # The runtime list differs only in its absolute snapshot paths.
    runtime = output / "capture-panel.json"
    write_json(runtime, capture)
    subprocess.run(
        [java, "-XX:ActiveProcessorCount=2", "-Xmx2G",
         "-javaagent:" + worker["agent"], "-cp", worker["classpath"],
         "NaturalTerrainSnapshot", str(runtime)],
        check=True, cwd=output,
    )
    return output / "panel.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", type=Path,
                        default=ROOT / "data/mineshafts/yield-panel.json")
    parser.add_argument("--configuration", type=Path,
                        default=ROOT / "data/mineshafts/yield-measurement.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--java", default="java")
    args = parser.parse_args()
    from ultra_low_hut.layouts.prepare_yield import build

    print(prepare(args.panel, args.configuration, args.output, build(args.java), args.java))


if __name__ == "__main__":
    main()
