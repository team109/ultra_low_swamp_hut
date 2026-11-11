import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from ultra_low_hut.verification.measure_orders import PrefixProcess, claim_job, fail_job, protocol_response, reusable_jobs, saved_result_ids, make_plan, measurement_cpus


class MeasurementBehaviorTests(unittest.TestCase):
    def test_cpu_selection_respects_current_allocation(self):
        with patch('ultra_low_hut.verification.measure_orders.os.sched_getaffinity', return_value={2, 3, 4, 8}):
            self.assertEqual(measurement_cpus(None, 2, 2), {2, 3, 4, 8})
            self.assertEqual(measurement_cpus('2-3,8', 3, 1), {2, 3, 8})
            with self.assertRaisesRegex(ValueError, 'outside'):
                measurement_cpus('0-1', 1, 1)
            with self.assertRaisesRegex(ValueError, 'must fit'):
                measurement_cpus('2-3', 3, 1)
            for invalid in ('', '-1', '4-2', '2-3-4'):
                with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                    measurement_cpus(invalid, 1, 1)

    def test_plans_and_resume_isolate_world_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'index.json').write_text(json.dumps(dict(version_groups=[dict(
                files=[dict(file='huts.jsonl')])])) )
            (root / 'huts.jsonl').write_text(json.dumps(dict(seed='123', x=16, z=-32)) + '\n')
            worlds = [dict(world_type='normal'), dict(world_type='large_biomes'),
                      dict(world_type='single_biome', biome='swamp'),
                      dict(world_type='single_biome', biome='desert')]
            plans = [make_plan(root, ['1.21'], **world) for world in worlds]
            self.assertEqual(len({p['jobs'][0]['job_id'] for p in plans}), len(worlds))
            plan = plans[2]
            self.assertEqual(plan['biome'], 'minecraft:swamp')
            row = dict(plan['jobs'][0], policy=plan['policy']['id'], heights=[-57])
            path = root / 'results.jsonl'
            path.write_text(json.dumps(row) + '\n')
            self.assertEqual(reusable_jobs([path], plan, 1)[0], {row['job_id']})
            row['biome'] = 'minecraft:desert'
            path.write_text(json.dumps(row) + '\n')
            with self.assertRaisesRegex(ValueError, 'identity/policy differs'):
                reusable_jobs([path], plan, 1)

    def test_resident_jvm_receives_world_and_rejects_wrong_world(self):
        for wrong in (False, True):
            service = PrefixProcess(Path('.'), 0, '3G', 1, True)
            service.version = '1.21'
            job = dict(job_id='a', version='1.21', seed='1', x=0, z=0,
                       world_type='single_biome', biome='minecraft:swamp')
            response = dict(job, id='a', heights=[-57])
            if wrong:
                response['biome'] = 'minecraft:desert'
            process = Mock()
            process.stdin = io.StringIO()
            process.stdout = io.StringIO(json.dumps(response) + '\n')
            service.process, service.log = process, io.StringIO()
            if wrong:
                with self.assertRaisesRegex(ValueError, 'world configuration'):
                    service.query(job, [()])
            else:
                self.assertEqual(service.query(job, [()])['heights'], [-57])
            sent = json.loads(process.stdin.getvalue())
            self.assertEqual(sent['world_type'], job['world_type'])
            self.assertEqual(sent['biome'], job['biome'])
            service.close()

    def test_reuse_requires_exact_query_policy_and_prefix_shape(self):
        job = dict(job_id='1.21:a', seed='123', x=16, z=-32, version='1.21')
        plan = dict(policy=dict(id='policy'), world_type='normal', jobs=[job])
        row = dict(job, policy='policy', world_type='normal', heights=[-57, None])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'reused.jsonl'
            path.write_text(json.dumps(row) + '\n')
            identities, sources = reusable_jobs([path], plan, 2)
            self.assertEqual(identities, {'1.21:a'})
            self.assertEqual(len(sources), 1)
            row['x'] = 32
            path.write_text(json.dumps(row) + '\n')
            with self.assertRaisesRegex(ValueError, 'identity/policy differs'):
                reusable_jobs([path], plan, 2)
            row['x'], row['heights'] = 16, [-57]
            path.write_text(json.dumps(row) + '\n')
            with self.assertRaisesRegex(ValueError, 'heights are incomplete'):
                reusable_jobs([path], plan, 2)

    def test_protocol_accepts_vanilla_stdout_redirection(self):
        response = dict(id='one', heights=[-57, None])
        self.assertEqual(protocol_response(json.dumps(response)), response)
        self.assertEqual(protocol_response('[20:03:31] [main/INFO]: [STDOUT]: ' + json.dumps(response)), response)
        self.assertIsNone(protocol_response('[main/INFO]: Loaded recipes'))

    def test_worker_failure_stops_other_hosts_claiming(self):
        jobs = [dict(job_id='1.21:a'), dict(job_id='1.21:b')]
        state = dict(next=0, assigned={}, failures={})
        first = claim_job(state, jobs, 'host-a')
        fail_job(state, first['job_id'], 'host-a', RuntimeError('generation failed'))
        self.assertIsNone(claim_job(state, jobs, 'host-b'))
        self.assertEqual(state['next'], 1)
        self.assertIn(first['job_id'], state['failures'])
        state['halted'] = False
        self.assertEqual(claim_job(state, jobs, 'host-c'), jobs[1])

    def test_resume_rejects_partial_jsonl_without_modifying_it(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'results.jsonl'
            text = json.dumps(dict(job_id='a')) + '\n'
            path.write_text(text)
            self.assertEqual(saved_result_ids(path), {'a'})
            partial = text + '{"job_id":'
            path.write_text(partial)
            with self.assertRaisesRegex(ValueError, 'Incomplete result'):
                saved_result_ids(path)
            self.assertEqual(path.read_text(), partial)



if __name__ == '__main__':
    unittest.main()
