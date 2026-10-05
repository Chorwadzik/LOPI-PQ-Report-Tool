import unittest

from lopi_report.app import validate_filename, validate_project


class AppValidationTests(unittest.TestCase):
    def test_filename(self):
        self.assertEqual(validate_filename("Raport Łódź"), "Raport Łódź.pdf")
        self.assertEqual(validate_filename("Raport.PDF"), "Raport.PDF")
        for value in ("", "../a.pdf", "C:\\raport.pdf", "NUL.pdf", "COM1.txt", "a?b", "raport.", "a\x00.pdf"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_filename(value)

    def test_project(self):
        data = {"format": "lopi-pq-project", "version": 1,
                "filename": "Raport.pdf", "metadata": {"title": "Łódź"},
                "selected_channels": ["UL1"], "time_offset_hours": 2}
        self.assertEqual(validate_project(data), data)
        for key, value in [("format", "unknown"), ("version", 2), ("metadata", []),
                           ("selected_channels", "UL1"), ("time_offset_hours", float("nan")),
                           ("time_offset_hours", 15), ("time_offset_hours", True),
                           ("filename", "../report.pdf"), ("source_kind", "exe")]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate_project({**data, key: value})

    def test_spectrum_setting_persists_and_rejects_unknown_statistic(self):
        data = {"format": "lopi-pq-project", "version": 1,
                "filename": "Raport.pdf", "metadata": {"title": "Raport"}}
        for statistic in ("mean", "max", "p95"):
            value = {**data, "metadata": {**data["metadata"], "spectrum_statistic": statistic}}
            self.assertEqual(validate_project(value)["metadata"]["spectrum_statistic"], statistic)
        with self.assertRaises(ValueError):
            validate_project({**data, "metadata": {"spectrum_statistic": "automatic"}})


if __name__ == "__main__":
    unittest.main()
