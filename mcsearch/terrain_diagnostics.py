"""Pre-feature optimistic excavation height; evaluated on complete terrain columns."""

import ctypes as C, time


def evaluate_excavation_bound(context, x, z, geometry, target=-58, early=True):
    masks = geometry[1]
    width = getattr(geometry, "width", 7)
    probe_terrain = context.lib.ms_terrain_probe
    probe_terrain.argtypes = [C.c_void_p, C.c_int, C.c_int, C.POINTER(C.c_int)]
    # Start every unqueried column at the world's lower limit. This avoids
    # assuming that a natural pre-feature column always reaches Y=-54.
    total = -64 * 63
    columns = {}
    probes = 0
    started_at = time.perf_counter()
    order = sorted(
        range(63), key=lambda column_index: int(masks[column_index]).bit_count()
    )
    for column_index in order:
        terrain_heights = (C.c_int * 2)()
        status = probe_terrain(
            context.handle,
            x + column_index % width,
            z + column_index // width,
            terrain_heights,
        )
        if status:
            raise RuntimeError(context.lib.ms_error().decode())
        height = terrain_heights[1]
        excavated_height = height
        while (
            excavated_height > -64
            and -64 <= excavated_height - 1 < -32
            and masks[column_index] & (1 << (excavated_height - 1 + 64))
        ):
            excavated_height -= 1
        columns[column_index] = dict(raw=height, optimistic=excavated_height)
        probes += 1
        total += excavated_height + 64
        if early and total > target * 63:
            break
    return dict(
        passed=total <= target * 63,
        optimistic_sum_lower_bound=total,
        columns_queried=probes,
        complete=probes == 63,
        seconds=time.perf_counter() - started_at,
        columns=columns,
    )


def check_room_boundary_fluids(context, x, z, geometry):
    probe_boundary_fluids = context.lib.ms_room_upper_fluid_gate
    probe_boundary_fluids.argtypes = [
        C.c_void_p,
        C.c_int,
        C.c_int,
        C.POINTER(C.c_int),
        C.POINTER(C.c_int),
    ]
    probe_boundary_fluids.restype = C.c_int
    probe_result = (C.c_int * 5)()
    started_at = time.perf_counter()
    status = probe_boundary_fluids(context.handle, x, z, geometry[0], probe_result)
    if status:
        raise RuntimeError(context.lib.ms_error().decode())
    return dict(
        passed=bool(probe_result[0]),
        probes=probe_result[1],
        first_liquid=list(probe_result)[2:] if not probe_result[0] else None,
        seconds=time.perf_counter() - started_at,
        scope="Pre-feature boundary faces above the bedrock band; official validation checks remaining generation effects",
    )


def calculate_excavation_gains(geometry):
    result = {}
    for base, key in [
        (-53, "optimisticGainFromMinus53"),
        (-54, "optimisticGainFromMinus54"),
    ]:
        total = 0
        for mask in geometry[1]:
            height = base
            while height > -64 and mask & (1 << (height + 63)):
                height -= 1
            total += base - height
        result[key] = total
    return result
