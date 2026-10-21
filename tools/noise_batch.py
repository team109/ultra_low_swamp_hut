"""Batched noise screening with compact GPU output."""

import ctypes as C
from array import array
from noise_cascade import Cascade


class BatchCascade(Cascade):
    def __init__(self, device, specs, library):
        super().__init__(device, specs, library)
        self.compact = self.lib.nc26_batch_compact
        self.compact.argtypes = [
            C.c_uint64,
            C.c_void_p,
            C.c_void_p,
            C.c_int,
            C.c_int,
            C.c_void_p,
            C.c_void_p,
            C.c_int,
            C.c_void_p,
        ]
        self.compact.restype = C.c_int

    def batch(self, pairs):
        if not 1 <= len(pairs) <= 2048:
            raise ValueError("A noise batch must contain 1..2048 seed-position pairs")
        lows = array("Q", [int(root["low48"]) for root, _ in pairs])
        coords = array(
            "i",
            [
                value
                for _, hut in pairs
                for value in (hut["hutChunkX"] * 16, hut["hutChunkZ"] * 16)
            ],
        )
        bins = len(self.stages) + 1
        histograms = array("i", [0]) * (len(pairs) * bins)
        capacity = max(1024, len(pairs) * 16)
        indices = array("I", [0]) * capacity
        count = C.c_int()

        def evaluate():
            return self.compact(
                self.handle,
                lows.buffer_info()[0],
                coords.buffer_info()[0],
                len(pairs),
                len(self.stages),
                histograms.buffer_info()[0],
                indices.buffer_info()[0],
                capacity,
                C.byref(count),
            )

        code = evaluate()
        if code == -2:
            capacity = count.value
            indices = array("I", [0]) * capacity
            code = evaluate()
        if code:
            raise RuntimeError("Compact cascade CUDA status " + str(code))
        selected = [[] for _ in pairs]
        for index in sorted(indices[: count.value]):
            root_index, high16 = divmod(index, 65536)
            selected[root_index].append(high16)
        result = []
        for root_index, (root, hut) in enumerate(pairs):
            remaining = 65536
            counts = {"upper16": remaining}
            for index, name in enumerate(self.stages):
                remaining -= histograms[root_index * bins + index]
                counts[name] = remaining
            low = lows[root_index]
            x, z = coords[2 * root_index : 2 * root_index + 2]
            high16_values = selected[root_index]
            found = []
            for high16 in high16_values:
                seed = low | (high16 << 48)
                found.append(
                    dict(
                        seed=str(seed if seed < (1 << 63) else seed - (1 << 64)),
                        x=x,
                        z=z,
                        mineChunkX=root["mineChunkX"],
                        mineChunkZ=root["mineChunkZ"],
                        geometry=hut,
                        status="heuristic-natural-candidate-unverified",
                    )
                )
            result.append((dict(low48=str(low), x=x, z=z, counts=counts), found))
        return result
