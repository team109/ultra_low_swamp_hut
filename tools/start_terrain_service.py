"""Start the dedicated in-memory vanilla generation service."""

import argparse
import json
import os
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mcsearch.hut_versions import resolve


def start(version, output, java="java", exact=False):
    cfg = resolve(version)
    v = cfg["requested_version"] if exact else cfg["representative"]
    prepared = ROOT / "runs/versions" / v
    jar = ROOT / "runs/query-service-build/query-service.jar"
    if not jar.exists():
        raise RuntimeError("Prepare this version with tools/prepare_terrain_service.py")
    with zipfile.ZipFile(jar) as archive:
        adapters = json.loads(archive.read("META-INF/query-versions.json"))
    if v not in adapters:
        raise RuntimeError(
            "Prepare the requested version with tools/prepare_terrain_service.py"
        )
    out = Path(output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    java = str(Path(java).resolve()) if os.sep in java else java
    command = [
        java,
        "-XX:ActiveProcessorCount=2",
        "-Xmx3G",
        "-javaagent:" + str(jar),
        "-Dhut.service.root=" + str(out),
        "-Dhut.service.version=" + v,
        "-cp",
        str(jar) + os.pathsep + (prepared / "classpath.txt").read_text(),
        "QueryServiceLauncher",
    ]
    with (out / "server.log").open("w") as log:
        process = subprocess.Popen(
            command,
            cwd=out,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    record = dict(
        pid=process.pid,
        version=v,
        requested_version=version,
        interval=cfg["id"],
        started=time.time(),
        command=command,
        engine="vanilla-memory-generation",
    )
    (out / "process.json").write_text(json.dumps(record, indent=2) + "\n")
    return process, record


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--version", required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--java", default="java")
    p.add_argument("--exact", action="store_true")
    p.add_argument("--accept-eula", action="store_true")
    a = p.parse_args()
    if not a.accept_eula:
        p.error("Read the Minecraft EULA and supply --accept-eula")
    _, record = start(a.version, a.output, a.java, a.exact)
    print(json.dumps(record))


if __name__ == "__main__":
    main()
