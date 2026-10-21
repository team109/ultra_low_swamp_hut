"""Shared ctypes records for mineshaft layout inversion."""

import ctypes as C
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Template(C.Structure):
    _fields_ = [("original", C.c_uint64), ("target", C.c_uint64)] + [
        (s, C.c_int)
        for s in ["relx", "relz", "width", "g53", "g54", "covered", "pieces"]
    ]


class Mapped(C.Structure):
    _fields_ = [("seed", C.c_uint64)] + [
        (s, C.c_int)
        for s in [
            "cx",
            "cz",
            "x",
            "z",
            "width",
            "g53",
            "g54",
            "covered",
            "pieces",
            "index",
        ]
    ]
