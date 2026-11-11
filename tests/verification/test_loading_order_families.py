import json
from pathlib import Path
import tempfile
import unittest

from ultra_low_hut.verification.loading_orders import (
    center_prefixes, order_work, load_order_spec, structured_order_spec,
)


class StructuredOrderTests(unittest.TestCase):
    def test_direction_file_is_the_input_and_validates_each_order(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'orders.txt'
            path.write_text('# editable\nN NE E SE S SW W NW C\n')
            spec = structured_order_spec(path)
            self.assertEqual(load_order_spec(path), spec)
            self.assertEqual(len(spec['orders']), 1)
            self.assertEqual(spec['orders'][0]['offsets'][0], [0, -1])
            self.assertEqual(center_prefixes(spec), (tuple(range(8)),))
            manifest = Path(directory) / 'orders.json'
            manifest.write_text(json.dumps(dict(schema=spec['schema'], id=spec['id'],
                                                orders_sha256=spec['orders_sha256'], orders_file='orders.txt')))
            self.assertEqual(load_order_spec(manifest)['orders'], spec['orders'])
            path.write_text('C N NE E SE S SW W NW\n')
            with self.assertRaisesRegex(ValueError, 'manifest does not match'):
                load_order_spec(manifest)
            manifest.write_text(json.dumps(dict(schema=spec['schema'], orders_file='orders.txt')))
            changed = load_order_spec(manifest)
            self.assertNotEqual(changed['id'], spec['id'])
            self.assertEqual(changed['orders'][0]['offsets'][0], [0, 0])
            path.write_text('N NE E SE S SW W NW N\n')
            with self.assertRaisesRegex(ValueError, 'each order'):
                structured_order_spec(path)

    def test_center_prefixes_merge_suffixes_and_count_shared_work(self):
        # Two paths share N, while two orders differ only after the center.
        spec = dict(orders=[
            dict(offsets=[[0, 0], [0, -1]]),
            dict(offsets=[[0, -1], [0, 0], [1, 0]]),
            dict(offsets=[[0, -1], [0, 0], [-1, 0]]),
            dict(offsets=[[0, -1], [1, 0], [0, 0]]),
        ])
        self.assertEqual(center_prefixes(spec), ((), (0,), (0, 2)))
        work = order_work(spec)
        self.assertEqual(work["prefixes"], 3)
        self.assertEqual(work["shared_steps"], 5)
        self.assertLess(work["shared_steps"], sum(len(prefix) + 1 for prefix in center_prefixes(spec)))


if __name__ == '__main__':
    unittest.main()
