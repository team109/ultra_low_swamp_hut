"""Resolve prepared vanilla dependencies after relocating the repository."""

import os
from pathlib import Path


def prepared_classpath(prepared):
    prepared = Path(prepared).resolve()
    marker = "/runs/versions/" + prepared.name + "/"
    paths = []
    for entry in (prepared / "classpath.txt").read_text().strip().split(os.pathsep):
        path = Path(entry)
        if not path.exists() and marker in entry:
            path = prepared / entry.split(marker, 1)[1]
        if not path.exists():
            raise FileNotFoundError("Missing prepared vanilla dependency: " + str(path))
        paths.append(str(path))
    return os.pathsep.join(paths)
