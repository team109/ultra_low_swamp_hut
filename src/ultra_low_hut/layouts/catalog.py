"""Shared mineshaft template records and footprint validation."""

import ctypes
import json
from pathlib import Path

from ultra_low_hut import ROOT
LAYOUT_CATALOG = ROOT / "data/mineshafts/templates.json"
_ENUMERATION = json.loads((ROOT / "data/mineshafts/enumeration.json").read_text())
LAYOUT_PROFILE = _ENUMERATION["layout_profile"]
LAYOUT_VERSIONS = frozenset(_ENUMERATION["supported_versions"])


class LayoutCandidate(ctypes.Structure):
    _fields_ = [("target", ctypes.c_uint64)] + [
        (name, ctypes.c_int)
        for name in (
            "g53",
            "g54",
            "far53",
            "far54",
            "covered",
            "pieces",
            "room_width",
            "room_height",
            "room_depth",
            "bottom",
            "origin_x",
            "origin_z",
            "corridor_gain",
            "hut_width",
            "region_mask",
            "ordered_gain",
            "bridge_columns",
            "deep_corridor_gain",
        )
    ]


def template(candidate, model):
    return dict(
        layout_profile=LAYOUT_PROFILE,
        original=str(candidate.target),
        target=str(candidate.target),
        relx=0,
        relz=0,
        width=candidate.hut_width,
        g53=candidate.far53,
        g54=candidate.far54,
        geometry_origin=[candidate.origin_x, candidate.origin_z],
        covered=candidate.covered,
        pieces=candidate.pieces,
        coordinate_gain54=candidate.far54,
        coordinate_regions_mask=candidate.region_mask,
        dimensions=[candidate.room_width, candidate.room_height, candidate.room_depth],
        room_bottom=candidate.bottom,
        auxiliary_corridor_gain=candidate.corridor_gain,
        deep_corridor_gain=candidate.deep_corridor_gain,
        ordered_floor_gain=candidate.ordered_gain,
        bridge_columns=candidate.bridge_columns,
        prior_origin=[candidate.origin_x, candidate.origin_z],
        layout_model=model,
    )


def template_footprint(row):
    width = int(row.get("width", row.get("hut_width", 7)))
    if "hut_width" in row and int(row["hut_width"]) != width:
        raise ValueError("Template width and hut_width disagree")
    relative_x, relative_z = int(row.get("relx", 0)), int(row.get("relz", 0))
    if width not in (7, 9) or any(
        not -(1 << 31) <= v < 1 << 31 for v in (relative_x, relative_z)
    ):
        raise ValueError("Template requires width 7 or 9 and signed 32-bit offsets")
    return relative_x, relative_z, width


def require_natural_template(row):
    if row.get("mineshaft_type", "normal") != "normal":
        raise ValueError("Search layouts require a NORMAL mineshaft")
    if (
        row.get("controlled_forced_terminal_height", False)
        or row.get("forced_terminal_height", False)
        or "force_room_bottom" in row
    ):
        raise ValueError(
            "Layout templates must use natural mineshaft placement heights"
        )
    relative_x, relative_z, width = template_footprint(row)
    if relative_x == 0 and relative_z == 0:
        target = int(row["target"])
        state = ((target ^ 0x5DEECE66D) * 0x5DEECE66D + 11) & ((1 << 48) - 1)
        expected = 9 if (state >> 46) & 1 else 7
        if width != expected:
            raise ValueError(
                f"Same-chunk layout {target} requires a {expected}×{63 // expected} "
                f"swamp-hut footprint; received {width}×{63 // width}"
            )
    if row.get("layout_profile") is not None:
        if row["layout_profile"] != LAYOUT_PROFILE:
            raise ValueError("Unknown mineshaft layout profile")
        if (relative_x, relative_z) != (0, 0):
            raise ValueError("Shared layouts require a same-chunk NORMAL mineshaft")


def require_layout_version(row, version):
    """Check layout reuse separately from version-specific terrain screening."""
    from ultra_low_hut.versions import resolve_hunt

    require_natural_template(row)
    destination = resolve_hunt(version, -62, True)
    source = resolve_hunt(row["version"], -62, True) if row.get("version") else None
    shared = row.get("layout_profile") == LAYOUT_PROFILE
    # Old exported templates may carry their source version without a profile.
    # The audited NORMAL, same-chunk construction is shared across these releases.
    if source is not None and template_footprint(row)[:2] == (0, 0):
        shared = source["requested_version"] in LAYOUT_VERSIONS
    if shared:
        if destination["requested_version"] not in LAYOUT_VERSIONS or (
            source is not None and source["requested_version"] not in LAYOUT_VERSIONS
        ):
            raise ValueError("Shared layout has not been qualified for this release")
    elif source is not None and source["screen"] != destination["screen"]:
        raise ValueError(
            "Layout template version requires a different screening configuration"
        )
