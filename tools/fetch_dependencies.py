"""Fetch the pinned CPU terrain dependency and verify its build inputs."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
URL = "https://github.com/M33Galaxy/LowYSwampHut.git"
PROXY_KEYS = {
    name
    for kind in ("HTTP", "HTTPS", "ALL", "FTP")
    for name in (kind + "_PROXY", kind.lower() + "_proxy")
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT / "external")
    parser.add_argument("--verify-only", action="store_true")
    options = parser.parse_args()
    lock = json.loads((ROOT / "sources.lock.json").read_text())
    environment = {
        key: value for key, value in os.environ.items() if key not in PROXY_KEYS
    }
    if not options.verify_only:
        target = options.root / "LowYSwampHut"
        revision = lock["repositories"]["LowYSwampHut"]
        if not (target / ".git").exists():
            if target.exists() and any(target.iterdir()):
                raise RuntimeError(
                    "Dependency directory must be empty or a Git checkout"
                )
            subprocess.run(
                ["git", "clone", "--no-checkout", URL, str(target)],
                check=True,
                env=environment,
            )
        elif subprocess.check_output(
            ["git", "-C", str(target), "status", "--porcelain"], text=True
        ).strip():
            raise RuntimeError("Terrain dependency has local changes")
        subprocess.run(
            ["git", "-C", str(target), "fetch", "origin", revision],
            check=True,
            env=environment,
        )
        subprocess.run(
            ["git", "-C", str(target), "checkout", "--detach", revision], check=True
        )
    failures = [
        name
        for name, digest in lock["inputs"].items()
        if not (options.root / name).is_file()
        or hashlib.sha256((options.root / name).read_bytes()).hexdigest() != digest
    ]
    if failures:
        raise SystemExit("Dependency input mismatch:\n" + "\n".join(failures))
    print(f"Verified {len(lock['inputs'])} dependency inputs")


if __name__ == "__main__":
    main()
