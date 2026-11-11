import json
from pathlib import Path
import tempfile
import threading
import unittest

from ultra_low_hut.verification.loading_orders import APPROACHES, LOADING_POLICY, FEATURES_POLICY, legacy_feature_spec, aggregate_loading_orders
from unittest.mock import patch
from ultra_low_hut.verification.client import VerificationGroup, loading_order_fields
from ultra_low_hut.search.export import export_results
from ultra_low_hut.search.log import SearchLog
from ultra_low_hut.verification.pool import QueryPool


def response(heights=None, version="1.21"):
    heights = heights or dict.fromkeys(APPROACHES, [-59])
    return aggregate_loading_orders({
        a: dict(seed="-123", x=16, z=-32, version=version, controlled=False,
                loading_policy=LOADING_POLICY, approach=a, world_reused=False,
                heights=heights[a], seconds=1)
        for a in APPROACHES
    })


class LoadingOrderTests(unittest.TestCase):
    def test_features_requires_actual_order_and_rejects_mixed_policies(self):
        orders = response()["loading_orders"]
        fixture = legacy_feature_spec()
        fixture["id"] = FEATURES_POLICY
        for order in fixture["orders"]:
            result = orders[order["id"]]
            sequence = [[1+dx, -2+dz] for dx, dz in order["offsets"]]
            result.update(loading_policy=FEATURES_POLICY, generation_status="FEATURES",
                          requested_chunk_order=sequence,
                          actual_decoration_order=sequence)
        with patch("ultra_low_hut.verification.loading_orders.ORDER_SPEC", fixture):
            self.assertEqual(aggregate_loading_orders(orders)["loading_policy"], FEATURES_POLICY)
            orders["east"]["actual_decoration_order"] = list(reversed(orders["east"]["requested_chunk_order"]))
            with self.assertRaises(ValueError):
                aggregate_loading_orders(orders)
            orders["east"]["actual_decoration_order"] = orders["east"]["requested_chunk_order"]
            orders["north"]["loading_policy"] = LOADING_POLICY
            with self.assertRaises(ValueError):
                aggregate_loading_orders(orders)

    def test_batch_fills_workers_across_candidate_boundaries(self):
        with tempfile.TemporaryDirectory() as directory:
            pool = QueryPool(directory, "1.21", "java", workers=2, generation_mode="full")
            barrier = threading.Barrier(2, timeout=2)

            def query(request):
                barrier.wait()
                return dict(seed=request['seed'], x=16, z=-32, version='1.21',
                            controlled=False, loading_policy=LOADING_POLICY,
                            approach=request['approach'], world_reused=False,
                            heights=[-59],seconds=1)

            pool.query = query
            try:
                r = pool.process(dict(requests=[dict(seed=s,loading_orders=True) for s in ['1','2']]))
                self.assertEqual([one['seed'] for one in r['responses']], ['1','2'])
                self.assertEqual([one['min_hpos'] for one in r['responses']], [-59,-59])
            finally:
                pool.close()

    def test_minimum_and_all_tied_directions(self):
        r = response(dict(center=[-58], north=[-59], east=[-59], south=[-57], west=[-58]))
        self.assertEqual(r["heights"], [-59])
        self.assertEqual(r["min_hpos_approaches"], ["north", "east"])
        self.assertTrue(r["loading_order_affected"])

    def test_stable_and_no_hut_results(self):
        stable = response()
        self.assertFalse(stable["loading_order_affected"])
        self.assertEqual(stable["min_hpos_approaches"], list(APPROACHES))
        empty = response(dict.fromkeys(APPROACHES, []))
        self.assertIsNone(empty["min_hpos"])
        self.assertEqual(empty["heights"], [])
        self.assertEqual(empty["min_hpos_approaches"], [])

    def test_partial_failed_or_reused_results_are_not_accepted(self):
        orders = response()["loading_orders"]
        del orders["west"]
        with self.assertRaises(ValueError):
            aggregate_loading_orders(orders)
        orders = response()["loading_orders"]
        orders["east"]["error"] = "failed"
        with self.assertRaises(RuntimeError):
            aggregate_loading_orders(orders)
        orders = response()["loading_orders"]
        orders["north"]["world_reused"] = True
        with self.assertRaises(ValueError):
            aggregate_loading_orders(orders)

    def test_search_accepts_single_passing_direction_and_preserves_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "inbox").mkdir()
            (root / "outbox").mkdir()
            group = VerificationGroup(["1.21"], {"1.21": root}, loading_policy=LOADING_POLICY)
            candidate = dict(seed="-123", x=16, z=-32, geometry=dict(width=7))
            active = group.submit(candidate, lambda p, r: p.write_text(json.dumps(r)))
            self.assertTrue(json.loads((root / "inbox" / active[0]).read_text())["loading_orders"])
            r = response(dict(center=[-58], north=[-58], east=[-59], south=[-58], west=[-58]))
            path = root / "outbox" / active[0]
            path.write_text(json.dumps(r))
            grouped, responses = group.collect(active)
            self.assertEqual(grouped, {-59: ["1.21"]})
            fields = loading_order_fields(responses, ["1.21"])
            self.assertEqual(fields["min_hpos_approaches"], {"1.21": ["east"]})
            self.assertTrue(fields["loading_order_affected"])
            row = dict(candidate, version="1.21", versions=["1.21"], HPos=-59,
                       excavation=321, verified_at=100,
                       campaign_trials_observed_at_verification=65536, **fields)
            log = SearchLog(root, 40)
            log.discovery(row)
            public = json.loads((root / "results.jsonl").read_text())
            self.assertEqual(public["spawn_y"], -59)
            self.assertEqual(public["min_hpos_approaches"], {"1.21": ["east"]})
            (root / "low-huts.jsonl").write_text(json.dumps(row)+"\n")
            exported = export_results(root)[0]
            self.assertEqual(exported["height"], -59)
            self.assertEqual(exported["loading_order_heights"], fields["loading_order_heights"])
            r["heights"] = [-58]
            path.write_text(json.dumps(r))
            with self.assertRaises(RuntimeError):
                group.collect(active)


if __name__ == "__main__":
    unittest.main()
