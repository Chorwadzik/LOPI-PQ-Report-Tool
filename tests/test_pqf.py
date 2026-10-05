import math
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import hashlib

from lopi_report.pqf import import_pqf, SIGNATURE, RECORD_SIZE
from lopi_report.pqf_profile import LAYOUT, CHANNELS


def header(kind):
    return SIGNATURE + bytes((0, kind)) + b'20260924120146' + b'\xff' * 16


def record(stamp, flag=0):
    data = bytearray()
    for kind, size in LAYOUT:
        payload = bytearray(size)
        struct.pack_into('<II', payload, 0, stamp, 0x01040000)
        if kind == 150:
            struct.pack_into('<I', payload, 8, flag)
        data.extend(struct.pack('>HH', kind, size) + payload)
    for offset, _ in CHANNELS.values():
        struct.pack_into('<f', data, offset, 12.5)
    assert len(data) == RECORD_SIZE
    return data


class PQFTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        info = bytearray(header(0) + bytes(2012))
        info[48:52] = bytes.fromhex('00020064')
        struct.pack_into('<I', info, 60, 60)
        (self.folder / 'info.pqf').write_bytes(info)
        self.profile_patch = patch('lopi_report.pqf.VERIFIED_INFO_PAYLOAD_SHA256', hashlib.sha256(info[48:]).hexdigest())
        self.profile_patch.start()
        self.addCleanup(self.profile_patch.stop)
        (self.folder / 'cyc2h.pqf').write_bytes(header(0x43))
        self.write_records(record(1159092180), record(1159092240))

    def tearDown(self):
        self.tmp.cleanup()

    def write_records(self, *rows):
        (self.folder / 'cyc.pqf').write_bytes(header(1) + b''.join(rows))

    def load(self):
        return import_pqf(self.folder, time_offset_hours=2)

    def test_known_values_time_and_flags(self):
        self.write_records(record(1159092180), record(1159092240, 0x8000))
        ds = self.load()
        self.assertEqual(ds.times[0].isoformat(), '2026-09-24T12:03:00')
        self.assertEqual(ds.channels['UL1'], [12.5, None])
        self.assertEqual(ds.metadata['flagged_intervals'], 1)

    def test_twohour_flag_is_conservative_union(self):
        first = struct.pack('>HH', 600, 24) + struct.pack('<IIIIII', 1159092240, 0x01040000, 0x8000, 0, 0, 0)
        second = struct.pack('>HH', 602, 140) + struct.pack('<II', 1159092240, 0x01040000) + bytes(132)
        (self.folder / 'cyc2h.pqf').write_bytes(header(0x43) + first + second)
        self.assertEqual(self.load().channels['UL1'], [12.5, None])

    def test_clock_requires_explicit_user_value(self):
        with self.assertRaisesRegex(ValueError, 'przesunięcie'):
            import_pqf(self.folder)

    def test_unknown_flag_rejected(self):
        self.write_records(record(1159092180, 1))
        with self.assertRaisesRegex(ValueError, 'flagi'):
            self.load()

    def test_unknown_layout_and_truncation_rejected(self):
        row = record(1159092180)
        row[0] = 1
        self.write_records(row)
        with self.assertRaisesRegex(ValueError, 'układ'):
            self.load()
        self.write_records(row[:-1])
        with self.assertRaisesRegex(ValueError, 'Niepełny'):
            self.load()

    def test_bad_float_is_missing_not_zero(self):
        row = record(1159092180)
        struct.pack_into('<f', row, CHANNELS['UL1'][0], math.nan)
        struct.pack_into('<f', row, CHANNELS['UL2'][0], math.inf)
        self.write_records(row)
        ds = self.load()
        self.assertEqual(ds.channels['UL1'], [None])
        self.assertEqual(ds.channels['UL2'], [None])

    def test_duplicate_and_conflicting_times_rejected(self):
        self.write_records(record(1159092180), record(1159092180))
        with self.assertRaisesRegex(ValueError, 'czasy'):
            self.load()
        row = record(1159092180)
        struct.pack_into('<I', row, 32, 1159092240)
        self.write_records(row)
        with self.assertRaisesRegex(ValueError, 'znaczniki'):
            self.load()

    def test_unknown_firmware_rejected(self):
        path = self.folder / 'cyc.pqf'
        data = bytearray(path.read_bytes())
        data[14] = ord('9')
        path.write_bytes(data)
        with self.assertRaisesRegex(ValueError, 'firmware'):
            self.load()

    def test_configuration_payload_change_rejected(self):
        path = self.folder / 'info.pqf'
        info = bytearray(path.read_bytes())
        info[80] ^= 1
        path.write_bytes(info)
        with self.assertRaisesRegex(ValueError, 'Konfiguracja'):
            self.load()

    def test_missing_intervals_remain_gaps(self):
        self.write_records(record(1159092180), record(1159092300))
        ds = self.load()
        self.assertEqual(len(ds.times), 2)
        self.assertTrue(any('brakuje 1 interwałów' in w for w in ds.warnings))

    def test_multiple_measurements_rejected(self):
        sub = self.folder / 'another'
        sub.mkdir()
        (sub / 'info.pqf').write_bytes((self.folder / 'info.pqf').read_bytes())
        with self.assertRaisesRegex(ValueError, 'dokładnie jeden'):
            self.load()


class LocalWinPQComparison(unittest.TestCase):
    def test_all_samples_against_reference_export_if_available(self):
        from lopi_report.csv_import import import_csv
        root = Path(__file__).resolve().parents[1]
        source = root / 'przykładowy raport/przykładowe pomiary PQBox/20260924_1201_000'
        exported = root / 'exports/20260924_all.csv'
        if not source.is_dir() or not exported.is_file():
            self.skipTest('Prywatne dane walidacyjne nie są dołączane do repozytorium.')
        binary = import_pqf(source, time_offset_hours=2)
        reference = import_csv(exported)
        self.assertEqual(len(binary.times), 11283)
        self.assertEqual(len(binary.channels), 41)
        self.assertEqual(binary.times, reference.times)
        self.assertEqual(binary.metadata['flagged_intervals'], 2)
        self.assertEqual(binary.metadata['flagged_intervals'], reference.metadata['flagged_intervals'])
        for name, values in binary.channels.items():
            self.assertEqual(binary.units[name], reference.units[name])
            for i, (actual, expected) in enumerate(zip(values, reference.channels[name])):
                self.assertEqual(actual is None, expected is None, (name, i))
                if actual is not None:
                    self.assertLess(abs(actual - expected), 0.000501, (name, i))


if __name__ == '__main__':
    unittest.main()
