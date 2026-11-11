"""Canonical vanilla world configuration shared by search and verification."""

import copy
import re

WORLD_TYPES = ("normal", "large_biomes", "single_biome")


def world_config(world_type="normal", biome=None):
    if world_type not in WORLD_TYPES:
        raise ValueError("world_type must be normal, large_biomes or single_biome")
    result = {"world_type": world_type}
    if world_type != "single_biome":
        if biome is not None:
            raise ValueError("biome is only valid for single_biome")
        return result
    biome = "minecraft:swamp" if biome is None else biome
    if not isinstance(biome, str) or not biome:
        raise ValueError("Invalid biome resource identifier")
    if ":" not in biome:
        biome = "minecraft:" + biome
    if not re.fullmatch(r"[a-z0-9_.-]+:[a-z0-9/._-]+", biome):
        raise ValueError("Invalid biome resource identifier")
    result["biome"] = biome
    return result


def config_world(config):
    return world_config(config.get("world_type", "normal"), config.get("biome"))


def world_has_witch_huts(config):
    """Apply the vanilla hut biome tag after registry validation by the service."""
    world = config_world(config)
    return world["world_type"] != "single_biome" or world["biome"] == "minecraft:swamp"


def world_build_profile(profile, world_type="normal"):
    return profile if world_type == "normal" else profile + "-" + world_type


def noise_specs_for_world(specs, world_type="normal"):
    """Large climate noises use different named seeds AND octave frequencies."""
    world_config(world_type)
    result = copy.deepcopy(specs)
    if world_type == "large_biomes":
        for name in ("erosion", "temperature", "continentalness"):
            spec = result[name]
            spec["name"] += "_large"
            spec["config"]["base_octave"] -= 2
            for layer in spec["layers"]:
                octave = int(layer["octave"].removeprefix("octave_")) - 2
                layer["octave"] = "octave_" + str(octave)
                layer["frequency"] *= 0.25
    return result
