import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from natural_terrain_samples import NaturalTerrainSampler


class NaturalTerrainSamplesTests(unittest.TestCase):
    def test_recovery_uses_committed_search_records(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            job = root / "search"
            job.mkdir()
            sample = dict(seed="-42", x=16, z=32, raw_y=-53, version="1.21")
            journal = [dict(index=0), dict(index=1, natural_samples=[sample])]
            (job / "completed.jsonl").write_text(
                "".join(json.dumps(r) + "\n" for r in journal) + '{"index":2'
            )
            output = root / "samples"
            output.mkdir()
            (output / "jobs.json").write_text(json.dumps([str(job)]))
            sampler = NaturalTerrainSampler(output, "1.21", -46, 3 * 65536)
            self.assertEqual(sampler.trials, 2 * 65536)
            self.assertTrue(sampler.start_root())
            self.assertFalse(sampler.start_root())
            sampler.commit([sample])
            sampler.close()
            rows = (output / "samples.jsonl").read_text().splitlines()
            self.assertEqual([json.loads(r) for r in rows], [sample])

    def test_observation_uses_no_layout_condition(self):
        class Terrain:
            def screen_hut(self, x, z, threshold):
                self.query = x, z, threshold
                return dict(accepted=True, y=-47)

        with tempfile.TemporaryDirectory() as directory:
            sampler = NaturalTerrainSampler(directory, "1.21", -46, 65536)
            terrain = Terrain()
            candidate = dict(seed="123", x=0, z=16)
            self.assertEqual(sampler.observe(terrain, candidate)["raw_y"], -47)
            self.assertEqual(terrain.query, (0, 16, -46))
            sampler.close()
