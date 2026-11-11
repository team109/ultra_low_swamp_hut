"""Build the shared query-service JAR with version-specific hosting adapters."""

import argparse
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

from ultra_low_hut import ROOT
from ultra_low_hut.versions import catalog, resolve
from ultra_low_hut.verification.adapters.query import adapt_query_source
from ultra_low_hut.verification.classpath import prepared_classpath

COMMON_SOURCES = [
    "QueryServiceLauncher.java",
    "VersionQueryRuntime.java",
    "VersionQueryAgent.java",
    "VersionQueryObservation.java",
]


def source_fingerprint():
    digest = hashlib.sha256()
    files = [ROOT / "src/ultra_low_hut/verification/java" / name for name in COMMON_SOURCES]
    files += [ROOT / "src/ultra_low_hut/verification/java/query121/VanillaQueryMain.java",
              ROOT / "src/ultra_low_hut/verification/adapters/query.py"]
    for path in files:
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def compile_adapter(version, java, output):
    fingerprint = source_fingerprint()
    prepared = ROOT / "runs/versions" / version
    adapter = output / "adapters" / version
    adapter.mkdir(parents=True, exist_ok=True)
    source = (ROOT / "src/ultra_low_hut/verification/java/query121/VanillaQueryMain.java").read_text()
    resolve(version)
    source = adapt_query_source(source, version)
    generated = adapter / "VanillaQueryMain.java"
    generated.write_text(source)
    classes = adapter / "classes"
    classes.mkdir(exist_ok=True)
    classpath = (
        prepared_classpath(prepared)
        + os.pathsep
        + str(prepared / "asm.jar")
    )
    subprocess.run(
        [
            java,
            "-XX:ActiveProcessorCount=2",
            "-jar",
            str(prepared / "ecj.jar"),
            "-17",
            "-cp",
            classpath,
            "-d",
            str(classes),
            *[str(ROOT / "src/ultra_low_hut/verification/java" / name) for name in COMMON_SOURCES],
            str(generated),
        ],
        check=True,
    )
    if source_fingerprint() != fingerprint:
        raise RuntimeError("Query-service sources changed during compilation; rebuild")
    (adapter / "build.json").write_text(json.dumps(dict(version=version, source_sha256=fingerprint)) + "\n")
    return classes, prepared / "asm.jar"


def package_service(output, shared_classes, asm_path):
    jar = output / "query-service.jar"
    temporary = output / "query-service.jar.tmp"
    fingerprint = source_fingerprint()
    adapters = sorted(
        path.parent.name
        for path in (output / "adapters").glob("*/classes")
        if (path / "VanillaQueryMain.class").exists()
        and (path.parent / "build.json").exists()
        and json.loads((path.parent / "build.json").read_text()).get("source_sha256") == fingerprint
        and path.parent.name
        in {v for row in catalog()["intervals"] for v in row["versions"]}
    )
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "META-INF/MANIFEST.MF",
            "Manifest-Version: 1.0\nPremain-Class: VersionQueryAgent\nMain-Class: QueryServiceLauncher\n\n",
        )
        archive.write(
            ROOT / "LICENSES/ASM-BSD-3-Clause.txt", "META-INF/LICENSE-ASM.txt"
        )
        archive.write(ROOT / "LICENSE", "META-INF/LICENSE-Ultra-Low-Hut.txt")
        archive.writestr("META-INF/query-versions.json", json.dumps(adapters))
        for prefix in [
            "QueryServiceLauncher",
            "VersionQueryRuntime",
            "VersionQueryAgent",
            "VersionQueryObservation",
        ]:
            for file in sorted(shared_classes.glob(prefix + "*.class")):
                archive.write(file, file.name)
        for version in adapters:
            for file in sorted(
                (output / "adapters" / version / "classes").glob(
                    "VanillaQueryMain*.class"
                )
            ):
                archive.write(file, "adapters/" + version + "/" + file.name)
        with zipfile.ZipFile(asm_path) as asm:
            for name in asm.namelist():
                if name.startswith("org/objectweb/asm/") and name.endswith(".class"):
                    archive.writestr(name, asm.read(name))
    temporary.replace(jar)
    return dict(
        versions=adapters,
        jar=str(jar.relative_to(ROOT)),
        source_sha256=fingerprint,
    )


def build_versions(versions, java="java", output=None):
    output = Path(output) if output is not None else ROOT / "runs/query-service-build"
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    with (output / "build.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        for version in versions:
            shared_classes, asm_path = compile_adapter(version, java, output)
        record = package_service(output, shared_classes, asm_path)
        if not set(versions) <= set(record["versions"]):
            raise RuntimeError("Query-service sources changed between adapters; rebuild all requested versions")
        (output / "build.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


def build(version, java="java", exact=False):
    config = resolve(version)
    selected = config["requested_version"] if exact else config["representative"]
    record = build_versions([selected], java)
    return dict(record, version=selected, interval=config["id"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--version")
    selection.add_argument(
        "--all", action="store_true", help="Bundle all modern verifier representatives"
    )
    parser.add_argument("--java", default="java")
    parser.add_argument("--exact", action="store_true")
    options = parser.parse_args()
    if options.all:
        catalog = json.loads((ROOT / "config/versions/compatibility.json").read_text())
        versions = list(
            dict.fromkeys(
                resolve(v)["representative"] for v in catalog["search_versions"]
            )
        )
        record = build_versions(versions, options.java)
    else:
        record = build(options.version, options.java, options.exact)
    print(json.dumps(record))


if __name__ == "__main__":
    main()
