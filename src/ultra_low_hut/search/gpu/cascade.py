"""GPU noise-cascade bindings and stage counters."""

import ctypes as C
import hashlib
from array import array

NAMES = [
    "offset",
    "erosion",
    "temperature",
    "continentalness",
    "ridge",
    "aquifer_fluid_level_floodedness",
    "cave_entrance",
    "cave_cheese",
    "spaghetti_3d_rarity",
    "spaghetti_3d_thickness",
    "spaghetti_3d_1",
    "spaghetti_3d_2",
    "spaghetti_roughness_modulator",
    "spaghetti_roughness",
]
STAGES = (
    ["erosion", "temperature", "continentalness", "ridge"]
    + ["dry_" + str(y) for y in [60, 0, -53, 30, -30]]
    + ["opening_60", "opening_50"]
    + ["cave_" + str(y) for y in [0, -53, -30, 30, -10, -40, 10, 40, 20]]
)


class Cascade:
    def __init__(self, device, specs, library, world_type="normal"):
        from ultra_low_hut.world_types import noise_specs_for_world

        specs = noise_specs_for_world(specs, world_type)
        self.stages = STAGES[:4] + ["surface56"] + STAGES[4:]
        if device not in range(8):
            raise ValueError("Physical GPU must be in 0..7")
        self.lib = C.CDLL(str(library))
        self.lib.nc26_create.argtypes = [
            C.c_int,
            C.c_void_p,
            C.c_void_p,
            C.c_void_p,
            C.c_void_p,
            C.c_void_p,
            C.c_int,
        ]
        self.lib.nc26_create.restype = C.c_uint64
        self.lib.nc26_destroy.argtypes = [C.c_uint64]
        self.lib.nc26_destroy.restype = None
        names = NAMES.copy()
        md5 = lambda s: [
            int.from_bytes(hashlib.md5(s.encode()).digest()[i : i + 8], "big")
            for i in (0, 8)
        ]
        hashes = array("Q")
        ranges = array("i")
        oh = array("Q")
        banks = array("i")
        fa = array("d")
        for name in names:
            spec = specs[name]
            hashes.extend(md5(spec["name"]))
            ranges.extend([len(banks), len(spec["layers"])])
            for v in spec["layers"]:
                oh.extend(md5(v["octave"]))
                banks.append(v["bank"])
                fa.extend([v["frequency"], v["amplitude"]])
        ptr = lambda a: a.buffer_info()[0]
        self.handle = self.lib.nc26_create(
            device, ptr(hashes), ptr(ranges), ptr(oh), ptr(banks), ptr(fa), len(banks)
        )
        if not self.handle:
            raise RuntimeError("cascade GPU initialization failed")

    def close(self):
        if self.handle:
            self.lib.nc26_destroy(self.handle)
            self.handle = 0
