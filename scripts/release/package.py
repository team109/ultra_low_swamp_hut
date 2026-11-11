"""Create a source archive containing code, configuration and published data."""

import argparse
import json
import os
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[2]
PUBLIC_FILES = (
    ".gitattributes", ".gitignore", "CMakeLists.txt", "LICENSE", "README.md",
    "THIRD_PARTY.md", "sources.lock.json",
)
PUBLIC_DIRECTORIES = (".github", "LICENSES", "config", "data", "docs", "scripts", "src", "tests")
EXCLUDED_DIRECTORIES = {".git", ".local", "__pycache__", ".venv"}
ARTIFACT_SUFFIXES = {".so", ".o", ".a", ".class", ".jar", ".pyc", ".pyo", ".pyd", ".log"}


def published_hut_files():
    directory = ROOT / 'data/huts'
    index = json.loads((directory / 'index.json').read_text())
    names = {'README.md', 'index.json', 'verification.json'}
    for group in index['version_groups']:
        names.update(entry['file'] for entry in group['files'])
        if group.get('verification'):
            names.add(group['verification'])
    paths = set()
    for name in names:
        path = directory / name
        if not path.resolve().is_relative_to(directory.resolve()):
            raise ValueError('Published hut file must stay inside data/huts: ' + name)
        if not path.is_file() or path.is_symlink():
            raise FileNotFoundError('Published hut file is missing or not a regular file: ' + str(path))
        paths.add(path)
    return paths


def source_files():
    huts = published_hut_files()
    for name in PUBLIC_FILES:
        path = ROOT / name
        if path.is_file() and not path.is_symlink():
            yield path
    for name in PUBLIC_DIRECTORIES:
        directory = ROOT / name
        if not directory.is_dir():
            continue
        for base, directories, files in os.walk(directory):
            directories[:] = sorted(
                d for d in directories
                if d not in EXCLUDED_DIRECTORIES and not d.endswith(".egg-info")
            )
            for filename in sorted(files):
                path = Path(base) / filename
                if path.is_relative_to(ROOT / "data/huts") and path not in huts:
                    continue
                if (path.is_file() and not path.is_symlink()
                        and path.suffix not in ARTIFACT_SUFFIXES
                        and filename not in {"AGENTS.md", ".env"}):
                    yield path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "dist/ultra-low-hut-source.tar.gz"
    )
    args = parser.parse_args()
    output = args.output.resolve()
    if output.is_relative_to(ROOT) and output.relative_to(ROOT).parts[0] not in (
        "dist", "runs",
    ):
        parser.error("Place generated archives in dist/, runs/, or outside the source tree")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    with tarfile.open(temporary, "w:gz") as archive:
        for path in source_files():
            archive.add(path, arcname="ultra-low-hut/" + path.relative_to(ROOT).as_posix())
    temporary.replace(output)
    print(output)


if __name__ == "__main__":
    main()
