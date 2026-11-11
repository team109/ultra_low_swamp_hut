import json
from pathlib import Path
import tempfile
import unittest

from ultra_low_hut.search.export import export_results
from ultra_low_hut.verification.loading_orders import aggregate_loading_orders, get_order_spec
from ultra_low_hut.search.log import SearchLog
from ultra_low_hut.verification.client import VerificationGroup


class VerificationProfileTests(unittest.TestCase):
    def test_client_normalizes_and_validates_single_biome(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "inbox").mkdir()
            (root / "ready.json").write_text(json.dumps(dict(
                loading_policy=get_order_spec("on")["id"],
                biomes=["minecraft:swamp", "minecraft:desert"])))
            candidate = dict(seed="123", x=16, z=-32, geometry=dict(width=7))
            names = set()
            for kind, biome in (("normal", None), ("large_biomes", None),
                                ("single_biome", "swamp"), ("single_biome", "desert")):
                group = VerificationGroup(["1.21"], {"1.21": root}, world_type=kind, biome=biome)
                self.assertTrue(group.ready())
                active = group.submit(candidate, lambda p, v: p.write_text(json.dumps(v)))
                self.assertNotIn(active[0], names)
                names.add(active[0])
                request = json.loads((root / "inbox" / active[0]).read_text())
                self.assertEqual(request["world_type"], kind)
                if biome:
                    self.assertEqual(request["biome"], "minecraft:" + biome)
            group = VerificationGroup(["1.21"], {"1.21": root}, world_type="single_biome", biome="missing")
            with self.assertRaisesRegex(ValueError, "Unknown biome"):
                group.ready()

    def test_on_round_trip_uses_the_configured_orders_and_identity(self):
        spec = get_order_spec("on")
        candidate = dict(seed="123", x=16, z=-32, geometry=dict(width=7))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "inbox").mkdir()
            (root / "outbox").mkdir()
            (root / "ready.json").write_text(json.dumps(dict(
                loading_policy=get_order_spec("on")["id"])))
            group = VerificationGroup(["1.21"], {"1.21": root}, verification_mode="on")
            self.assertTrue(group.ready())
            active = group.submit(candidate, lambda path, value: path.write_text(json.dumps(value)))
            request = json.loads((root / "inbox" / active[0]).read_text())
            self.assertEqual(request["loading_order_profile"], "on")
            results = {}
            for index, order in enumerate(spec["orders"]):
                sequence = [[1 + dx, -2 + dz] for dx, dz in order["offsets"]]
                results[order["id"]] = dict(
                    seed="123", x=16, z=-32, version="1.21", controlled=False,
                    world_type="normal", world_reused=False, loading_policy=spec["id"],
                    approach=order["id"], generation_status="FEATURES",
                    requested_chunk_order=sequence, actual_decoration_order=sequence,
                    heights=[-59 if index == 0 else -57], seconds=1)
            response = dict(aggregate_loading_orders(results, spec=spec), verification_mode="on")
            (root / "outbox" / active[0]).write_text(json.dumps(response))
            self.assertEqual(group.collect(active)[0], {-59: ["1.21"]})
            response["verification_mode"] = "off"
            (root / "outbox" / active[0]).write_text(json.dumps(response))
            with self.assertRaisesRegex(RuntimeError, "mode mismatch"):
                group.collect(active)

    def test_native_candidates_are_not_exported_or_published(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            native = dict(seed="123", x=0, z=0, native_y=-60, verification_mode="off")
            (root / "low-huts.jsonl").write_text(json.dumps(native) + "\n")
            self.assertEqual(export_results(root), [])
            log = SearchLog(root, 0)
            with self.assertRaisesRegex(ValueError, "Unverified"):
                log.discovery(native)
            self.assertEqual((root / "results.jsonl").read_text(), "")


if __name__ == "__main__":
    unittest.main()
