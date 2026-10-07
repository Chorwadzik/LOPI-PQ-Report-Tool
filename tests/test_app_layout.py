import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import patch

from lopi_report.app import Application


class AppLayoutTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        if "high_dpi" in self._testMethodName:
            self.root.tk.call("tk", "scaling", 2.0)
        style = ttk.Style(self.root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("TLabel", font=("Segoe UI", 10))
        style.configure("TButton", padding=(10, 5))
        self.app = Application(self.root)

    def tearDown(self):
        for callback in self.root.tk.call("after", "info"):
            self.root.after_cancel(callback)
        self.root.destroy()

    def test_confirmation_and_pdf_action_fit_small_window(self):
        for width, height in ((800, 650), (1050, 668), (1330, 790)):
            with self.subTest(size=(width, height)):
                self.root.geometry(f"{width}x{height}")
                self.app.tabs.select(2)
                self.root.update()
                generate = next(w for w in self.app.controls
                                if isinstance(w, ttk.Button) and w.cget("text") == "Generuj PDF")
                for widget in (self.app.dates_check, generate):
                    self.assertTrue(widget.winfo_viewable())
                    self.assertGreater(widget.winfo_height(), 10)
                    self.assertGreaterEqual(widget.winfo_rooty(), self.root.winfo_rooty())
                    self.assertLessEqual(widget.winfo_rooty() + widget.winfo_height(),
                                         self.root.winfo_rooty() + self.root.winfo_height())
                self.assertLess(self.app.dates_check.winfo_rooty(), self.app.channel_list.winfo_rooty())

    def test_high_dpi_keeps_channels_and_warnings_accessible_by_scroll(self):
        self.root.geometry("800x650")
        self.app.tabs.select(2)
        self.root.update()
        canvas = self.app.channels_canvas
        for widget in (self.app.channel_list, self.app.warnings):
            self.assertGreater(widget.winfo_height(), 40)
            self.assertTrue(widget.winfo_viewable())
        canvas.yview_moveto(1)
        self.root.update()
        self.assertGreater(self.app.warnings.winfo_rooty() + self.app.warnings.winfo_height(), canvas.winfo_rooty())
        self.assertLess(self.app.warnings.winfo_rooty(), canvas.winfo_rooty() + canvas.winfo_height())
        canvas.yview_moveto(0)
        self.root.update()
        self.assertGreaterEqual(self.app.dates_check.winfo_rooty(), canvas.winfo_rooty())

    @patch("lopi_report.app.messagebox.showerror")
    def test_unverified_pqf_still_blocks_generation_and_shows_period(self, error):
        self.app.dataset = object()
        self.app.measurement_period.set("Okres do sprawdzenia: 2026-01-01 — 2026-01-02")
        with patch.object(self.app, "_work") as work:
            self.app.generate()
            work.assert_not_called()
        self.assertIn("2026-01-01", error.call_args.args[1])
        self.assertEqual(self.app.tabs.index(self.app.tabs.select()), 2)
        self.assertFalse(self.app.dates_verified.get())

    def test_source_change_clears_confirmation_and_period(self):
        self.app.dates_verified.set(True)
        self.app.measurement_period.set("Poprzedni okres")
        self.app.time_offset.set("1")
        self.assertFalse(self.app.dates_verified.get())
        self.assertEqual(self.app.measurement_period.get(), "Nie wczytano pomiarów.")
