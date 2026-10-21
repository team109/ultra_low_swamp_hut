"""Contracts for published templates and fixed-budget natural-yield measurement."""

import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT)]
from layout_placement import PlacementWorker, read_layouts
from measure_layout_yields import measure
from select_layout import select
from search_huts import load_layout_template


class LayoutMeasurementTests(unittest.TestCase):
    def test_published_templates_can_be_selected_for_search(self):
        catalog = ROOT / "data/mineshafts/1.21/templates.json"
        metrics = [
            json.loads(line)
            for line in (catalog.parent / "layouts.jsonl").read_text().splitlines()
        ]
        self.assertEqual(
            {row["target"] for row in read_layouts(catalog)},
            {row["layout_seed"] for row in metrics},
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "selected.json"
            for metric in metrics:
                output.write_text(
                    json.dumps(select(catalog, int(metric["layout_seed"])))
                )
                template, _ = load_layout_template(output)
                self.assertEqual(template["target"], metric["layout_seed"])

    def test_placement_client_uses_the_java_classpath(self):
        process = Mock()
        process.stdout = io.StringIO('{"ready":true}\n')
        process.poll.return_value = 0
        with tempfile.TemporaryDirectory() as directory:
            with patch(
                "layout_placement.subprocess.Popen", return_value=process
            ) as launch:
                worker = PlacementWorker(
                    {"agent": "agent.jar", "classpath": "classes"},
                    Path("panel.json"),
                    "java",
                    Path(directory),
                )
                command = launch.call_args.args[0]
                self.assertEqual(command[command.index("-cp") + 1], "classes")
                worker.close()

    def test_fixed_draws_use_terrain_weights_and_report_excavation(self):
        requests = []

        class Context:
            def __init__(self, *args):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def room_budget(self, *args):
                return {"passed": True}

        class Worker:
            def __init__(self, *args):
                self.process = Mock(stdin=io.StringIO())

            def receive(self):
                request = json.loads(self.process.stdin.getvalue().splitlines()[-1])
                requests.append(request)
                return {
                    "target": request["layout"]["target"],
                    "n": request["n"],
                    "hits59": 128 if request["counts"][0] else 64,
                }

            def close(self):
                pass

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = root / "terrain.bin"
            snapshot.write_bytes((bytes([1]) * 10 + bytes(374)) * 256)
            panel = root / "panel.json"
            panel.write_text(
                json.dumps(
                    [
                        {
                            "id": str(i),
                            "seed": str(i),
                            "x": 0,
                            "z": 0,
                            "raw_y": -54,
                            "snapshot_file": "terrain.bin",
                            "trial_weight": weight,
                        }
                        for i, weight in enumerate([0.0001, 0.0004])
                    ]
                )
            )
            (root / "configuration.json").write_text(
                json.dumps(
                    {
                        "seed_position_trials": 1000000,
                        "raw_height_max": -46,
                        "gate_budget": -57,
                        "reference_max_y": -48,
                    }
                )
            )
            layout = {
                "target": "1",
                "width": 7,
                "relx": 0,
                "relz": 0,
                "coordinate_regions_mask": 256,
            }
            clearing = [((1 << 10) - 1) & ~((1 << 5) - 1)] * 63
            with patch("measure_layout_yields.Context", Context), patch(
                "measure_layout_yields.PlacementWorker", Worker
            ), patch("measure_layout_yields.room_geometry", return_value=None), patch(
                "measure_layout_yields.mineshaft_clearing_masks", return_value=clearing
            ):
                result = measure([layout], panel, root / "output", {}, workers=1)[0]
            self.assertEqual([request["n"] for request in requests], [256, 256])
            self.assertEqual(result["excavation"], 315)
            self.assertAlmostEqual(result["expected59_per_trillion_trials"], 150000000)
            row = json.loads((root / "output/results.jsonl").read_text())
            self.assertEqual(
                list(row)[:3],
                ["layout_seed", "excavation", "expected59_per_trillion_trials"],
            )


if __name__ == "__main__":
    unittest.main()
