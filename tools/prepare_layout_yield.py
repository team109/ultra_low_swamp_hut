"""Build the vanilla 1.21 controlled layout placement worker."""

import argparse, json, os, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build(java="java"):
    prepared = ROOT / "runs/versions/1.21"
    for name in ["server-mapped.jar", "ecj.jar", "asm.jar"]:
        if not (prepared / name).exists():
            raise FileNotFoundError(
                "Run tools/prepare_version_verifier.py --version 1.21 first"
            )
    from prepare_terrain_service import build as build_service

    service = build_service("1.21", java)
    out = ROOT / "runs/layout-yield-build"
    classes = out / "classes"
    classes.mkdir(parents=True, exist_ok=True)
    cp = os.pathsep.join(
        [
            str(prepared / "server-mapped.jar"),
            *[str(p) for p in sorted((prepared / "libraries").glob("*.jar"))],
            str(prepared / "asm.jar"),
        ]
    )
    source = ROOT / "tools/oracle"
    files = [
        source / n
        for n in [
            "QueryServiceLauncher.java",
            "VersionQueryRuntime.java",
            "VersionQueryAgent.java",
            "VersionQueryObservation.java",
            "query121/VanillaQueryMain.java",
            "NaturalBiomeSampler.java",
            "LayoutPlacementReplay.java",
            "LayoutYieldService.java",
        ]
    ]
    subprocess.run(
        [
            java,
            "-XX:ActiveProcessorCount=2",
            "-jar",
            str(prepared / "ecj.jar"),
            "-21",
            "-cp",
            cp,
            "-d",
            str(classes),
            *map(str, files),
        ],
        check=True,
    )
    # Share the world-generation host with the query service.
    agent = ROOT / service["jar"]
    record = dict(
        classes=str(classes),
        classpath=os.pathsep.join([str(classes), cp]),
        agent=str(agent),
    )
    (out / "worker.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--java", default="java")
    a = p.parse_args()
    print(json.dumps(build(a.java)))
