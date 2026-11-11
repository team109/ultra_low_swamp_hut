"""The source archive must be usable and contain only the published hut catalog."""

import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest

import tests

ROOT = Path(__file__).resolve().parents[1]


class SourceReleaseTests(unittest.TestCase):
    def test_archive_contains_indexed_huts_and_public_sources(self):
        runs = ROOT / 'runs'
        runs.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=runs) as folder:
            output = Path(folder) / 'source.tar.gz'
            subprocess.run([sys.executable, str(ROOT / 'scripts/release/package.py'),
                            '--output', str(output)], check=True, capture_output=True)
            with tarfile.open(output) as archive:
                names = {name.removeprefix('ultra-low-hut/') for name in archive.getnames()}
                index = json.load(archive.extractfile('ultra-low-hut/data/huts/index.json'))
                expected = {'data/huts/' + entry['file']
                            for group in index['version_groups'] for entry in group['files']}
                actual = {name for name in names if name.startswith('data/huts/') and name.endswith('.jsonl')}
                self.assertEqual(actual, expected)
                for path in ('src/ultra_low_hut/search/run.py', 'scripts/build/dependencies.py',
                             '.github/workflows/cpu.yml', 'LICENSE'):
                    self.assertIn(path, names)
                self.assertFalse(any('/__pycache__/' in name or '/external/' in name for name in names))
            self.assertEqual([path.name for path in Path(folder).iterdir()], ['source.tar.gz'])


if __name__ == '__main__':
    unittest.main()
