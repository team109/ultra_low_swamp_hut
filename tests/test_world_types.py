"""World configurations must reach both discovery and verification unchanged."""

import json
import ctypes as C
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
import tests
from ultra_low_hut._native import LIB
from ultra_low_hut.world_types import config_world, noise_specs_for_world, world_config


class WorldTypeTests(unittest.TestCase):
    def setUp(self):
        (ROOT / ".local").mkdir(parents=True, exist_ok=True)

    def test_empty_world_campaign_finishes_all_layouts_and_does_not_restart(self):
        from ultra_low_hut.search import campaign as search_layout_pool

        with tempfile.TemporaryDirectory(dir=ROOT / ".local") as temp:
            directory = Path(temp)
            pool = directory / "pool.json"
            pool.write_text(json.dumps(json.loads((ROOT / "data/mineshafts/templates.json").read_text())[:2]))
            root = directory / "campaign"
            def launch(command, **kwargs):
                run = Path(command[command.index("--root") + 1])
                run.mkdir(parents=True)
                (run / "STOPPED.json").write_text(json.dumps({
                    "reason": "world-has-no-witch-huts", "seed_position_trials": 0}))
                return SimpleNamespace(pid=999999999, poll=lambda: 0, returncode=0)
            argv = ["search_layout_pool", "--root", str(root), "--layout-pool", str(pool),
                    "--devices", "0", "--world-type", "single_biome", "--biome", "desert", "--accept-eula"]
            with mock.patch.object(sys, "argv", argv), mock.patch.object(search_layout_pool.signal, "signal"), \
                 mock.patch.object(search_layout_pool.subprocess, "Popen", side_effect=launch) as launched:
                search_layout_pool.main()
                self.assertEqual(launched.call_count, 1)
                argv.append("--resume")
                launched.reset_mock()
                search_layout_pool.main()
                launched.assert_not_called()
            state = json.loads((root / "state.json").read_text())
            self.assertEqual(state["status"], "world-has-no-witch-huts")
            self.assertTrue(all(p["status"] == state["status"] for p in state["phases"]))
            self.assertEqual(json.loads((root / "STOPPED.json").read_text())["reason"], state["status"])


    @unittest.skipUnless(LIB.exists(),
                         "Build the CPU world-types library first")
    def test_cpu_world_noise_changes_and_fixed_biome_bypasses_climate(self):
        from ultra_low_hut.search.reference.native import Context

        terrain = {}
        for kind, biome in (("normal", None), ("large_biomes", None),
                            ("single_biome", "swamp"), ("single_biome", "desert")):
            with Context(1, "1.21", world_type=kind, biome=biome) as context:
                probe = context.lib.ms_terrain_probe
                probe.argtypes = [C.c_void_p, C.c_int, C.c_int, C.POINTER(C.c_int)]
                output = (C.c_int * 2)()
                self.assertEqual(probe(context.handle, 16384, 32768, output), 0)
                terrain[kind, biome] = tuple(output)
                if kind == "single_biome":
                    result = context.screen_hut(16384, 32768, -40)
                    self.assertEqual(result["biome"], 6 if biome == "swamp" else -1)
                    if biome == "desert":
                        self.assertFalse(result["accepted"])
        self.assertNotEqual(terrain["normal", None], terrain["large_biomes", None])
        self.assertEqual(terrain["normal", None], terrain["single_biome", "swamp"])

    def test_cpu_library_selection_is_independent_of_import_order(self):
        from ultra_low_hut import _native

        loaded = {}
        def load(path):
            functions = {name: mock.Mock() for name in
                         ("ms_open", "ms_close", "ms_error", "ms_hut", "ms_hut_screen")}
            loaded[path] = SimpleNamespace(**functions)
            return loaded[path]
        with mock.patch.object(_native, "_libraries", {}), \
             mock.patch.object(_native.C, "CDLL", side_effect=load) as open_library, \
             mock.patch.dict(_native.os.environ, {"MCSEARCH_LIBRARY": "first-cpu.so"}):
            first = _native.library()
            with mock.patch.dict(_native.os.environ, {"MCSEARCH_LIBRARY": "second-cpu.so"}):
                second = _native.library()
                self.assertIsNot(first, second)
                self.assertIs(_native.library("first-cpu.so"), first)
                second.ms_error.return_value = b"selected library error"
                with self.assertRaisesRegex(RuntimeError, "selected library error"):
                    _native.check(-1, second)
            self.assertIs(_native.library(), first)
            self.assertEqual(open_library.call_count, 2)

    def test_invalid_combinations_are_rejected_before_work(self):
        for kind, biome in (("default", None), ("normal", "swamp"),
                            ("large_biomes", "swamp"), ("single_biome", "Bad biome")):
            with self.subTest(kind=kind, biome=biome), self.assertRaises(ValueError):
                world_config(kind, biome)
        self.assertEqual(world_config("single_biome", "swamp"),
                         {"world_type": "single_biome", "biome": "minecraft:swamp"})
        self.assertEqual(config_world({}), {"world_type": "normal"})

    def test_large_specs_change_seed_namespace_and_octave_not_coordinate_only(self):
        specs = {n["name"].split(":")[1]: n for n in json.loads(
            (ROOT / "data/noises/seed-specs26.json").read_text())["noises"]}
        frozen = json.dumps(specs, sort_keys=True)
        large = noise_specs_for_world(specs, "large_biomes")
        for name in ("erosion", "temperature", "continentalness"):
            self.assertNotEqual(large[name]["name"], specs[name]["name"])
            for before, after in zip(specs[name]["layers"], large[name]["layers"]):
                self.assertEqual(int(after["octave"][7:]), int(before["octave"][7:]) - 2)
                self.assertEqual(after["frequency"] * 4, before["frequency"])
                self.assertEqual(after["amplitude"], before["amplitude"])
        for name in set(specs) - {"erosion", "temperature", "continentalness"}:
            self.assertEqual(large[name], specs[name])
        self.assertEqual(json.dumps(specs, sort_keys=True), frozen)
        self.assertEqual(noise_specs_for_world(specs, "single_biome"), specs)

    def test_campaign_forwards_world_and_refuses_mixed_resume(self):
        local = ROOT / ".local"
        for kind in ("large_biomes", "single_biome"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory(dir=local) as temp:
                root = Path(temp) / "campaign"
                command = [sys.executable, str(ROOT / "scripts/campaign.py"),
                           "--root", str(root), "--layout-pool",
                           str(ROOT / "data/mineshafts/templates.json"), "--plan-only",
                           "--devices", "0", "--world-type", kind]
                if kind == "single_biome":
                    command += ["--biome", "swamp"]
                subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
                plan = json.loads((root / "plan.json").read_text())
                world = world_config(kind, "swamp" if kind == "single_biome" else None)
                self.assertEqual(config_world(plan["config"]), world)
                child = plan["phases"][0]["command"]
                self.assertEqual(child[child.index("--world-type") + 1], kind)
                if kind == "single_biome":
                    self.assertEqual(child[child.index("--biome") + 1], "minecraft:swamp")
                changed = [sys.executable, str(ROOT / "scripts/campaign.py"),
                           "--root", str(root), "--plan-only", "--world-type", "normal"]
                result = subprocess.run(changed, cwd=ROOT, capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("different world configuration", result.stderr)


if __name__ == "__main__":
    unittest.main()
