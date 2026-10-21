import ctypes as C
import os
from array import array
from pathlib import Path

LIB = Path(
    os.environ.get(
        "MCSEARCH_LIBRARY",
        Path(__file__).resolve().parents[1] / "build-cpu/libmcsearch.so",
    )
)
_lib = None
I, D, P = C.c_int, C.c_double, C.c_void_p
IP, DP = C.POINTER(I), C.POINTER(D)


def library():
    global _lib
    if _lib is None:
        lib = C.CDLL(str(LIB))
        signatures = {
            "ms_open": ([C.c_uint64, C.c_char_p, I], P),
            "ms_close": ([P], None),
            "ms_error": ([], C.c_char_p),
            "ms_hut": ([P, I, I, I, IP], I),
            "ms_hut_screen": ([P, I, I, I, IP], I),
        }
        for name, (args, result) in signatures.items():
            f = getattr(lib, name)
            f.argtypes = args
            f.restype = result
        _lib = lib
    return _lib


def ptr(a, typ=I):
    return (typ * len(a)).from_buffer(a)


def check(status):
    if status:
        raise RuntimeError(library().ms_error().decode())


class RoomGeometry(tuple):
    """Two-array geometry with the footprint used to index its 63 columns."""

    def __new__(cls, box, masks, width=7, relx=0, relz=0):
        result = super().__new__(cls, (box, masks))
        result.width, result.relx, result.relz = width, relx, relz
        return result


def room_geometry(target, x, z, width=7, relx=0, relz=0):
    """Mineshaft clearing geometry for a hut at its actual world anchor."""
    if width not in (7, 9):
        raise ValueError("Hut width must be 7 or 9")
    lib = library()
    lib.ms_room_box.argtypes = [C.c_uint64, IP]
    box, masks = (I * 6)(), (C.c_uint32 * 63)()
    check(lib.ms_room_box(target, box))
    box[0] -= relx
    box[3] -= relx
    box[2] -= relz
    box[5] -= relz
    fn = lib.ms_room_masks_for_hut
    fn.argtypes = [C.c_uint64, I, I, I, I, I, C.POINTER(C.c_uint32)]
    check(fn(target, x, z, width, relx, relz, masks))
    return RoomGeometry(box, masks, width, relx, relz)


def mineshaft_clearing_masks(target, x, z, width=7, relx=0, relz=0):
    """Optimistic full-height clearing masks, one Python integer per hut column."""
    fn = library().ms_mineshaft_clearing_masks
    fn.argtypes = [C.c_uint64, I, I, I, I, I, C.POINTER(C.c_uint64)]
    output = (C.c_uint64 * (63 * 6))()
    check(fn(target, x, z, width, relx, relz, output))
    return [
        sum(int(output[column * 6 + word]) << (word * 64) for word in range(6))
        for column in range(63)
    ]


class Context:
    def __init__(self, seed, version="26.3", device=-1):
        self.seed, self.device = seed, device
        self.lib = library()
        self.handle = self.lib.ms_open(seed, version.encode(), device)
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
        check(self.lib.ms_hut(self.handle, x, z, max_y, ptr(out)))
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
        check(self.lib.ms_hut_screen(self.handle, x, z, max_y, ptr(out)))
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
        check(fn(self.handle, x, z, *geometry, width, target, out))
        return dict(
            stage=out[0], probes=out[1], optimistic_sum=out[2], passed=out[0] == 0
        )
