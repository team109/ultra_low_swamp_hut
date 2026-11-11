import json
from pathlib import Path
import tempfile
import unittest

from scripts.release.convert_catalog import prepare_catalog


class CatalogTests(unittest.TestCase):
    def test_sensitive_huts_include_an_order_attaining_the_published_height(self):
        offsets = [[0, 0], [0, -1], [1, -1], [1, 0], [1, 1], [0, 1], [-1, 1], [-1, 0], [-1, -1]]
        orders = [dict(id="center", offsets=offsets),
                  dict(id="north", offsets=[offsets[1], offsets[0], *offsets[2:]])]
        jobs = [dict(job_id=str(i), seed=str(i), x=16, z=-32,
                     version="1.21", interval="one") for i in range(3)]
        plan = dict(world_type="normal", cases=3, jobs=jobs,
                    policy=dict(id="policy", orders=orders),
                    intervals=[dict(id="one", versions=["1.21"], representative="1.21")])
        rows = [dict(job, world_type="normal", policy="policy", heights=heights)
                for job, heights in zip(jobs, [[-56, -59], [-59, -59], [None, None]])]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "plan.json").write_text(json.dumps(plan))
            (root / "measurements-results-test.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in rows))
            outputs, summary = prepare_catalog(root)
        published = [json.loads(line) for line in outputs["1.21/y-59.jsonl"].splitlines()]
        self.assertEqual(published[0]["min_hpos_order"], "N C")
        self.assertNotIn("min_hpos_order", published[1])
        self.assertEqual(summary["published_records"], 2)
        self.assertEqual(summary["intervals"][0]["absent_huts"], 1)
