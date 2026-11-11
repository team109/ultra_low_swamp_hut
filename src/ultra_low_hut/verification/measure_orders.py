"""Plan and resume CPU measurements of structured loading-order prefixes."""
import argparse
import concurrent.futures
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import threading
import time

from ultra_low_hut import ROOT
from ultra_low_hut.versions import catalog, resolve
from ultra_low_hut.world_types import WORLD_TYPES, config_world, world_config
from ultra_low_hut.verification.loading_orders import center_prefixes, get_order_spec, structured_order_spec


def atomic(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


def case_id(row):
    return hashlib.sha256(f"{row['seed']}:{row['x']}:{row['z']}".encode()).hexdigest()[:20]


def all_prefixes(prefix=(), remaining=tuple(range(8))):
    yield prefix
    for index in remaining:
        yield from all_prefixes(prefix + (index,), tuple(i for i in remaining if i != index))


def saved_result_ids(path):
    saved = set()
    if path.exists():
        with path.open() as stream:
            for number, line in enumerate(stream, 1):
                try:
                    identity = json.loads(line)['job_id']
                except (json.JSONDecodeError, KeyError) as error:
                    raise ValueError(f'Incomplete result at {path}:{number}; preserve and inspect it before resume') from error
                if identity in saved:
                    raise ValueError('Duplicate saved result: ' + identity)
                saved.add(identity)
    return saved


def protocol_response(line):
    """Accept raw JSON or vanilla Bootstrap's redirected stdout prefix."""
    candidates = [line]
    marker = '[STDOUT]: '
    if marker in line:
        candidates.insert(0, line.split(marker, 1)[1])
    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


def reusable_jobs(paths, plan, prefix_count):
    expected = {job['job_id']: job for job in plan['jobs']}
    identities, sources = set(), {}
    for path in paths:
        raw = path.read_bytes()
        sources[str(path.resolve())] = hashlib.sha256(raw).hexdigest()
        for number, line in enumerate(raw.decode().splitlines(), 1):
            row = json.loads(line)
            identity = row.get('job_id')
            if identity not in expected or identity in identities:
                raise ValueError(f'{path}:{number}: unknown or duplicate reused job')
            job = expected[identity]
            if (row.get('policy') != plan['policy']['id'] or config_world(row) != config_world(plan)
                    or any(str(row.get(k)) != str(job[k]) for k in ('seed', 'x', 'z', 'version'))):
                raise ValueError(f'{path}:{number}: reused query identity/policy differs')
            heights = row.get('heights')
            if (not isinstance(heights, list) or len(heights) != prefix_count
                    or any(h is not None and type(h) is not int for h in heights)):
                raise ValueError(f'{path}:{number}: reused prefix heights are incomplete')
            identities.add(identity)
    return identities, sources


def claim_job(state, jobs, host, stopped=False):
    if stopped or state.get('halted'):
        return None
    if state.get('retry'):
        identity = state['retry'].pop(0)
        job = next(j for j in jobs if j['job_id'] == identity)
    elif state['next'] < len(jobs):
        job = jobs[state['next']]
        state['next'] += 1
    else:
        return None
    state['assigned'][job['job_id']] = dict(host=host, pid=os.getpid(), started=time.time())
    return job


def fail_job(state, identity, host, error):
    state['assigned'].pop(identity)
    state['failures'][identity] = dict(error=repr(error), host=host)
    state['halted'] = True


def make_plan(source, versions=None, case_limit=None, orders=None, *, world_type="normal", biome=None):
    world = world_config(world_type, biome)
    index = json.loads((source / 'index.json').read_text())
    cases = {}
    for group in index['version_groups']:
        for entry in group['files']:
            for line in (source / entry['file']).read_text().splitlines():
                row = json.loads(line)
                identity = case_id(row)
                cases[identity] = dict(id=identity, seed=str(row['seed']), x=row['x'], z=row['z'])
    selected = sorted(cases.values(), key=lambda row: row['id'])
    if case_limit is not None:
        selected = selected[:case_limit]
    intervals = catalog()['intervals']
    if versions:
        requested = {resolve(v)['id'] for v in versions}
        intervals = [r for r in intervals if r['id'] in requested]
    world_suffix = ('' if world['world_type'] == 'normal' else ':' + hashlib.sha256(
        json.dumps(world, sort_keys=True).encode()).hexdigest()[:12])
    jobs = [dict(case, **world, version=r['representative'], interval=r['id'], versions=r['versions'],
                 job_id=r['representative'] + ':' + case['id'] + world_suffix)
            for r in intervals for case in selected]
    return dict(schema='hut-prefix-measurements-v1', **world,
                policy=get_order_spec('on') if orders is None else structured_order_spec(orders), cases=len(selected),
                intervals=[dict(id=r['id'], representative=r['representative'], versions=r['versions'])
                           for r in intervals], jobs=jobs)


def extract_matrix(work, matrix_path):
    """Reuse already measured 1.21 heights in the current policy's order."""
    plan = json.loads((work / 'plan.json').read_text())
    if config_world(plan) != {'world_type': 'normal'}:
        raise ValueError('The archived matrix is for normal worlds only')
    selected = center_prefixes(plan['policy'])
    index = {prefix: i for i, prefix in enumerate(all_prefixes())}
    positions = [index[p] for p in selected]
    with gzip.open(matrix_path, 'rt') as stream:
        matrix = json.load(stream)
    if (matrix.get('version'), matrix.get('world_type'), matrix.get('order_count')) != ('1.21', 'normal', 109601):
        raise ValueError('Expected the complete normal-world 1.21 matrix')
    jobs = {j['id']: j for j in plan['jobs'] if j['version'] == '1.21'}
    rows = {case_id(row): row for row in matrix['cases']}
    if set(jobs) != set(rows):
        raise ValueError('Matrix and measurement cohort differ')
    output = work / 'reused-1.21.jsonl'
    if output.exists():
        raise ValueError('Extracted results already exist: ' + str(output))
    temporary = output.with_suffix('.jsonl.tmp')
    targets = covered = sensitive = 0
    with temporary.open('x') as stream:
        for identity, job in jobs.items():
            original = rows[identity]['heights']
            if len(original) != 109601:
                raise ValueError('Incomplete matrix row')
            heights = [original[i] for i in positions]
            truth, seen = set(original) - {None}, set(heights) - {None}
            targets += len(truth)
            covered += len(truth & seen)
            sensitive += len(set(heights)) > 1
            stream.write(json.dumps(dict(job_id=job['job_id'], version='1.21', interval=job['interval'],
                seed=job['seed'], x=job['x'], z=job['z'], policy=plan['policy']['id'],
                world_type='normal', heights=heights, reused=True), separators=(',', ':')) + '\n')
    temporary.replace(output)
    print(json.dumps(dict(cases=len(jobs), prefixes=len(selected), height_targets=targets,
                          heights_covered=covered, sensitive=sensitive, output=str(output))))


class PrefixProcess:
    """One warm JVM; changing version replaces the process."""
    def __init__(self, work, slot, heap, cpu_per_jvm, reuse_prefixes, queue='service', affinity=None,
                 build_root=None, java_options=()):
        self.work, self.slot, self.heap = work, slot, heap
        self.cpu_per_jvm, self.reuse_prefixes = cpu_per_jvm, reuse_prefixes
        self.queue, self.affinity = queue, affinity
        self.build_root = Path(build_root) if build_root is not None else work / 'build'
        self.java_options = tuple(java_options)
        self.process = self.log = self.version = None

    def close(self):
        if self.process is not None:
            process, self.process = self.process, None
            try:
                try:
                    process.stdin.close()
                except (BrokenPipeError, OSError):
                    pass
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    try:
                        process.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
            finally:
                if process.stdout is not None:
                    process.stdout.close()
                if self.log is not None:
                    self.log.close()
                self.version = None

    def query(self, job, prefixes):
        if self.version != job['version']:
            self.close()
            self.version = job['version']
            build = json.loads((self.build_root / 'versions' / self.version / 'prefix-build.json').read_text())
            java = build.get('java') or 'java'
            command = [java, *self.java_options, '-XX:ActiveProcessorCount=' + str(self.cpu_per_jvm), '-Xmx' + self.heap,
                       '-javaagent:' + build['agent'], '-Dhut.service.version=' + self.version,
                       '-cp', build['classpath'], build.get('main', 'FeatureOrderEnumerator121'), '--serve']
            if self.affinity:
                command = ['taskset', '-c', ','.join(map(str, self.affinity))] + command
            directory = self.work / 'workers' / self.queue / (socket.gethostname() + '-' + str(self.slot))
            directory.mkdir(parents=True, exist_ok=True)
            self.log = (directory / 'server.log').open('a')
            self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                            stderr=self.log, text=True, bufsize=1, cwd=directory)
        request = dict(id=job['job_id'], seed=job['seed'], x=job['x'], z=job['z'],
                       prefixes=prefixes, reuse_prefixes=self.reuse_prefixes, **config_world(job))
        self.process.stdin.write(json.dumps(request, separators=(',', ':')) + '\n')
        self.process.stdin.flush()
        while True:
            line = self.process.stdout.readline()
            if not line:
                raise RuntimeError('Prefix JVM exited: ' + str(self.process.poll()))
            result = protocol_response(line)
            if result is None:
                self.log.write(line)
                self.log.flush()
                continue
            if not isinstance(result, dict) or result.get('id') != job['job_id']:
                self.log.write(line)
                self.log.flush()
                continue
            if result.get('error'):
                raise RuntimeError(str(result['error']))
            if any(str(result.get(k)) != str(job[k]) for k in ('version', 'seed', 'x', 'z')):
                raise ValueError('Prefix JVM returned a different query identity')
            if config_world(result) != config_world(job) or result.get('controlled', False):
                raise ValueError('Prefix JVM returned a different world configuration')
            heights = result.get('heights')
            if not isinstance(heights, list) or len(heights) != len(prefixes):
                raise ValueError('Missing prefix heights')
            if any(v is not None and type(v) is not int for v in heights):
                raise ValueError('Invalid prefix height')
            return result


def measurement_cpus(specification, workers, cpu_per_jvm):
    """Select CPUs from the current process affinity allocation."""
    available = (set(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity')
                 else set(range(os.cpu_count() or 1)))
    if specification is None:
        selected = available
    else:
        selected = set()
        try:
            for part in specification.split(','):
                bounds = part.split('-')
                if len(bounds) == 1:
                    first = last = int(bounds[0])
                elif len(bounds) == 2:
                    first, last = map(int, bounds)
                else:
                    raise ValueError()
                if first < 0 or last < first:
                    raise ValueError()
                # Reject out-of-allocation ranges before constructing large sets.
                if last - first + 1 > len(available):
                    raise ValueError()
                selected.update(range(first, last + 1))
        except ValueError as error:
            raise ValueError('cpus must be a comma-separated CPU list, e.g. 0-3,8') from error
        if not selected or not selected <= available:
            raise ValueError('Requested CPUs are outside the current process allocation: '
                             + ','.join(map(str, sorted(available))))
    if workers < 1 or cpu_per_jvm < 1 or workers * cpu_per_jvm > len(selected):
        raise ValueError('workers * cpu-per-jvm must fit the available selected CPUs')
    return selected


def run_host(args):
    work = args.work.resolve()
    host = socket.gethostname()
    affinity = measurement_cpus(args.cpus, args.workers, args.cpu_per_jvm)
    plan_bytes = (work / 'plan.json').read_bytes()
    plan = json.loads(plan_bytes)
    policy = plan['policy']
    prefixes = center_prefixes(policy)
    world = config_world(plan)
    jobs = []
    for job in plan['jobs']:
        if 'world_type' in job and config_world(job) != world:
            raise ValueError('Measurement job differs from plan world configuration')
        jobs.append(dict(job, **world))
    if args.version:
        allowed = {resolve(v)['representative'] for v in args.version}
        jobs = [j for j in jobs if j['version'] in allowed]
    if args.exclude_version:
        excluded = {resolve(v)['representative'] for v in args.exclude_version}
        jobs = [j for j in jobs if j['version'] not in excluded]
    if args.case:
        jobs = [j for j in jobs if j['id'] in set(args.case)]
    if args.cases:
        cohort = json.loads(args.cases.read_text())['cases']
        identities = [c['id'] for c in cohort]
        if len(set(identities)) != len(identities):
            raise ValueError('Benchmark cohort contains duplicate cases')
        allowed = set(identities)
        jobs = [j for j in jobs if j['id'] in allowed]
    if args.max_tasks is not None:
        jobs = jobs[:args.max_tasks]
    reused, reuse_sources = reusable_jobs(args.reuse_results, plan, len(prefixes))
    skipped_reused = sum(job['job_id'] in reused for job in jobs)
    jobs = [job for job in jobs if job['job_id'] not in reused]
    if not jobs:
        raise ValueError('No measurement jobs match the requested filters')
    build_root = args.build_root.resolve() if args.build_root else work / 'build'
    builds = {version: json.loads((build_root / 'versions' / version / 'prefix-build.json').read_text())
              for version in {j['version'] for j in jobs}}
    references = {}
    if args.reference:
        with args.reference.open() as stream:
            references = {row['job_id']: row['heights'] for row in map(json.loads, stream)}
        missing = {j['job_id'] for j in jobs} - references.keys()
        if missing:
            raise ValueError('Reference lacks measurement jobs: ' + str(sorted(missing)[:3]))
    frozen = hashlib.sha256(plan_bytes + json.dumps(dict(
        jobs=[j['job_id'] for j in jobs], reuse_prefixes=not args.no_prefix_reuse,
        reuse_sources=reuse_sources,
        java_options=args.jvm_option,
        builds={v: b['source_sha256'] for v, b in builds.items()}), sort_keys=True).encode()).hexdigest()
    queue_path = work / (args.queue + '.json')
    lock_path = work / (args.queue + '.lock')
    result_path = work / (args.queue + '-results-' + host + '.jsonl')
    host_lock = (work / (args.queue + '-' + host + '.lock')).open('a')
    fcntl.flock(host_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    stopping = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stopping.set())
    signal.signal(signal.SIGINT, lambda *_: stopping.set())

    def transaction(action):
        with lock_path.open('a') as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            state = json.loads(queue_path.read_text()) if queue_path.exists() else dict(
                frozen=frozen, next=0, completed=0, assigned={}, failures={})
            if state['frozen'] != frozen:
                raise ValueError('Queue plan/filter changed; choose a new --queue')
            value = action(state)
            atomic(queue_path, state)
            return value

    def claim(state):
        return claim_job(state, jobs, host, stopping.is_set())

    def recover(state):
        # Recover this host only, while its per-host lock is held. Other live
        # hosts retain their own assignments and warm JVMs.
        saved = saved_result_ids(result_path)
        retry = state.setdefault('retry', [])
        for identity, owner in list(state['assigned'].items()):
            if owner['host'] != host:
                continue
            if identity in saved:
                state['assigned'].pop(identity)
                state['completed'] += 1
            else:
                state['assigned'].pop(identity)
                if identity not in retry:
                    retry.append(identity)
        if args.retry_failures:
            state['halted'] = False
            for identity in list(state['failures']):
                retry.append(identity)
                del state['failures'][identity]

    transaction(recover)

    output_lock = threading.Lock()
    started = time.time()
    counters = dict(completed=0, cold_cases=0, warm_cases=0, case_seconds=0.0,
                    warm_case_seconds=0.0, startup_seconds=0.0, queue_seconds=0.0)
    warm_window = [None, None]
    process_record = dict(host=host, pid=os.getpid(), started=started, command=sys.argv,
                          workers=args.workers, cpu_per_jvm=args.cpu_per_jvm,
                          affinity=sorted(affinity), heap=args.heap, jobs=len(jobs),
                          frozen=frozen, reuse_prefixes=not args.no_prefix_reuse)
    process_record.update(build_root=str(build_root), java_options=args.jvm_option, skipped_reused=skipped_reused)
    atomic(work / (args.queue + '-process-' + host + '.json'), process_record)
    print(json.dumps(dict(event='STARTED', **process_record)), flush=True)

    def worker(slot):
        cpus = sorted(affinity)[slot*args.cpu_per_jvm:(slot+1)*args.cpu_per_jvm]
        service = PrefixProcess(work, slot, args.heap, args.cpu_per_jvm, not args.no_prefix_reuse,
                                queue=args.queue, affinity=cpus, build_root=build_root,
                                java_options=args.jvm_option)
        errors = 0
        try:
            while not stopping.is_set():
                queue_before = time.time()
                job = transaction(claim)
                with output_lock:
                    counters['queue_seconds'] += time.time() - queue_before
                if job is None:
                    break
                before = time.time()
                cold = service.version != job['version']
                try:
                    result = service.query(job, prefixes)
                    if references and result['heights'] != references[job['job_id']]:
                        stopping.set()
                        mismatch = next(i for i, (a, b) in enumerate(zip(result['heights'], references[job['job_id']])) if a != b)
                        raise ValueError('Prefix height mismatch at ' + str(prefixes[mismatch]) +
                                         ': observed=' + str(result['heights'][mismatch]) +
                                         ', expected=' + str(references[job['job_id']][mismatch]))
                    result.update(job_id=job['job_id'], seed=job['seed'], x=job['x'], z=job['z'],
                                  version=job['version'], interval=job['interval'],
                                  policy=policy['id'], **world,
                                  elapsed_seconds=time.time() - before, host=host, cold=cold,
                                  query_started=before, query_ended=time.time())
                    def finish(state):
                        with output_lock, result_path.open('a') as stream:
                            stream.write(json.dumps(result, separators=(',', ':')) + '\n')
                            stream.flush()
                            os.fsync(stream.fileno())
                        state['assigned'].pop(job['job_id'])
                        state['completed'] += 1
                        if state['completed'] == len(jobs) and not state['failures']:
                            state['complete'] = True
                            state['ended'] = time.time()
                        return state['completed']
                    queue_before = time.time()
                    done = transaction(finish)
                    with output_lock:
                        counters['queue_seconds'] += time.time() - queue_before
                        counters['completed'] += 1
                        counters['cold_cases' if cold else 'warm_cases'] += 1
                        counters['case_seconds'] += result['elapsed_seconds']
                        if cold:
                            counters['startup_seconds'] += max(0, result['elapsed_seconds'] - result.get('seconds', 0))
                        else:
                            counters['warm_case_seconds'] += result['elapsed_seconds']
                            warm_window[0] = min(warm_window[0] or before, before)
                            warm_window[1] = max(warm_window[1] or result['query_ended'], result['query_ended'])
                    print(json.dumps(dict(event='CASE_END', job_id=job['job_id'], completed=done,
                                          total=len(jobs), seconds=result['elapsed_seconds'])), flush=True)
                except Exception as error:
                    errors += 1
                    if args.reference:
                        stopping.set()
                    service.close()
                    service.version = None
                    def fail(state):
                        fail_job(state, job['job_id'], host, error)
                    transaction(fail)
                    print(json.dumps(dict(event='CASE_FAILED', job_id=job['job_id'], error=repr(error))), flush=True)
        finally:
            service.close()
        return errors

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        errors = sum(pool.map(worker, range(args.workers)))
    ended = time.time()
    halted = transaction(lambda state: bool(state.get('halted')))
    warm_wall = warm_window[1] - warm_window[0] if warm_window[0] is not None else None
    record = dict(process_record, ended=ended, elapsed_seconds=ended-started,
                  errors=errors, halted=halted, exit_code=int(bool(errors or stopping.is_set() or halted)),
                  huts_per_second=counters['completed'] / (ended-started),
                  warm_huts_per_second=(counters['warm_cases']/warm_wall if warm_wall else None),
                  warm_capacity_huts_per_second=(args.workers*counters['warm_cases']/counters['warm_case_seconds']
                                                 if counters['warm_case_seconds'] else None),
                  warm_window_seconds=warm_wall,
                  startup_fraction=(counters['startup_seconds']/counters['case_seconds']
                                    if counters['case_seconds'] else 0), **counters)
    atomic(work / (args.queue + '-EXIT-' + host + '.json'), record)
    print(json.dumps(dict(event='HOST_EXIT', **record)), flush=True)
    return record['exit_code']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    plan = sub.add_parser('plan')
    plan.add_argument('--work', type=Path, required=True)
    plan.add_argument('--source', type=Path, default=ROOT / 'data/huts')
    plan.add_argument('--version', action='append')
    plan.add_argument('--case-limit', type=int)
    plan.add_argument('--world-type', choices=WORLD_TYPES, default='normal')
    plan.add_argument('--biome')
    plan.add_argument('--orders', type=Path, help='Editable direction list; defaults to the configured verification list')
    run = sub.add_parser('run')
    run.add_argument('--work', type=Path, required=True)
    run.add_argument('--workers', type=int, required=True)
    run.add_argument('--cpu-per-jvm', type=int, default=1)
    run.add_argument('--cpus', help='CPU IDs/ranges, e.g. 0-3,8; defaults to the current process allocation')
    run.add_argument('--heap', default='6G')
    run.add_argument('--build-root', '--build-dir', dest='build_root', type=Path)
    run.add_argument('--jvm-option', action='append', default=[])
    run.add_argument('--queue', default='measurements')
    run.add_argument('--version', action='append')
    run.add_argument('--exclude-version', action='append')
    run.add_argument('--case', action='append')
    run.add_argument('--cases', type=Path, help='Existing cohort JSON containing cases[]')
    run.add_argument('--max-tasks', type=int)
    run.add_argument('--retry-failures', action='store_true')
    run.add_argument('--no-prefix-reuse', action='store_true')
    run.add_argument('--skip-post-hut-features', action='store_true')
    run.add_argument('--reference', type=Path, help='Check every prefix against saved result JSONL')
    run.add_argument('--reuse-results', type=Path, action='append', default=[],
                     help='Validated completed results to skip; repeat for multiple files')
    extract = sub.add_parser('extract')
    extract.add_argument('--work', type=Path, required=True)
    extract.add_argument('--matrix', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'plan':
        args.work.mkdir(parents=True, exist_ok=True)
        destination = args.work / 'plan.json'
        value = make_plan(args.source, args.version, args.case_limit, args.orders,
                          world_type=args.world_type, biome=args.biome)
        if destination.exists() and json.loads(destination.read_text()) != value:
            raise ValueError('Existing plan differs; choose a new work directory')
        atomic(destination, value)
        print(json.dumps(dict(cases=value['cases'], intervals=len(value['intervals']), jobs=len(value['jobs']),
                              orders=len(value['policy']['orders']), prefixes=len(center_prefixes(value['policy'])))))
        return 0
    if args.command == 'extract':
        extract_matrix(args.work, args.matrix)
        return 0
    if args.workers < 1 or args.cpu_per_jvm < 1 or (args.max_tasks is not None and args.max_tasks < 1):
        parser.error('workers, cpu-per-jvm and max-tasks must be positive')
    if args.skip_post_hut_features:
        args.jvm_option.append('-Dhut.prefix.skipPostHutFeatures=true')
    return run_host(args)


if __name__ == '__main__':
    sys.exit(main())
