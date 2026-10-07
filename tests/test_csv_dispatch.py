import tempfile
import unittest
from pathlib import Path

from lopi_report.csv_import import import_csv, default_channels, export_csv
from tools.smoke_test_exe import sonel_fixture


class CSVDispatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'input.csv'

    def test_sonel_auto_dispatch_quoted_metadata_and_utc(self):
        self.path.write_text(sonel_fixture().replace('UTC+1', 'UTC').replace('Analizator:;PQM-710', '"Analizator:";"PQM-710"'), encoding='utf-8-sig')
        data = import_csv(self.path)
        self.assertEqual(data.metadata['import_type'], 'Sonel Analiza CSV')
        self.assertEqual(data.channels['U L1 śred. 10 s'], [230, 231])
        self.assertEqual(data.metadata['measurement_start'], data.times[0].isoformat(' '))
        self.assertEqual(len(default_channels(data)), 2)
        self.assertAlmostEqual(data.channels['tg(φ) L1 śred. 10 s'][0], 0.2)

    def test_normalized_sonel_export_still_selects_channels(self):
        self.path.write_text(sonel_fixture(), encoding='utf-8-sig')
        data = import_csv(self.path)
        output = self.path.with_name('normalized.csv')
        export_csv(data, output)
        loaded = import_csv(output)
        self.assertEqual(default_channels(loaded), default_channels(data))
        self.assertEqual(loaded.channels, data.channels)

    def test_native_sonel_has_actionable_error(self):
        self.path.write_bytes(b'SNLAR20\x00')
        with self.assertRaisesRegex(ValueError, 'Raport CSV'):
            import_csv(self.path)

    def test_historical_unitless_winpq_with_long_preamble(self):
        self.path.write_text('x\n' * 40000 + 'Data;Czas;tg_(fi)_\n01.01.2025;00:00:00;0.2\n', encoding='utf-8')
        self.assertEqual(import_csv(self.path).channels['tg_(fi)_'], [0.2])
