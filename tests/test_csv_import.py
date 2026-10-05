import tempfile
import unittest
from pathlib import Path

from lopi_report.csv_import import import_csv, export_csv, default_channels


class CSVTests(unittest.TestCase):
    def make_file(self, text):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        p = Path(folder.name) / 'pomiar.csv'
        p.write_text(text, encoding='utf-8-sig')
        return p

    def test_flags_blanks_and_multiple_blocks(self):
        p = self.make_file('Interwał:60sek\nData\tCzas\tFlagowanie\tUL1_[V]\tTHD_I1_[%]\n'
                           '01.10.2026\t12:01:00.000\t \t230,5\t10\n'
                           '01.10.2026\t12:02:00.000\tX\t999\t99\n'
                           '01.10.2026\t12:03:00.000\t \t\t12\n\n'
                           'Interwał:10sek\nData\tCzas\tFlagowanie\tf_[Hz]\n'
                           '01.10.2026\t12:01:10.000\t \t50\n')
        d = import_csv(p)
        self.assertEqual(d.channels['UL1'], [230.5, None, None])
        self.assertEqual(d.channels['THD_I1'], [10, None, 12])
        self.assertEqual(d.units['THD_I1'], '%')
        self.assertNotIn('f', d.channels)
        self.assertEqual(d.metadata['measurement_start'], '2026-10-01 12:00:00')
        self.assertEqual(d.metadata['flagged_intervals'], 1)

    def test_duplicate_names_are_never_guessed(self):
        p = self.make_file('Data;Czas;UL1_[V];E_[Wh];E_[Wh]\n01.10.2026;12:01:00;230;1;2\n')
        self.assertEqual(list(import_csv(p).channels), ['UL1'])

    def test_blank_line_does_not_discard_remaining_samples(self):
        p = self.make_file('Data;Czas;UL1_[V]\n01.10.2026;12:01:00;230\n\n01.10.2026;12:02:00;999\n')
        d = import_csv(p)
        self.assertEqual(d.channels['UL1'], [230, 999])
        self.assertFalse(any('Dalsze bloki' in w for w in d.warnings))

    def test_corrupt_row_rejected(self):
        p = self.make_file('Data;Czas;UL1_[V]\n01.10.2026;12:01:00;230;EXTRA\n')
        with self.assertRaisesRegex(ValueError, 'kolumn'):
            import_csv(p)

    def test_duplicate_timestamp_rejected(self):
        p = self.make_file('Data;Czas;UL1_[V]\n01.10.2026;12:01:00;230\n01.10.2026;12:01:00;231\n')
        with self.assertRaisesRegex(ValueError, 'unikalne'):
            import_csv(p)

    def test_truncated_at_complete_row_rejected(self):
        p = self.make_file('Data/Czas:01.10.2026\t12:01:00.000 - 01.10.2026\t12:03:00.000\n'
                           'Data;Czas;UL1_[V]\n01.10.2026;12:01:00;230\n01.10.2026;12:02:00;231\n')
        with self.assertRaisesRegex(ValueError, 'niekompletny'):
            import_csv(p)

    def test_invalid_numeric_is_missing_not_zero(self):
        p = self.make_file('Data;Czas;UL1_[V]\n01.10.2026;12:01:00;230\n01.10.2026;12:02:00;NaN\n01.10.2026;12:03:00;broken\n')
        d = import_csv(p)
        self.assertEqual(d.channels['UL1'], [230, None, None])
        self.assertTrue(any('nieprawidłowych' in w for w in d.warnings))

    def test_normalized_export_roundtrip(self):
        p = self.make_file('Data;Czas;UL1_[V]\n01.10.2026;12:01:00;230\n01.10.2026;12:02:00;\n')
        d = import_csv(p)
        out = p.with_name('normalized.csv')
        export_csv(d, out)
        result = import_csv(out)
        self.assertEqual(d.times, result.times)
        self.assertEqual(d.channels, result.channels)
        self.assertEqual(default_channels(result), ['UL1'])


if __name__ == '__main__':
    unittest.main()
