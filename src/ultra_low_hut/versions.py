from ultra_low_hut import ROOT

"""Reviewed default-world version intervals used by the independent hut hunt."""

import copy, json
from pathlib import Path

CATALOG = ROOT / "config/versions/profiles.json"


def catalog():
    data = json.loads(CATALOG.read_text())
    seen = set()
    for row in data["intervals"]:
        if not row["versions"] or row["representative"] not in row["versions"]:
            raise ValueError("Invalid representative")
        for v in row["versions"]:
            if v in seen:
                raise ValueError("Overlapping version intervals: " + v)
            seen.add(v)
    return data


def resolve(version):
    # Official release IDs omit .0; accept it without accepting unlisted patches.
    v = str(version)
    if v.endswith(".0"):
        v = v[:-2]
    for row in catalog()["intervals"]:
        if v in row["versions"]:
            result = copy.deepcopy(row)
            result["requested_version"] = v
            return result
    raise ValueError("Unsupported hut version: " + str(version))


def resolve_hunt(version, room_y_max=None, coordinate_layouts=False):
    cfg = resolve(version)
    policy = None
    if coordinate_layouts:
        policy = json.loads(
            (CATALOG.parents[1] / "search/screening.json").read_text()
        )
        if not cfg["screen"]["coordinate_room"]:
            raise ValueError("Coordinate room search requires version 1.19.3 or later")
        if room_y_max not in (None, policy["room_y_max"]):
            raise ValueError("Coordinate layout policy requires room_y_max=-62")
        room_y_max = policy["room_y_max"]
    if room_y_max is not None:
        if not -62 <= room_y_max <= -53:
            raise ValueError("room_y_max must be in -62..-53")
        if not cfg["screen"]["coordinate_room"]:
            raise ValueError("Room-focused search requires version 1.19.3 or later")
        cfg["screen"].update(room_only=True, room_y_max=room_y_max)
    cfg["build_profile"] = cfg["id"] + (
        f"-room{room_y_max}" if room_y_max is not None else ""
    )
    if policy:
        cfg["coordinate_layouts"] = policy
        cfg["screen"].update(
            min_template_gain53=0,
            min_covered_columns=0,
            inverse_k=policy["inverse_k"],
            upper16_batch=policy.get("upper16_batch", cfg["screen"]["upper16_batch"]),
        )
        cfg["build_profile"] += "-coordinate"
    return cfg
