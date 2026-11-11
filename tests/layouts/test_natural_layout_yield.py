from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
from ultra_low_hut._native import LIB
from ultra_low_hut.layouts.measure_yields import optimistic_height_sum, raw_height_bound


class NaturalLayoutYieldTests(unittest.TestCase):
    def test_clearings_bridge_existing_air(self):
        # Surface height at -48, existing cavity below it, then occupied strata at -54.
        occupied = (1 << 10) - 1 | (1 << 15)
        clearing = 1 << 15
        self.assertEqual(optimistic_height_sum([occupied], [clearing]), -54)
        # Clearing at -49 can lower a column by six despite a one-block run.
        self.assertEqual(raw_height_bound([clearing] * 63), -53)


    @unittest.skipUnless(
        LIB.exists(), "CPU library required"
    )
    def test_full_masks_preserve_existing_low_height_masks(self):
        from ultra_low_hut.layouts.bindings import mineshaft_clearing_masks, room_geometry

        for x, z in [(0, 0), (12582912, 20000000), (20000000, 12582912)]:
            full = mineshaft_clearing_masks(156186219368766, x, z)
            low = room_geometry(156186219368766, x, z)[1]
            self.assertEqual([v & 0xFFFFFFFF for v in full], list(low))


if __name__ == "__main__":
    unittest.main()
