"""Load the shared CPU library and declare its C interface."""

import ctypes as C
import os
from pathlib import Path

from ultra_low_hut import ROOT
DEFAULT_LIBRARY = ROOT / "build-cpu-worlds/libmcsearch.so"
if not DEFAULT_LIBRARY.exists():
    DEFAULT_LIBRARY = ROOT / "build-cpu/libmcsearch.so"
LIB = Path(
    os.environ.get(
        "MCSEARCH_LIBRARY",
        DEFAULT_LIBRARY,
    )
)
_libraries = {}
I, D, P = C.c_int, C.c_double, C.c_void_p
IP, DP = C.POINTER(I), C.POINTER(D)


def library(path=None):
    """Load each selected CPU implementation independently of import order."""
    path = Path(path if path is not None else os.environ.get("MCSEARCH_LIBRARY", LIB)).resolve()
    if path not in _libraries:
        lib = C.CDLL(str(path))
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
        _libraries[path] = lib
    return _libraries[path]


def ptr(a, typ=I):
    return (typ * len(a)).from_buffer(a)


def check(status, lib=None):
    if status:
        raise RuntimeError((lib if lib is not None else library()).ms_error().decode())
