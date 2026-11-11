import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ultra_low_hut.layouts.terrain_samples import NaturalTerrainSampler
from ultra_low_hut.layouts.prepare_panel import prepare


class NaturalTerrainSamplesTests(unittest.TestCase):
    def test_panel_preparation_preserves_weights_and_localizes_snapshots(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.json"
            config = root / "configuration.json"
            row = dict(id="sample", seed="-42", x=16, z=32,
                       raw_y=-53, trial_weight=0.001,
                       snapshot_file="old-location.bin")
            source.write_text(json.dumps([row]))
            config.write_text(json.dumps(dict(version="1.21", seed_position_trials=1000)))
            output = root / "output"
            with patch("ultra_low_hut.layouts.prepare_panel.subprocess.run") as run:
                path = prepare(source, config, output,
                               dict(agent="agent.jar", classpath="classes"))
            result = json.loads(path.read_text())[0]
            self.assertEqual(result["trial_weight"], row["trial_weight"])
            self.assertEqual(result["seed"], row["seed"])
            self.assertEqual(result["snapshot_file"], "snapshots/0000.bin")
            runtime = json.loads((output / "capture-panel.json").read_text())[0]
            self.assertEqual(Path(runtime["snapshot_file"]), output / result["snapshot_file"])
            self.assertIn("NaturalTerrainSnapshot", run.call_args.args[0])

    def test_changed_panel_is_rejected_without_modifying_existing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.json"
            config = root / "configuration.json"
            row = dict(id="sample", seed="-42", x=16, z=32, raw_y=-53)
            source.write_text(json.dumps([row]))
            config.write_text(json.dumps(dict(version="1.21", seed_position_trials=1000)))
            output = root / "output"
            with patch("ultra_low_hut.layouts.prepare_panel.subprocess.run"):
                prepare(source, config, output, dict(agent="agent.jar", classpath="classes"))
            snapshot = output / "snapshots/0000.bin"
            snapshot.write_bytes(b"original snapshot")
            before = {p: p.read_bytes() for p in output.rglob("*") if p.is_file()}
            source.write_text(json.dumps([dict(row, seed="43")]))
            with patch("ultra_low_hut.layouts.prepare_panel.subprocess.run") as run:
                with self.assertRaisesRegex(ValueError, "different terrain panel"):
                    prepare(source, config, output, {})
                run.assert_not_called()
            self.assertEqual(before, {p: p.read_bytes() for p in output.rglob("*") if p.is_file()})

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
