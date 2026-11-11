"""CPU bindings for mineshaft room and clearing geometry."""

from ultra_low_hut._native import C, I, IP, check, library


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
