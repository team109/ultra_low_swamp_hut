"""Submit natural-generation queries to every selected game version."""

import hashlib
import json
from pathlib import Path

from ultra_low_hut.versions import resolve
from ultra_low_hut.world_types import world_config
from ultra_low_hut.verification.loading_orders import LOADING_FIELDS, LOADING_POLICY, get_order_spec, summarize_loading_orders, normalize_verification_mode


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


def loading_order_fields(responses, versions):
    selected = {
        item["result"].get("version", version): item["result"]
        for version, item in responses.items()
        if item["result"].get("version", version) in versions
    }
    policies = {r["loading_policy"] for r in selected.values()}
    if len(policies) != 1:
        raise ValueError("Cannot combine different generation policies across versions")
    modes = {normalize_verification_mode(r.get("verification_mode", "on")) for r in selected.values()}
    if len(modes) != 1:
        raise ValueError("Cannot combine different verification modes across versions")
    return dict(
        loading_policy=policies.pop(),
        min_hpos=min(r["min_hpos"] for r in selected.values()),
        loading_order_affected=any(r["loading_order_affected"] for r in selected.values()),
        loading_order_heights={v: r["loading_order_heights"] for v, r in selected.items()},
        min_hpos_approaches={v: r["min_hpos_approaches"] for v, r in selected.items()},
    )


class VerificationGroup:
    def __init__(self, versions, directories, *, world_type="normal", biome=None,
                 loading_policy=None, verification_mode="on"):
        verification_mode = normalize_verification_mode(verification_mode)
        if verification_mode != "on":
            raise ValueError("Vanilla verification mode must be on")
        self.verification_mode = verification_mode
        self.order_spec = get_order_spec(verification_mode)
        if loading_policy in (LOADING_POLICY, "features-3x3-v1"):
            self.order_spec = None
        elif loading_policy is not None and loading_policy != self.order_spec["id"]:
            raise ValueError("Verification mode differs from its loading-order policy")
        self.versions = list(versions)
        self.directories = {v: Path(directories[v]) for v in versions}
        world = world_config(world_type, biome)
        self.world_type = world["world_type"]
        self.loading_policy = loading_policy or self.order_spec["id"]
        self.biome = world.get("biome")

    def ready(self):
        if not all((d / "ready.json").exists() for d in self.directories.values()):
            return False
        for directory in self.directories.values():
            ready = json.loads((directory / "ready.json").read_text())
            profile = ready.get("loading_order_profiles", {}).get(self.verification_mode)
            policy = profile.get("loading_policy") if profile else ready.get("loading_policy")
            if policy != self.loading_policy:
                raise RuntimeError("Verifier uses a different loading-order policy")
        if self.biome is not None:
            for version, directory in self.directories.items():
                ready = json.loads((directory / "ready.json").read_text())
                if not isinstance(ready.get("biomes"), list):
                    raise RuntimeError("Rebuild the query service to validate single-biome worlds")
                if self.biome not in ready["biomes"]:
                    raise ValueError(f"Unknown biome for {version}: {self.biome}")
        return True

    def submit(self, candidate, atomic):
        identity = f"{candidate['seed']}:{candidate['x']}:{candidate['z']}"
        if self.world_type != "normal":
            identity += f":{self.world_type}:{self.biome or ''}"
        name = hashlib.sha256(identity.encode()).hexdigest() + ".json"
        request = dict(
            seed=candidate["seed"],
            x=candidate["x"],
            z=candidate["z"],
            geometry=dict(width=candidate["geometry"]["width"]),
            loading_orders=True,
            verification_mode=self.verification_mode,
            loading_order_profile=self.verification_mode,
            world_type=self.world_type,
        )
        if self.biome is not None:
            request["biome"] = self.biome
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
            if result.get("world_type", "normal") != self.world_type or result.get("biome") != self.biome:
                raise RuntimeError("Verifier world configuration mismatch")
            responses[version] = dict(response=path, result=result)
            if "error" in result:
                raise RuntimeError(f"Verifier failed for {version}: {result['error']}")
            actual = result.get("version", version)
            expected = resolve(version)["representative"]
            if actual not in (version, expected):
                raise RuntimeError(f"Verifier version mismatch: {version}: {actual}")
            for field in ("seed", "x", "z"):
                if field in result and str(result[field]) != str(candidate[field]):
                    raise RuntimeError("Verifier candidate mismatch: " + field)
            if normalize_verification_mode(result.get("verification_mode", "on")) != self.verification_mode:
                raise RuntimeError("Verifier verification-mode mismatch")
            summary = summarize_loading_orders(result.get("loading_orders", {}), spec=self.order_spec)
            if summary["loading_policy"] != self.loading_policy:
                raise RuntimeError("Verifier uses a different loading-order policy")
            if any(result.get(field) != summary[field] for field in LOADING_FIELDS):
                raise RuntimeError("Verifier loading-order summary mismatch")
            expected_heights = [] if summary["min_hpos"] is None else [summary["min_hpos"]]
            if result.get("heights") != expected_heights:
                raise RuntimeError("Verifier did not return the configured loading-order minimum")
            for height in set(result.get("heights", [])):
                if type(height) is not int:
                    raise RuntimeError("Verifier returned a non-integer height")
                group = grouped.setdefault(height, [])
                if actual not in group:
                    group.append(actual)
        return grouped, responses
