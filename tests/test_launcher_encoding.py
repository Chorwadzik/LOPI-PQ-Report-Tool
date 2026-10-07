import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from tools.smoke_test_exe import sonel_fixture


class LauncherEncodingTests(unittest.TestCase):
    def test_unicode_tangent_status_on_cp1250_pipe(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'sonel.csv'
            source.write_text(sonel_fixture(), encoding='utf-8-sig')
            metadata = root / 'metadata.json'
            metadata.write_text('{"title":"Test"}', encoding='utf-8')
            env = dict(os.environ, PYTHONIOENCODING='cp1250')
            result = subprocess.run([sys.executable, 'launcher.py', '--input', str(source),
                                     '--metadata', str(metadata), '--output', str(root / 'report.pdf')],
                                    capture_output=True, env=env, timeout=90)
            self.assertEqual(result.returncode, 0, result.stderr.decode('cp1250', errors='replace'))
            status = json.loads(result.stdout)
            self.assertTrue(status['ok'])
            self.assertEqual(status['channels'], 2)
            self.assertTrue(any('tg(φ)' in value for value in status['warnings']))
