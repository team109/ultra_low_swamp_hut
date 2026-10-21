"""Submit natural-generation queries to every selected game version."""

import hashlib
import json
from pathlib import Path

from mcsearch.hut_versions import resolve


def verification_options(screen_version, versions=None, java_options=None):
    versions = list(dict.fromkeys(versions or [screen_version]))
    for version in versions:
        resolve(version)
    executables = {}
    for value in java_options or []:
        version, separator, executable = value.partition("=")
        if not separator or version not in versions or not executable:
            raise ValueError("--verify-java requires a selected VERSION=JAVA")
        executables[version] = executable
    return versions, executables


def excavation_fields(candidate):
    geometry = candidate.get("geometry", {})
    fields = {}
    for source, target in (
        ("optimisticGainFromMinus54", "excavation"),
        ("optimisticGainFromMinus53", "excavation_from_minus53"),
    ):
        if source in geometry:
            fields[target] = int(geometry[source])
    return fields


class VerificationGroup:
    def __init__(self, versions, directories):
        self.versions = list(versions)
        self.directories = {v: Path(directories[v]) for v in versions}

    def ready(self):
        return all((d / "ready.json").exists() for d in self.directories.values())

    def submit(self, candidate, atomic):
        name = (
            hashlib.sha256(
                f"{candidate['seed']}:{candidate['x']}:{candidate['z']}".encode()
            ).hexdigest()
            + ".json"
        )
        request = dict(
            seed=candidate["seed"],
            x=candidate["x"],
            z=candidate["z"],
            geometry=dict(width=candidate["geometry"]["width"]),
        )
        for directory in self.directories.values():
            atomic(directory / "inbox" / name, request)
        return name, candidate

    def collect(self, active):
        name, candidate = active
        paths = {v: d / "outbox" / name for v, d in self.directories.items()}
        if not all(p.exists() for p in paths.values()):
            return None
        grouped, responses = {}, {}
        for version in self.versions:
            path = paths[version]
            result = json.loads(path.read_text())
            if result.get("controlled", False):
                raise RuntimeError("Discovery verification requires natural generation")
            responses[version] = dict(response=path, result=result)
            if "error" in result:
                continue
            actual = result.get("version", version)
            expected = resolve(version)["representative"]
            if actual not in (version, expected):
                raise RuntimeError(f"Verifier version mismatch: {version}: {actual}")
            for field in ("seed", "x", "z"):
                if field in result and str(result[field]) != str(candidate[field]):
                    raise RuntimeError("Verifier candidate mismatch: " + field)
            for height in set(result.get("heights", [])):
                if type(height) is not int:
                    raise RuntimeError("Verifier returned a non-integer height")
                group = grouped.setdefault(height, [])
                if actual not in group:
                    group.append(actual)
        return grouped, responses
