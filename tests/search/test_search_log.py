import json
from pathlib import Path
import tempfile
import unittest

from ultra_low_hut.search.log import SearchLog


class SearchLogTests(unittest.TestCase):
    def test_discoveries_use_a_compact_english_schema_and_resume_without_duplicates(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            row = dict(
                seed=-123,
                x=16,
                z=-32,
                HPos=-59,
                excavation=321,
                versions=["1.21", "26.3"],
                verified_at=100,
                campaign_trials_observed_at_verification=65536,
            )
            log = SearchLog(directory, 40)
            log.discovery(row)
            SearchLog(directory, 40).discovery(row)
            lines = (Path(directory) / "results.jsonl").read_text().splitlines()
            self.assertEqual(len(lines), 1)
            self.assertTrue(lines[0].isascii())
            self.assertEqual(
                json.loads(lines[0]),
                dict(
                    world_type="normal",
                    time="1970-01-01T00:01:40+00:00",
                    seed="-123",
                    x=16,
                    z=-32,
                    spawn_y=-59,
                    excavation=321,
                    versions=["1.21", "26.3"],
                    elapsed_seconds=60,
                    seed_position_trials=65536,
                ),
            )

    def test_world_configuration_is_preserved_and_part_of_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            row = dict(seed="1", x=0, z=0, HPos=-59, excavation=10, versions=["1.21"],
                       verified_at=100, campaign_trials_observed_at_verification=20)
            log = SearchLog(directory, 0)
            log.discovery(row)
            log.discovery(dict(row, world_type="single_biome", biome="minecraft:swamp"))
            records = [json.loads(line) for line in log.results.read_text().splitlines()]
            self.assertEqual(len(records), 2)
            self.assertEqual(records[1]["biome"], "minecraft:swamp")
