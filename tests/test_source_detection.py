import tempfile
import unittest
from pathlib import Path

from lopi_report.pqf import SIGNATURE
from lopi_report.source_detection import detect_source


class SourceDetectionTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)

    def make_file(self, name, data):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def test_sonel_signature_not_extension(self):
        path = self.make_file('renamed.bin', b'SNLAR20\x00' + b'\x01\x00\x00\x00')
        self.assertEqual(detect_source(path).kind, 'sonel_native')
        fake = self.make_file('false.pqm710', b'not a Sonel archive')
        with self.assertRaisesRegex(ValueError, 'sygnatury'):
            detect_source(fake)

    def test_incomplete_sonel_magic_rejected(self):
        path = self.make_file('broken.pqm710', b'SNLAR20')
        with self.assertRaises(ValueError):
            detect_source(path)

    def test_pqbox_nested_directory_uses_measurement_folder(self):
        path = self.make_file('nested/info.pqf', SIGNATURE + b'\x00\x00')
        detected = detect_source(self.root)
        self.assertEqual(detected.kind, 'pqbox_pqf')
        self.assertEqual(detected.path, path.parent)
        # Detection does not claim that this header-only fixture is importable.

    def test_wrong_pqbox_kind_rejected(self):
        self.make_file('info.pqf', SIGNATURE + b'\x00\x01')
        with self.assertRaises(ValueError):
            detect_source(self.root)

    def test_csv_encodings_delimiters_and_quoted_header(self):
        for encoding in ('utf-8-sig', 'utf-16', 'cp1250'):
            for delimiter in (';', '\t', ','):
                with self.subTest(encoding=encoding, delimiter=delimiter):
                    text = 'Interwał:60sek\n' + delimiter.join(['"Data"', '"Czas"', '"UL1_[V]"']) + '\n'
                    path = self.make_file('export.txt', text.encode(encoding))
                    self.assertEqual(detect_source(path).kind, 'winpq_csv')

    def test_english_csv_header(self):
        path = self.make_file('data.csv', b'Date;Time;UL1_[V]\n')
        self.assertEqual(detect_source(path).kind, 'winpq_csv')

    def test_sonel_csv_header_with_flags_and_utc(self):
        path = self.make_file('export.csv', (
            '  Analizator:  ;  PQM-710  \n'
            ";;'E / Ef';'P / Pf';'G / Gf';'T / Tf';'A / Af'; Data ; Czas (UTC+1) ; U L1 śred. 10 s [V]\n"
        ).encode('utf-8-sig'))
        self.assertEqual(detect_source(path).kind, 'sonel_csv')

    def test_unrelated_csv_rejected(self):
        path = self.make_file('other.csv', b'Date;Time;Appointment\n')
        with self.assertRaisesRegex(ValueError, 'Nie rozpoznano'):
            detect_source(path)

    def test_quoted_sonel_metadata_with_utc_without_offset(self):
        path = self.make_file('utc.csv', (
            '"Analizator:";"PQM-710"\n'
            ";;'E / Ef';'P / Pf';'G / Gf';'T / Tf';'A / Af';Data;Czas (UTC);U L1 śred. 10 s [V]\n"
        ).encode('utf-8-sig'))
        self.assertEqual(detect_source(path).kind, 'sonel_csv')

    def test_single_sonel_directory(self):
        path = self.make_file('session.pqm702', b'SNLAR20\x00')
        self.assertEqual(detect_source(self.root).path, path)

    def test_ambiguous_sources_rejected(self):
        self.make_file('first.pqm710', b'SNLAR20\x00')
        self.make_file('second.pqm710', b'SNLAR20\x00')
        with self.assertRaisesRegex(ValueError, 'źródeł: 2'):
            detect_source(self.root)

    def test_mixed_sources_rejected(self):
        self.make_file('first.pqm710', b'SNLAR20\x00')
        self.make_file('export.csv', b'Data;Czas;UL1_[V]\n')
        with self.assertRaisesRegex(ValueError, 'źródeł: 2'):
            detect_source(self.root)

    def test_missing_path_rejected(self):
        with self.assertRaisesRegex(ValueError, 'nie istnieje'):
            detect_source(self.root / 'missing.csv')


if __name__ == '__main__':
    unittest.main()
