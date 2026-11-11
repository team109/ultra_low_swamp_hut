import struct
from ultra_low_hut.layouts.bindings import room_geometry as compute_room_geometry
from ultra_low_hut._native import library, check, C, I

_room_boxes = {}
_geometry_cache = {}


def _float32(value):
    return struct.unpack("f", struct.pack("f", value))[0]


def room_geometry(target, x, z, width=7, relx=0, relz=0):
    if width not in (7, 9):
        raise ValueError("Hut width must be 7 or 9")
    if target not in _room_boxes:
        room_box = (I * 6)()
        query_room_box = library().ms_room_box
        query_room_box.argtypes = [C.c_uint64, C.POINTER(I)]
        check(query_room_box(target, room_box))
        _room_boxes[target] = list(room_box)
    room_box = _room_boxes[target]
    center_x = _float32(
        _float32(x - relx + room_box[0]) + _float32((room_box[3] - room_box[0] + 1) / 2)
    )
    center_z = _float32(
        _float32(z - relz + room_box[2]) + _float32((room_box[5] - room_box[2] + 1) / 2)
    )
    key = (
        target,
        width,
        relx,
        relz,
        tuple(_float32(_float32(x + i) - center_x) for i in range(width)),
        tuple(_float32(_float32(z + i) - center_z) for i in range(63 // width)),
    )
    if key not in _geometry_cache:
        _geometry_cache[key] = compute_room_geometry(target, x, z, width, relx, relz)
    return _geometry_cache[key]
