import copy
import unittest
from datetime import datetime, timedelta

from lopi_report.harmonics import harmonic_channel, spectrum_groups, validate_thda
from lopi_report.model import Dataset


def dataset(channels, units):
    count = len(next(iter(channels.values()))) if channels else 0
    return Dataset([datetime(2026, 1, 1) + timedelta(seconds=i) for i in range(count)], channels, units)


class HarmonicsTests(unittest.TestCase):
    def test_exact_channels_and_orders(self):
        self.assertEqual(harmonic_channel('H2_UL1', '%'), ('U', 'L1', 2))
        self.assertEqual(harmonic_channel('H50_I3', 'A'), ('I', 'L3', 50))
        self.assertEqual(harmonic_channel('H12_IN', 'A'), ('I', 'N', 12))
        for name in ('H1_I1', 'H51_UL1', 'H02_UL1', 'H2_UNE', 'H2_U12', 'H2_I4', 'H2_UL1_[%]', 'h2_ul1'):
            self.assertIsNone(harmonic_channel(name, '%'))

    def test_units_and_thda_are_distinct(self):
        for name, unit in [('H2_UL1', 'V'), ('H2_I1', '%'), ('H2_IN', '')]:
            with self.assertRaises(ValueError):
                harmonic_channel(name, unit)
        for phase in ('1', '2', '3', 'N'):
            self.assertTrue(validate_thda('THD_(A)_I' + phase, 'A'))
            with self.assertRaises(ValueError):
                validate_thda('THD_(A)_I' + phase, '%')
        self.assertFalse(validate_thda('THD_I1', '%'))
        self.assertIsNone(harmonic_channel('THD_(A)_I1', 'A'))

    def test_known_statistics_and_interpolated_percentile(self):
        data = dataset({'H2_UL1': [1, None, 3, 10]}, {'H2_UL1': '%'})
        for statistic, expected in [('mean', 14 / 3), ('max', 10), ('p95', 9.3)]:
            group = spectrum_groups(data, statistic)[0]
            self.assertAlmostEqual(group['rows'][0]['values']['L1'], expected)
            self.assertEqual(group['rows'][0]['counts']['L1'], 3)
            self.assertEqual(group['statistic'], statistic)
            self.assertEqual(group['unit'], '%')

    def test_missing_phase_order_and_empty_series(self):
        data = dataset({'H50_IN': [None, None], 'H2_I1': [0, 0]}, {'H50_IN': 'A', 'H2_I1': 'A'})
        group = spectrum_groups(data)[0]
        self.assertEqual(group['phases'], ['L1', 'L2', 'L3', 'N'])
        self.assertEqual([r['order'] for r in group['rows']], list(range(2, 51)))
        self.assertEqual(group['rows'][0]['values']['L1'], 0)
        self.assertIsNone(group['rows'][0]['values']['L2'])
        self.assertIsNone(group['rows'][0]['names']['L2'])
        self.assertEqual(group['rows'][-1]['names']['N'], 'H50_IN')
        self.assertIsNone(group['rows'][-1]['values']['N'])
        self.assertEqual(group['rows'][-1]['counts']['N'], 0)
        self.assertEqual(len(group['warnings']), 2)

    def test_reject_invalid_amplitudes_and_length(self):
        for value in (-0.01, float('nan'), float('inf'), -float('inf'), 'bad'):
            with self.assertRaises(ValueError):
                spectrum_groups(dataset({'H2_I1': [value]}, {'H2_I1': 'A'}))
        data = dataset({'H2_I1': [1]}, {'H2_I1': 'A'})
        data.channels['H2_I1'].append(2)
        with self.assertRaises(ValueError):
            spectrum_groups(data)

    def test_groups_single_point_and_no_mutation(self):
        data = dataset({'H5_I2': [8], 'H2_UL1': [2]}, {'H5_I2': 'A', 'H2_UL1': '%'})
        before = copy.deepcopy(data)
        groups = spectrum_groups(data, 'p95')
        self.assertEqual([g['kind'] for g in groups], ['U', 'I'])
        self.assertEqual(groups[1]['rows'][3]['values']['L2'], 8)
        self.assertEqual(data, before)
        self.assertEqual(spectrum_groups(dataset({'UL1': [230]}, {'UL1': 'V'})), [])
        with self.assertRaises(ValueError):
            spectrum_groups(data, 'median')


if __name__ == '__main__':
    unittest.main()
