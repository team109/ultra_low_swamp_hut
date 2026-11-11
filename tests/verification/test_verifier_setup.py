import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from ultra_low_hut.verification import artifacts as setup


class VerifierSetupTests(unittest.TestCase):
    def test_cached_prefix_build_uses_the_requested_java(self):
        import json
        from ultra_low_hut.verification import prepare_prefix

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            marker = root / 'versions/1.21/prefix-build.json'
            marker.parent.mkdir(parents=True)
            marker.write_text(json.dumps(dict(source_sha256='current', java='/old/java')))
            with patch.object(prepare_prefix, 'prefix_fingerprint', return_value='current'), \
                 patch.object(prepare_prefix, 'build_versions', side_effect=AssertionError('unnecessary build')):
                self.assertEqual(prepare_prefix.compile_prefix('1.21', root)['java'], 'java')
                self.assertEqual(prepare_prefix.compile_prefix('1.21', root, '/chosen/java')['java'], '/chosen/java')
            self.assertEqual(json.loads(marker.read_text())['java'], '/chosen/java')

    def test_existing_jar_is_neither_read_nor_downloaded(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'server.jar'
            target.write_bytes(b'existing file')
            with patch.object(setup, 'fetch_bytes', side_effect=AssertionError('network')):
                with patch.object(Path, 'read_bytes', side_effect=AssertionError('read')):
                    setup.download('https://example.invalid/server.jar', target, 'wrong-digest')

    def test_cached_setup_downloads_only_the_missing_tool(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            prepared = root / 'runs/versions/1.21'
            prepared.mkdir(parents=True)
            library = prepared / 'libraries/example.jar'
            library.parent.mkdir()
            library.write_bytes(b'cached')
            for name in ('server.jar', 'server-inner.jar', 'server-mapped.jar', 'specialsource.jar', 'ecj.jar'):
                (prepared / name).write_bytes(b'cached')
            (prepared / 'classpath.txt').write_text(str(prepared/'server-mapped.jar') + setup.os.pathsep + str(library))
            missing = b'new asm'
            digest = hashlib.sha1(missing).hexdigest().encode()
            with patch.object(setup, 'ROOT', root), patch.object(setup, 'fetch_bytes', side_effect=[digest, missing]) as fetch:
                with patch.object(zipfile, 'ZipFile', side_effect=AssertionError('unnecessary unpack')):
                    setup.prepare('1.21', artifacts_only=True)
            self.assertEqual((prepared/'asm.jar').read_bytes(), missing)
            self.assertEqual(len(fetch.call_args_list), 2)
            self.assertTrue(all('/asm/' in call.args[0] for call in fetch.call_args_list))
            with patch.object(setup, 'ROOT', root), patch.object(setup, 'fetch_bytes', side_effect=AssertionError('network')):
                setup.prepare('1.21', artifacts_only=True)
            service = root / 'runs/query-service-build'
            adapter = service / 'adapters/1.21/classes/VanillaQueryMain.class'
            adapter.parent.mkdir(parents=True)
            adapter.write_bytes(b'cached class')
            (service/'query-service.jar').write_bytes(b'cached agent')
            with patch.object(setup, 'ROOT', root), patch.object(setup, 'fetch_bytes', side_effect=AssertionError('network')):
                with patch('ultra_low_hut.verification.prepare.build', side_effect=AssertionError('unnecessary build')):
                    setup.prepare('1.21')
