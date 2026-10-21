"""Create a source-only archive from the audited working tree; never commit or push."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import tarfile
from audit_release import ROOT, audit


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--output", type=Path, default=ROOT / "dist/ultra-low-hut-source.tar.gz"
    )
    args = p.parse_args()
    output = args.output.resolve()
    if output.is_relative_to(ROOT) and output.relative_to(ROOT).parts[0] not in (
        "dist",
        "runs",
    ):
        p.error("Place generated archives in dist/, runs/, or outside the source tree")
    report = audit()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    with temporary.open("wb") as raw, gzip.GzipFile(
        filename="", mode="wb", fileobj=raw, mtime=0
    ) as compressed, tarfile.open(fileobj=compressed, mode="w") as archive:
        for row in report["inventory"]:
            path = ROOT / row["path"]
            if hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]:
                raise RuntimeError("Source changed during packaging: " + row["path"])
            info = archive.gettarinfo(str(path), arcname="ultra-low-hut/" + row["path"])
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mtime = (
                315532800  # 1980-01-01, also valid when sources are packed into JARs.
            )
            with path.open("rb") as stream:
                archive.addfile(info, stream)
    temporary.replace(output)
    summary = dict(
        files=report["files"], sha256=hashlib.sha256(output.read_bytes()).hexdigest()
    )
    output.with_suffix(output.suffix + ".json").write_text(
        json.dumps(summary, indent=2) + "\n"
    )
    (output.parent / "SHA256SUMS").write_text(
        summary["sha256"] + "  " + output.name + "\n"
    )
    print(json.dumps(dict(archive=str(output), **summary)))


if __name__ == "__main__":
    main()
