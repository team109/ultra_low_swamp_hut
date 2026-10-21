"""Compact GPU result decoding, including buffer growth and signed seeds."""

import ctypes as C
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from noise_batch import BatchCascade


class NoiseBatchTests(unittest.TestCase):
    @staticmethod
    def pipeline(encoded, overflow=False):
        pipeline = object.__new__(BatchCascade)
        pipeline.handle = 1
        pipeline.stages = ["erosion", "temperature"]
        calls = []

        def compact(handle, lows, coords, roots, stages, bins, output, capacity, count):
            calls.append(capacity)
            C.cast(count, C.POINTER(C.c_int))[0] = len(encoded)
            if overflow and len(calls) == 1:
                return -2
            histogram = C.cast(bins, C.POINTER(C.c_int))
            for root in range(roots):
                retained = sum(index // 65536 == root for index in encoded)
                histogram[root * 3] = 65536 - retained
                histogram[root * 3 + 1] = 0
                histogram[root * 3 + 2] = retained
            buffer = C.cast(output, C.POINTER(C.c_uint32))
            for index, value in enumerate(encoded):
                buffer[index] = value
            return 0

        pipeline.compact = compact
        return pipeline, calls

    def test_decodes_roots_and_signed_world_seeds(self):
        pipeline, _ = self.pipeline([65536 + 65535, 3])
        pairs = [
            (
                dict(low48="7", mineChunkX=0, mineChunkZ=0),
                dict(hutChunkX=i, hutChunkZ=-i),
            )
            for i in range(2)
        ]
        result = pipeline.batch(pairs)
        self.assertEqual(result[0][0]["counts"]["temperature"], 1)
        self.assertEqual(int(result[0][1][0]["seed"]), 7 | (3 << 48))
        self.assertEqual(result[1][1][0]["x"], 16)
        self.assertEqual(result[1][1][0]["z"], -16)
        self.assertEqual(int(result[1][1][0]["seed"]), (7 | (65535 << 48)) - (1 << 64))

    def test_retries_with_the_required_output_capacity(self):
        pipeline, calls = self.pipeline(list(range(1100)), overflow=True)
        result = pipeline.batch(
            [
                (
                    dict(low48="1", mineChunkX=0, mineChunkZ=0),
                    dict(hutChunkX=0, hutChunkZ=0),
                )
            ]
        )
        self.assertEqual(calls, [1024, 1100])
        self.assertEqual(len(result[0][1]), 1100)


if __name__ == "__main__":
    unittest.main()
