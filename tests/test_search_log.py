import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.search_log import SearchLog


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

    def test_progress_is_periodic_and_separate_from_discoveries(self):
        with tempfile.TemporaryDirectory() as directory:
            log = SearchLog(directory, 0)
            log.progress(65536, 2, 1, [0])
            log.progress(65536, 2, 1, [0])
            records = (Path(directory) / "progress.jsonl").read_text().splitlines()
            self.assertEqual(len(records), 1)
            self.assertEqual(json.loads(records[0])["seed_position_trials"], 65536)
            self.assertEqual((Path(directory) / "results.jsonl").read_text(), "")
