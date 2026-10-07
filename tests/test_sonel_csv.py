import csv
from datetime import datetime, timedelta
from pathlib import Path
import statistics
import tempfile
import unittest
from unittest.mock import patch

from lopi_report.model import Dataset
from lopi_report.sonel_csv import import_sonel_csv, default_sonel_channels, add_combined_tangent


class SonelCSVTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / 'synthetic.csv'

    def make_file(self, values, labels=None, flags=None, encoding='utf-8-sig', delimiter=';', start_delta=0, end_delta=0):
        labels = labels or ['U L1 śred. 10 s [V]']
        stamps = [datetime(2025, 1, 1, 0, 0, 10) + timedelta(seconds=10 * i) for i in range(len(values))]
        rows = [['Analizator:', 'PQM-710'],
                ['Data rozpoczęcia rejestracji:', (stamps[0] + timedelta(milliseconds=start_delta)).isoformat(' ')],
                ['Data zakończenia rejestracji:', (stamps[-1] + timedelta(milliseconds=end_delta)).isoformat(' ')],
                ['Czas:', '(UTC+1)'], [],
                ['', ''] + [f"'{f} / {f}f'" for f in 'EPGTA'] + ['Data', 'Czas (UTC+1)'] + labels]
        for index, (stamp, row) in enumerate(zip(stamps, values)):
            rows.append(['', ''] + (flags[index] if flags else [''] * 5) + [stamp.strftime('%Y-%m-%d'), stamp.strftime('%H:%M:%S.%f')] + row)
        with self.path.open('w', encoding=encoding, newline='') as stream:
            csv.writer(stream, delimiter=delimiter).writerows(rows)
        return self.path

    def test_values_units_and_known_result_streaming(self):
        p = self.make_file([['230', '10'], ['240', '20'], ['250', '30']], ['U L1 śred. 10 s [V]', 'THD I L1 śred. 10 s [%]'])
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('Full read prohibited')):
            data = import_sonel_csv(p)
        self.assertEqual(statistics.mean(data.channels['U L1 śred. 10 s']), 240)
        self.assertEqual(data.units['THD I L1 śred. 10 s'], '%')
        self.assertEqual(data.times[0], datetime(2025, 1, 1, 0, 0, 10))
        self.assertEqual(data.metadata['source_timezone'], 'UTC+1')

    def test_missing_invalid_nonfinite_and_zero_are_distinct(self):
        data = import_sonel_csv(self.make_file([['0'], ['---'], [''], ['nan'], ['1e999'], ['bad'], ['230,5']]))
        self.assertEqual(data.channels['U L1 śred. 10 s'], [0, None, None, None, None, None, 230.5])
        self.assertEqual(data.metadata['invalid_values'], 3)
        self.assertEqual(data.metadata['missing_values'], 2)

    def test_flags_and_fast_flags_conservative(self):
        flags = [[''] * 5]
        for index, flag in enumerate('EPGTA'):
            for suffix in ('', 'f'):
                row = [''] * 5
                row[index] = "'" + flag + suffix + " '"
                flags.append(row)
        flags.extend([['UNKNOWN', '', '', '', ''], ['', '', 'G Gf', '', ''], ['', 'G', '', '', '']])
        data = import_sonel_csv(self.make_file([['230']] * len(flags), flags=flags))
        expected = [230, None, None, None, None, 230, 230, None, None, None, None, None, 230, None]
        self.assertEqual(data.channels['U L1 śred. 10 s'], expected)
        self.assertEqual(data.metadata['unknown_flag_intervals'], 2)
        self.assertTrue(any('precyzja czasu' in warning for warning in data.warnings))

    def test_other_aggregation_not_mixed(self):
        data = import_sonel_csv(self.make_file([['230', '2'], ['240', '2']], ['U L1 śred. 10 s [V]', 'Pst L1 chwil. 10 min [---]']))
        self.assertEqual(list(data.channels), ['U L1 śred. 10 s'])
        self.assertEqual(data.metadata['omitted_other_aggregation_channels'], 1)

    def test_blank_channels_removed_and_asterisk_preserved(self):
        data = import_sonel_csv(self.make_file([['0', '---'], ['1', '']], ['I *L1 śred. 10 s [A]', 'I *L2 śred. 10 s [A]']))
        self.assertEqual(list(data.channels), ['I *L1 śred. 10 s'])
        self.assertTrue(any('ograniczenie prądu' in warning for warning in data.warnings))

    def test_unsupported_headers_omitted_with_warning(self):
        data = import_sonel_csv(self.make_file([['230', '1']], ['U L1 śred. 10 s [V]', 'Unknown [V]']))
        self.assertEqual(data.metadata['omitted_unrecognized_channels'], 1)

    def test_duplicates_and_conflicting_units_rejected(self):
        for second in ('U L1 śred. 10 s [V]', 'U L1 śred. 10 s [kV]'):
            with self.subTest(second=second):
                with self.assertRaises(ValueError):
                    import_sonel_csv(self.make_file([['230', '230']], ['U L1 śred. 10 s [V]', second]))

    def test_bad_row_width_rejected(self):
        with self.assertRaisesRegex(ValueError, 'liczba kolumn'):
            import_sonel_csv(self.make_file([['230'], ['240', 'extra']]))

    def test_nonempty_reserved_columns_rejected(self):
        self.make_file([['230']])
        text = self.path.read_text(encoding='utf-8-sig').replace(';;;;;;;2025-', 'X;;;;;;;2025-')
        self.path.write_text(text, encoding='utf-8-sig')
        with self.assertRaisesRegex(ValueError, 'dwóch kolumn'):
            import_sonel_csv(self.path)

    def test_duplicate_and_invalid_timestamp_rejected(self):
        for replacement in ('00:00:10.000000', 'not-a-time'):
            self.make_file([['230'], ['240']])
            text = self.path.read_text(encoding='utf-8-sig').replace('00:00:20.000000', replacement)
            self.path.write_text(text, encoding='utf-8-sig')
            with self.assertRaises(ValueError):
                import_sonel_csv(self.path)

    def test_metadata_boundaries_tolerance_and_truncation(self):
        self.assertEqual(len(import_sonel_csv(self.make_file([['230'], ['240']], start_delta=-1, end_delta=-1)).times), 2)
        with self.assertRaisesRegex(ValueError, 'ucięty lub podzielony'):
            import_sonel_csv(self.make_file([['230'], ['240']], end_delta=10000))

    def test_timezone_mismatch_and_missing_preamble_rejected(self):
        for old, new in [('Czas:;(UTC+1)', 'Czas:;(UTC+2)'), ('Analizator:;PQM-710', 'Wrong:;PQM-710')]:
            self.make_file([['230']])
            self.path.write_text(self.path.read_text(encoding='utf-8-sig').replace(old, new), encoding='utf-8-sig')
            with self.assertRaises(ValueError):
                import_sonel_csv(self.path)

    def test_invalid_timezone_offset_rejected(self):
        for offset in ('UTC+99', 'UTC+14:01', 'UTC-01:60'):
            self.make_file([['230']])
            self.path.write_text(self.path.read_text(encoding='utf-8-sig').replace('UTC+1', offset), encoding='utf-8-sig')
            with self.assertRaisesRegex(ValueError, 'UTC'):
                import_sonel_csv(self.path)

    def test_spectra_not_accumulated_in_report_dataset(self):
        data = import_sonel_csv(self.make_file([['230', '2', '3']], ['U L1 śred. 10 s [V]', 'U H 2 L1 śred. 10 s [V]', 'EP+ L1 chwil. 10 s [Wh]']))
        self.assertEqual(list(data.channels), ['U L1 śred. 10 s'])
        self.assertEqual(data.metadata['omitted_outside_report_channels'], 2)
        self.assertEqual(data.metadata['instrument'], 'PQM-710')

    def test_encoding_and_delimiter_variants(self):
        for encoding in ('utf-8-sig', 'utf-16', 'cp1250'):
            for delimiter in (';', '\t', ','):
                with self.subTest(encoding=encoding, delimiter=delimiter):
                    data = import_sonel_csv(self.make_file([['230,5']], encoding=encoding, delimiter=delimiter))
                    self.assertEqual(data.channels['U L1 śred. 10 s'], [230.5])

    def test_defaults_keep_power_definitions_without_spectral_aliases(self):
        names = ['U L1 min. 10 s', 'Q1 Σ śred. 10 s', 'Sn L1 śred. 10 s', 'tg(φ)L+ L1 śred. 10 s', 'tg(φ)C- L1 śred. 10 s', 'U H 2 L1 śred. 10 s']
        data = Dataset([datetime(2025, 1, 1)], {n: [1] for n in names}, {n: 'V' for n in names})
        self.assertEqual(default_sonel_channels(data), names[:-1])


class CombinedTangentTests(unittest.TestCase):
    def make_dataset(self, samples, phase='L1', suffix='10 s'):
        names = [f'tg(φ){quadrant} {phase} śred. {suffix}' for quadrant in ('L+', 'C-', 'L-', 'C+')]
        times = [datetime(2025, 1, 1) + timedelta(seconds=10*i) for i in range(len(samples))]
        return Dataset(times, {name: [row[i] for row in samples] for i, name in enumerate(names)}, {name: '---' for name in names})

    def test_signed_sum_overlap_and_zero(self):
        data = self.make_dataset([[0.3, 0, 0, -0.1], [0, 0, 0, 0], [1, -2, 3, -4]])
        add_combined_tangent(data)
        target = 'tg(φ) L1 śred. 10 s'
        self.assertAlmostEqual(data.channels[target][0], 0.2)
        self.assertEqual(data.channels[target][1:], [0, -2])
        self.assertEqual(len(data.channels), 5)
        self.assertEqual(data.metadata['combined_tangent_channels'], [target])
        self.assertEqual(default_sonel_channels(data), [target])

    def test_missing_nonfinite_sign_and_overflow(self):
        data = self.make_dataset([[None, 0, 0, -0.1], [0.1, float('inf'), 0, 0], [-0.1, 0, 0, 0], [0.1, 0.2, 0, 0], [1e308, 0, 1e308, 0]])
        add_combined_tangent(data)
        target = 'tg(φ) L1 śred. 10 s'
        self.assertEqual(data.channels[target], [None]*5)
        self.assertEqual(data.metadata['derived_channels'][target]['missing_samples'], 2)
        self.assertEqual(data.metadata['derived_channels'][target]['invalid_sign_samples'], 2)
        self.assertEqual(data.metadata['derived_channels'][target]['overflow_samples'], 1)
        self.assertEqual(default_sonel_channels(data), [target])

    def test_missing_column_is_not_zero(self):
        data = self.make_dataset([[0.3, 0, 0, -0.1]])
        del data.channels['tg(φ)C- L1 śred. 10 s']
        add_combined_tangent(data)
        self.assertEqual(data.channels['tg(φ) L1 śred. 10 s'], [None])
        self.assertTrue(any('Brak pełnego' in warning for warning in data.warnings))

    def test_incompatible_units(self):
        data = self.make_dataset([[0.3, 0, 0, -0.1]])
        data.units['tg(φ)C+ L1 śred. 10 s'] = '%'
        add_combined_tangent(data)
        self.assertEqual(data.channels['tg(φ) L1 śred. 10 s'], [None])

    def test_total_uses_own_quadrants_and_periods_never_mix(self):
        data = self.make_dataset([[0.3, 0, 0, -0.1]])
        total = self.make_dataset([[0.9, 0, 0, -0.2]], phase='Σ')
        different = self.make_dataset([[1, 0, 0, -0.4]], suffix='1 min')
        data.channels.update(total.channels)
        data.units.update(total.units)
        data.channels.update(different.channels)
        data.units.update(different.units)
        add_combined_tangent(data)
        self.assertAlmostEqual(data.channels['tg(φ) L1 śred. 10 s'][0], 0.2)
        self.assertAlmostEqual(data.channels['tg(φ) Σ śred. 10 s'][0], 0.7)
        self.assertAlmostEqual(data.channels['tg(φ) L1 śred. 60 s'][0], 0.6)

    def test_min_max_not_combined(self):
        data = self.make_dataset([[0.3, 0, 0, -0.1]])
        data.channels = {name.replace('śred.', 'min.'): values for name, values in data.channels.items()}
        data.units = {name: '---' for name in data.channels}
        add_combined_tangent(data)
        self.assertEqual(data.metadata['combined_tangent_channels'], [])

    def test_existing_direct_channel_never_overwritten_or_marked_derived(self):
        data = self.make_dataset([[0.3, 0, 0, -0.1]])
        target = 'tg(φ) L1 śred. 10 s'
        data.channels[target] = [0.9]
        data.units[target] = '---'
        add_combined_tangent(data)
        self.assertEqual(data.channels[target], [0.9])
        self.assertEqual(data.metadata['combined_tangent_channels'], [])
        self.assertEqual(default_sonel_channels(data), [target])

    def test_normalized_export_defaults_without_metadata(self):
        data = self.make_dataset([[0.3, 0, 0, -0.1]])
        add_combined_tangent(data)
        data.metadata = {}
        self.assertEqual(default_sonel_channels(data), ['tg(φ) L1 śred. 10 s'])

    def test_empty_quadrant_survives_import_and_blocks_combined_value(self):
        case = SonelCSVTests()
        case.setUp()
        try:
            labels = [f'tg(φ){q} L1 śred. 10 s [---]' for q in ('L+', 'C-', 'L-', 'C+')]
            data = import_sonel_csv(case.make_file([['0.3', '---', '0', '-0.1']], labels))
            self.assertEqual(data.channels['tg(φ)C- L1 śred. 10 s'], [None])
            self.assertEqual(data.channels['tg(φ) L1 śred. 10 s'], [None])
            self.assertEqual(default_sonel_channels(data), ['tg(φ) L1 śred. 10 s'])
        finally:
            case.doCleanups()


if __name__ == '__main__':
    unittest.main()
