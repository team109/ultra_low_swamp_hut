"""Published catalogs must agree with their indexes and measurement inputs."""

import json
import math
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def read_json(path):
    return json.loads(path.read_text())


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


class DataCatalogTests(unittest.TestCase):
    def test_hut_index_rows_and_loading_orders(self):
        root = ROOT / "data/huts"
        index = read_json(root / "index.json")
        prefixes = set()
        for line in (ROOT / "config/verification/loading-orders.txt").read_text().splitlines():
            order = line.partition("#")[0].split()
            if order:
                prefixes.add(" ".join(order[:order.index("C") + 1]))
        files = set()
        for group in index["version_groups"]:
            seen = set()
            for entry in group["files"]:
                with self.subTest(file=entry["file"]):
                    self.assertNotIn(entry["file"], files)
                    files.add(entry["file"])
                    rows = read_rows(root / entry["file"])
                    self.assertEqual(len(rows), entry["huts"])
                    positions = []
                    for row in rows:
                        self.assertEqual(set(row), {"seed", "x", "z", "loading_order_affected"}
                                         | ({"min_hpos_order"} if row["loading_order_affected"] else set()))
                        self.assertIsInstance(row["seed"], str)
                        self.assertTrue(-(1 << 63) <= int(row["seed"]) < 1 << 63)
                        for axis in ("x", "z"):
                            self.assertIs(type(row[axis]), int)
                        self.assertIs(type(row["loading_order_affected"]), bool)
                        if row["loading_order_affected"]:
                            self.assertIn(row["min_hpos_order"], prefixes)
                        position = (int(row["seed"]), row["x"], row["z"])
                        self.assertNotIn(position, seen)
                        seen.add(position)
                        positions.append(position)
                    self.assertEqual(positions, sorted(positions))

    def test_layout_templates_regions_and_yield_measurements(self):
        root = ROOT / "data/mineshafts"
        index = read_json(root / "index.json")
        layouts = read_rows(root / "layouts.jsonl")
        templates = read_json(root / index["templates"])
        references = read_json(root / index["reference_positions"])
        seeds = {row["layout_seed"] for row in layouts}
        self.assertEqual(len(layouts), index["layouts"])
        self.assertEqual(len(seeds), len(layouts))
        self.assertEqual({row["target"] for row in templates}, seeds)
        self.assertEqual(len(templates), len(seeds))
        self.assertEqual({row["layout_seed"] for row in references}, seeds)
        self.assertEqual(len(references), len(seeds))
        references = {row["layout_seed"]: (row["x"], row["z"]) for row in references}
        cells = {}
        best = {}
        for region_id, region in enumerate(index["regions"]):
            rows = read_rows(root / region["file"])
            self.assertEqual(len(rows), region["layouts"], region["file"])
            keys = [(row["layout_seed"], region_id) for row in rows]
            self.assertEqual(len(set(keys)), len(rows))
            for key, row in zip(keys, rows):
                self.assertIn(row["layout_seed"], seeds)
                self.assertIs(type(row["excavation"]), int)
                self.assertTrue(math.isfinite(row["expected59_per_trillion_trials"]))
                self.assertGreaterEqual(row["expected59_per_trillion_trials"], 0)
                cells[key] = row
                score = (row["expected59_per_trillion_trials"], row["excavation"])
                if row["layout_seed"] not in best or score > best[row["layout_seed"]][0]:
                    best[row["layout_seed"]] = (score, row, (region["reference_x"], region["reference_z"]))
        for row in layouts:
            self.assertEqual(row, best[row["layout_seed"]][1])
            self.assertEqual(references[row["layout_seed"]], best[row["layout_seed"]][2])
        score = lambda row: (-row["expected59_per_trillion_trials"], -row["excavation"])
        self.assertEqual(layouts, sorted(layouts, key=score))
        measurement = read_json(root / index["yield_measurement"])
        panel = read_json(root / measurement["panel"])
        results = read_rows(root / measurement["results"])
        self.assertEqual(len(results), measurement["layout_regions"])
        self.assertEqual(len(seeds), measurement["layouts"])
        self.assertEqual(len({row["id"] for row in panel}), len(panel))
        self.assertEqual(len(panel), measurement["measurement"]["natural_terrains"])
        self.assertEqual({(row["layout_seed"], row["region"]) for row in results}, set(cells))
        self.assertEqual(len(results), len(cells))
        for row in results:
            key = (row["layout_seed"], row["region"])
            self.assertEqual({field: row[field] for field in cells[key]}, cells[key])
            region = index["regions"][row["region"]]
            self.assertEqual(row["test_origin"], [region["reference_x"], region["reference_z"]])
            self.assertEqual(row["natural_terrains"], len(panel))
            self.assertEqual(row["decoration_draws"], measurement["decoration_draws"])
            self.assertTrue(0 <= row["hits59"] <= row["replayed_placements"])
        self.assertEqual(sum(row["replayed_placements"] for row in results),
                         measurement["measurement"]["replayed_placements"])


if __name__ == "__main__":
    unittest.main()
