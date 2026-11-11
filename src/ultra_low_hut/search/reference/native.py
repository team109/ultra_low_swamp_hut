"""CPU reference terrain screening context."""

from array import array

from ultra_low_hut._native import C, I, IP, P, LIB, check, library, ptr


class Context:
    def __init__(self, seed, version="26.3", device=-1, *, world_type="normal", biome=None, cpu_library=None):
        from ultra_low_hut.world_types import WORLD_TYPES, world_config

        self.world = world_config(world_type, biome)
        self.seed, self.device = seed, device
        self.lib = library(cpu_library)
        if hasattr(self.lib, "ms_open_world"):
            fn = self.lib.ms_open_world
            fn.argtypes = [C.c_uint64, C.c_char_p, I, I, I]
            fn.restype = P
            self.handle = fn(seed, version.encode(), device,
                             WORLD_TYPES.index(world_type),
                             int(self.world.get("biome") == "minecraft:swamp"))
        elif world_type == "normal":
            self.handle = self.lib.ms_open(seed, version.encode(), device)
        else:
            raise RuntimeError("Rebuild the CPU reference library for world type support")
        if not self.handle:
            raise RuntimeError(self.lib.ms_error().decode())

    def close(self):
        if self.handle:
            self.lib.ms_close(self.handle)
            self.handle = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def hut(self, x, z, max_y):
        out = array("i", [0]) * 5
        check(self.lib.ms_hut(self.handle, x, z, max_y, ptr(out)), self.lib)
        return dict(
            y=out[0],
            accepted=bool(out[1]),
            biome=out[2],
            wet_columns=out[3],
            orientation=out[4],
        )

    def screen_hut(self, x, z, max_y):
        """Evaluate acceptance; rejected candidates omit height and wet-count diagnostics."""
        out = array("i", [0]) * 5
        check(self.lib.ms_hut_screen(self.handle, x, z, max_y, ptr(out)), self.lib)
        return dict(
            y=out[0] if out[1] else None,
            accepted=bool(out[1]),
            biome=out[2],
            wet_columns=out[3] if out[1] else None,
            orientation=out[4],
        )

    def room_budget(self, x, z, geometry, target=-57):
        """Pre-feature excavation budget for the geometry's hut footprint."""
        width = getattr(geometry, "width", 7)
        fn = self.lib.ms_room_budget_gate_footprint
        out = (I * 3)()
        fn.argtypes = [P, I, I, IP, C.POINTER(C.c_uint32), I, I, IP]
        check(fn(self.handle, x, z, *geometry, width, target, out), self.lib)
        return dict(
            stage=out[0], probes=out[1], optimistic_sum=out[2], passed=out[0] == 0
        )
