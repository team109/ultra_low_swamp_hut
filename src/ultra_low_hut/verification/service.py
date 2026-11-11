"""Start the dedicated in-memory vanilla generation service."""

import argparse
import json
import os
import subprocess
import sys
import time
import zipfile
from pathlib import Path

from ultra_low_hut import ROOT
from ultra_low_hut.versions import resolve
from ultra_low_hut.verification.classpath import prepared_classpath
from ultra_low_hut.verification.loading_orders import FEATURES_POLICY, LOADING_POLICY


def start_single(version, output, java="java", exact=False, *, generation_mode="features", jar=None):
    if generation_mode not in ("full", "features"):
        raise ValueError("generation_mode must be full or features")
    cfg = resolve(version)
    v = cfg["requested_version"] if exact else cfg["representative"]
    prepared = ROOT / "runs/versions" / v
    jar = Path(jar).resolve() if jar is not None else ROOT / "runs/query-service-build/query-service.jar"
    if not jar.exists():
        raise RuntimeError("Prepare this version with scripts/verification/prepare.py")
    with zipfile.ZipFile(jar) as archive:
        adapters = json.loads(archive.read("META-INF/query-versions.json"))
    if v not in adapters:
        raise RuntimeError(
            "Prepare the requested version with scripts/verification/prepare.py"
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
        "-Dhut.service.generationMode=" + generation_mode,
        "-Dhut.service.loadingPolicy=" + (FEATURES_POLICY if generation_mode == "features" else LOADING_POLICY),
        "-cp",
        str(jar) + os.pathsep + prepared_classpath(prepared),
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
        generation_mode=generation_mode,
    )
    (out / "process.json").write_text(json.dumps(record, indent=2) + "\n")
    return process, record


def start(version, output, java="java", exact=False, workers=4, *, generation_mode="features", jar=None):
    if workers < 1:
        raise ValueError("--workers must be positive")
    cfg = resolve(version)
    out = Path(output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    java = str(Path(java).resolve()) if os.sep in java else java
    command = [sys.executable, str(ROOT / "scripts/verification/pool.py"),
               "--version", version, "--output", str(out), "--java", java,
               "--workers", str(workers), "--generation-mode", generation_mode]
    if jar is not None:
        command.extend(["--jar", str(Path(jar).resolve())])
    if exact:
        command.append("--exact")
    with (out / "server.log").open("w") as log:
        process = subprocess.Popen(command, cwd=out, stdin=subprocess.DEVNULL,
                                   stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    record = dict(pid=process.pid, version=cfg["requested_version"] if exact else cfg["representative"],
                  requested_version=version, interval=cfg["id"], started=time.time(),
                  command=command, workers=workers, engine="vanilla-memory-generation", generation_mode=generation_mode)
    (out / "process.json").write_text(json.dumps(record, indent=2) + "\n")
    return process, record


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--version", required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--java", default="java")
    p.add_argument("--exact", action="store_true")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--generation-mode", choices=("full", "features"), default="features")
    p.add_argument("--jar", type=Path)
    p.add_argument("--accept-eula", action="store_true")
    a = p.parse_args()
    if not a.accept_eula:
        p.error("Read the Minecraft EULA and supply --accept-eula")
    from ultra_low_hut.verification.artifacts import prepare
    prepare(a.version, a.java, a.exact, artifacts_only=a.jar is not None)
    _, record = start(a.version, a.output, a.java, a.exact, a.workers, generation_mode=a.generation_mode, jar=a.jar)
    print(json.dumps(record))


if __name__ == "__main__":
    main()
