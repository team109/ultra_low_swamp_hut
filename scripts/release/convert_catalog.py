"""Publish completed normal-world prefix measurements as hut height lists."""

from pathlib import Path
import sys

sys.path[:0] = [str(Path(__file__).resolve().parents[2] / "src"), str(Path(__file__).resolve().parents[2])]

import argparse
from collections import defaultdict
import json

ROOT = Path(__file__).resolve().parents[2]
from ultra_low_hut.verification.loading_orders import center_prefixes


def encode(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + '\n'


def prepare_catalog(work, queue='measurements'):
    work = Path(work)
    plan = json.loads((work / 'plan.json').read_text())
    expected = {job['job_id']: job for job in plan['jobs']}
    if len(expected) != len(plan['jobs']) or plan['world_type'] != 'normal':
        raise ValueError('Expected unique normal-world jobs')
    prefixes = center_prefixes(plan['policy'])
    count = len(prefixes)
    paths = sorted(work.glob(queue + '*-results-*.jsonl'))
    paths += sorted(work.glob('reused-*.jsonl'))
    rows = {}
    for path in paths:
        for line in path.read_text().splitlines():
            row = json.loads(line)
            identity = row['job_id']
            if identity not in expected or identity in rows:
                raise ValueError('Unexpected or duplicate result: ' + identity)
            job = expected[identity]
            if (row.get('world_type') != 'normal' or row.get('policy') != plan['policy']['id']
                    or any(str(row.get(k)) != str(job[k]) for k in ('seed', 'x', 'z', 'version'))):
                raise ValueError('Result differs from measurement job: ' + identity)
            if (len(row['heights']) != count
                    or any(h is not None and type(h) is not int for h in row['heights'])):
                raise ValueError('Incomplete prefix heights: ' + identity)
            rows[identity] = row
    if set(rows) != set(expected):
        raise ValueError(f'Measurements incomplete: {len(rows)}/{len(expected)}')
    outputs, groups, summaries = {}, [], []
    published_positions, lowest_positions, sensitive_positions = set(), set(), set()
    for interval in plan['intervals']:
        versions = interval['versions']
        directory = versions[0] if len(versions) == 1 else versions[0] + '-' + versions[-1]
        selected = [rows[j['job_id']] for j in plan['jobs'] if j['interval'] == interval['id']]
        buckets, sensitive, absent = defaultdict(list), 0, 0
        for row in selected:
            values = set(row['heights'])
            present = values - {None}
            sensitive += len(values) > 1
            absent += not present
            height = min(present, default=None)
            if height is not None and height <= -55:
                public = {k: row[k] for k in ('seed', 'x', 'z')}
                public['loading_order_affected'] = len(values) > 1
                if public['loading_order_affected']:
                    prefix = min((p for p, h in zip(prefixes, row['heights']) if h == height),
                                 key=lambda p: (len(p), p))
                    directions = ('N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW')
                    public['min_hpos_order'] = ' '.join([directions[i] for i in prefix] + ['C'])
                buckets[height].append(public)
                position = (str(row['seed']), row['x'], row['z'])
                published_positions.add(position)
                if height <= -59:
                    lowest_positions.add(position)
                if public['loading_order_affected']:
                    sensitive_positions.add(position)
        files = []
        for height, bucket in sorted(buckets.items()):
            name = f'{directory}/y{height}.jsonl'
            bucket.sort(key=lambda r: (int(r['seed']), r['x'], r['z']))
            outputs[name] = ''.join(json.dumps(r, separators=(',', ':')) + '\n' for r in bucket)
            files.append(dict(spawn_y=height, file=name, huts=len(bucket)))
        summaries.append(dict(versions=versions, representative=interval['representative'],
                              tested_seed_positions=len(selected), published_huts=sum(map(len, buckets.values())),
                              loading_order_affected=sensitive, absent_huts=absent,
                              published_loading_order_affected=sum(r['loading_order_affected'] for b in buckets.values() for r in b),
                              above_threshold=len(selected)-absent-sum(map(len, buckets.values())),
                              heights={str(h): len(b) for h, b in sorted(buckets.items())}))
        groups.append(dict(directory=directory, versions=versions,
                           verified_versions=[interval['representative']], files=files,
                           world_type='normal', loading_policy=plan['policy']['id'],
                           generation_status='FEATURES', legacy=False, verification='verification.json'))
    summary = dict(world_type='normal', generation_status='FEATURES',
                   loading_policy=plan['policy']['id'], recipes=len(plan['policy']['orders']),
                   distinct_prefixes=count, tested_seed_positions=plan['cases'],
                   candidate_version_pairs=len(rows),
                   published_records=sum(s['published_huts'] for s in summaries),
                   published_sensitive_records=sum(s['published_loading_order_affected'] for s in summaries),
                   unique_published_seed_positions=len(published_positions),
                   unique_minus59_seed_positions=len(lowest_positions),
                   unique_sensitive_seed_positions=len(sensitive_positions), intervals=summaries)
    outputs['verification.json'] = encode(summary)
    outputs['index.json'] = encode(dict(schema=2, world_type='normal',
        columns=['seed', 'x', 'z', 'loading_order_affected', 'min_hpos_order'],
        height='Minimum witch spawning HPos over configured center prefixes',
        loading_policy=plan['policy']['id'], version_groups=groups))
    return outputs, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--source', type=Path, default=ROOT / 'data/huts')
    parser.add_argument('--queue', default='measurements')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    outputs, summary = prepare_catalog(args.work, args.queue)
    if args.apply:
        for name in sorted(outputs, key=lambda name: name == 'index.json'):
            target = args.source / name
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_suffix(target.suffix + '.tmp')
            temporary.write_text(outputs[name])
            temporary.replace(target)
    print(encode(dict(applied=args.apply, **summary)), end='')


if __name__ == '__main__':
    main()
