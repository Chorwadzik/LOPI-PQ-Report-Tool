import math
import unittest
from datetime import datetime, timedelta

from lopi_report.pdf_report import channel_groups, channel_statistics, plot_samples, section_title, presentation_scale, central_plot_range, isolated_plot_samples, report_group_order


class PdfHelpersTests(unittest.TestCase):
    def test_thda_colors_do_not_depend_on_selection_order(self):
        from lopi_report.pdf_report import channel_color
        for index in range(4):
            self.assertEqual(channel_color('THD_(A)_IN', index), '#8b54a2')
            self.assertEqual(channel_color('THD_(A)_I2', index), '#23833f')
            self.assertEqual(channel_color('THD_(A)_I3', index), '#235bb2')

    def test_thda_is_separate_from_percentage_thdi(self):
        names = ["THD_(A)_I1", "THD_(A)_I2", "THD_(A)_I3", "THD_(A)_IN", "THD_I1", "THD_I2"]
        units = {name: "A" if "(A)" in name else "%" for name in names}
        self.assertEqual(channel_groups(names, units), [names[:4], names[4:]])
        self.assertEqual(section_title(names[:4]), "Prąd harmonicznych THD(A)")

    def test_presentation_order_preserves_all_groups(self):
        groups = [["f"], ["UL1_min"], ["THD_I1"], ["IL1"], ["UL1_max"], ["UL1"], ["other"]]
        self.assertEqual(sorted(groups, key=report_group_order),
                         [["UL1"], ["UL1_max"], ["UL1_min"], ["IL1"], ["THD_I1"], ["f"], ["other"]])

    def test_separate_quantities_and_units(self):
        names = ["UL1", "UL2", "UL3", "UL1 max", "UL2 max", "THD IL1", "THD IL2"]
        units = {name: "V" for name in names}
        units.update({"THD IL1": "%", "THD IL2": "A"})
        self.assertEqual(channel_groups(names, units),
                         [["UL1", "UL2", "UL3"], ["UL1 max", "UL2 max"], ["THD IL1"], ["THD IL2"]])

    def test_missing_and_nonfinite_values(self):
        self.assertEqual(channel_statistics([1, None, 3, float("nan"), float("inf")]),
                         {"count": 2, "missing": 3, "min": 1.0, "mean": 2.0, "max": 3.0})
        self.assertIsNone(channel_statistics([None])["mean"])

    def test_gap_is_not_connected(self):
        start = datetime(2026, 1, 1)
        times = [start + timedelta(seconds=s) for s in [0, 1, 2, 10]]
        xs, ys = plot_samples(times, [1, None, 3, 4])
        self.assertEqual(len(xs), 5)
        self.assertTrue(math.isnan(ys[1]))
        self.assertTrue(math.isnan(ys[3]))
        self.assertEqual(ys[-1], 4)

    def test_length_mismatch_fails(self):
        with self.assertRaises(ValueError):
            plot_samples([datetime(2026, 1, 1)], [])

    def test_winpq_names_and_totals(self):
        names = ["THD_I1", "THD_I2", "THD_I3", "PL1", "PL2", "PL3", "Ptotal", "tg_(fi)_L1", "tg_(fi)_L2", "tg_(fi)_L3", "tg_(fi)_"]
        units = {n: "A" if n.startswith("THD") else "W" if n.startswith("P") else "" for n in names}
        self.assertEqual(channel_groups(names, units), [names[:3], names[3:7], names[7:]])
        self.assertEqual(section_title(["UL1_min", "UL2_min"]), "Napięcia fazowe — kanały minimum")
        self.assertEqual(section_title(["THD_I1"]), "Odkształcenia harmoniczne prądu")

    def test_presentation_units(self):
        self.assertEqual(presentation_scale("PL1", "W"), (0.001, "kW"))
        self.assertEqual(presentation_scale("QL1", "Var"), (0.001, "kvar"))
        self.assertEqual(presentation_scale("tg_(fi)", ""), (1, "1"))
        self.assertEqual(presentation_scale("unknown", ""), (1, ""))

    def test_percentile_zoom_preserves_outlier_count(self):
        low, high, outside = central_plot_range([list(range(101)), [None, float("nan")]])
        self.assertEqual((low, high, outside), (1.0, 99.0, 2))
        self.assertIsNone(central_plot_range([[None]]))
        self.assertEqual(central_plot_range([[2, 2]]), (2.0, 2.0, 0))

    def test_isolated_points_between_missing_samples_and_gaps(self):
        start = datetime(2026, 1, 1)
        times = [start + timedelta(seconds=s) for s in [0, 1, 2, 3, 4, 20, 21]]
        xs, ys = plot_samples(times, [None, 5, None, 2, 3, 9, None], expected_interval=1)
        isolated_x, isolated_y = isolated_plot_samples(xs, ys)
        self.assertEqual(isolated_x, [times[1], times[5]])
        self.assertEqual(isolated_y, [5, 9])
        self.assertEqual(isolated_plot_samples([times[0]], [float("nan")]), ([], []))


if __name__ == "__main__":
    unittest.main()
