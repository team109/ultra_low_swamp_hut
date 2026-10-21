import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT)]
from tools.search_huts import completed_record_count
from screening_pipeline import ScreeningPipeline


class ScreeningResumeTests(unittest.TestCase):
    def test_counter_ignores_an_uncommitted_trailing_record(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "completed.jsonl"
            path.write_bytes(b'{"index":0}\n{"index":1}\n{"index":')
            self.assertEqual(completed_record_count(path), 2)

    def test_persistent_job_preserves_original_indices_when_resuming(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            geometry = root / "geometry.json"
            geometry.write_text(json.dumps([{"low48": str(i)} for i in range(7)]))
            skip = root / "skip.json"
            skip.write_text("[0,2,5]")
            pipeline = object.__new__(ScreeningPipeline)

            def screen(rows):
                for index, row in rows:
                    yield dict(
                        index=index,
                        refined=[],
                        noise_candidates=0,
                        room_rejected=0,
                        gpu_and_transfer_seconds=0.0,
                        reference_seconds=0.0,
                        room_gate_stages={},
                        screens=[dict(counts=dict(upper16=65536))],
                    ), []

            pipeline.screen = screen
            summary = pipeline.run_job(geometry, root / "job", skip)
            records = [
                json.loads(line)
                for line in (root / "job/completed.jsonl").read_text().splitlines()
            ]
            self.assertEqual([r["index"] for r in records], [1, 3, 4, 6])
            self.assertEqual(summary["upper16_trials"], 4 * 65536)
            self.assertEqual(summary["status"], "completed")
