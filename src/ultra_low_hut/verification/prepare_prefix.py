"""Build version-specific vanilla prefix executors without replacing the query service."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from ultra_low_hut import ROOT
from ultra_low_hut.versions import catalog, resolve
from ultra_low_hut.verification.prepare import build_versions, source_fingerprint
from ultra_low_hut.verification.adapters.prefix import adapt_enumerator_source
from ultra_low_hut.verification.classpath import prepared_classpath


def prefix_fingerprint():
    digest = hashlib.sha256(source_fingerprint().encode())
    for name in ('src/ultra_low_hut/verification/java/FeatureOrderEnumerator121.java', 'src/ultra_low_hut/verification/java/StructureGraphSnapshot121.java',
                 'src/ultra_low_hut/verification/java/PrefixOrderExecutor.java', 'src/ultra_low_hut/verification/adapters/prefix.py',
                 'src/ultra_low_hut/verification/prepare_prefix.py'):
        digest.update(name.encode())
        digest.update((ROOT / name).read_bytes())
    return digest.hexdigest()


def compile_prefix(version, output, java=None):
    config = resolve(version)
    version = config['representative']
    java = java or 'java'
    output = Path(output).resolve() / 'versions' / version
    output.mkdir(parents=True, exist_ok=True)
    fingerprint = prefix_fingerprint()
    marker = output / 'prefix-build.json'
    if marker.exists():
        record = json.loads(marker.read_text())
        if record.get('source_sha256') == fingerprint:
            if record.get('java') != java:
                record['java'] = java
                marker.write_text(json.dumps(record, indent=2) + '\n')
            return record
    build_versions([version], java, output)
    classes = output / 'adapters' / version / 'classes'
    prepared = ROOT / 'runs/versions' / version
    classpath = os.pathsep.join((str(classes), str(output / 'query-service.jar'), prepared_classpath(prepared), str(prepared / 'asm.jar')))
    generated = output / 'FeatureOrderEnumerator121.java'
    generated.write_text(adapt_enumerator_source((ROOT / 'src/ultra_low_hut/verification/java/FeatureOrderEnumerator121.java').read_text(), version))
    command = [java, '-XX:ActiveProcessorCount=2', '-jar', str(prepared / 'ecj.jar'), '-17', '-cp', classpath, '-d', str(classes), str(generated), str(ROOT / 'src/ultra_low_hut/verification/java/StructureGraphSnapshot121.java'), str(ROOT / 'src/ultra_low_hut/verification/java/PrefixOrderExecutor.java')]
    subprocess.run(command, check=True)
    if fingerprint != prefix_fingerprint():
        raise RuntimeError('Prefix sources changed during compilation; rebuild')
    record = dict(version=version, interval=config['id'], versions=config['versions'], java=java,
                  classpath=classpath, agent=str(output/'query-service.jar'), source_sha256=fingerprint,
                  main='FeatureOrderEnumerator121')
    marker.write_text(json.dumps(record, indent=2)+'\n')
    return record


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument('--version')
    selection.add_argument('--all', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--java', default='java', help='Java executable; defaults to java on PATH')
    args=parser.parse_args()
    versions=[row['representative'] for row in catalog()['intervals']] if args.all else [args.version]
    for version in versions:
        print(json.dumps(compile_prefix(version,args.output,args.java)), flush=True)


if __name__=='__main__':
    main()
