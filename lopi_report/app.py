"""Offline desktop interface. Worker threads never access Tk widgets."""
from __future__ import annotations

import json
import os
from pathlib import Path
import queue
import re
import tempfile
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

FIELDS = {
    "title": "Tytuł raportu", "report_number": "Numer raportu",
    "company": "Wykonawca", "object_name": "Obiekt", "address": "Adres",
    "authors": "Autorzy", "instrument": "Analizator",
}


def validate_filename(value):
    value = value.strip()
    if not value or value in {".", ".."} or re.search(r'[<>:"/\\|?*\x00-\x1f]', value):
        raise ValueError("Podaj nazwę pliku bez ścieżki i znaków: < > : \" / \\ | ? *.")
    if value.endswith((".", " ")):
        raise ValueError("Nazwa pliku nie może kończyć się kropką ani spacją.")
    if re.match(r"(?i)^(CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])(?:\.|$)", value):
        raise ValueError("Ta nazwa jest zarezerwowana przez Windows.")
    if not value.lower().endswith(".pdf"):
        value += ".pdf"
    if len(value) > 180:
        raise ValueError("Nazwa pliku jest za długa (maksymalnie 180 znaków).")
    return value


def validate_project(data):
    if not isinstance(data, dict) or data.get("format") != "lopi-pq-project" or data.get("version") != 1:
        raise ValueError("Nieobsługiwany format lub wersja projektu.")
    for key in ("source_folder", "output_folder", "filename", "csv_path"):
        if not isinstance(data.get(key, ""), str):
            raise ValueError(f"Nieprawidłowe pole projektu: {key}.")
    metadata = data.get("metadata")
    if not isinstance(metadata, dict) or any(not isinstance(metadata.get(k, ""), str) for k in (*FIELDS, "description", "conclusions")):
        raise ValueError("Nieprawidłowe opisy w projekcie.")
    if metadata.get("spectrum_statistic", "mean") not in ("mean", "max", "p95"):
        raise ValueError("Nieprawidłowa statystyka widma w projekcie.")
    selection = data.get("selected_channels", [])
    if not isinstance(selection, list) or any(not isinstance(v, str) for v in selection):
        raise ValueError("Nieprawidłowa lista kanałów projektu.")
    if data.get("source_kind", "pqf") not in ("pqf", "csv"):
        raise ValueError("Nieprawidłowy rodzaj źródła projektu.")
    offset = data.get("time_offset_hours", 2)
    if isinstance(offset, bool) or not isinstance(offset, (int, float)) or not -14 <= offset <= 14:
        raise ValueError("Przesunięcie czasu musi być liczbą od −14 do +14 godzin.")
    validate_filename(data.get("filename", ""))
    return data


class Application:
    def __init__(self, root):
        self.root = root
        root.title("LOPI • Raport z pomiarów PQBox / Sonel")
        root.geometry(f"1050x{min(850, root.winfo_screenheight() - 100)}")
        root.minsize(800, 650)
        self.dataset = None
        self.last_pdf = None
        self.busy = False
        self.events = queue.Queue()
        self.controls = []
        self.pending_selection = None
        self.source_kind = "pqf"
        self.csv_path = ""
        self.time_offset = tk.StringVar(value="2")
        self.dates_verified = tk.BooleanVar(value=False)
        self.spectrum_statistic = tk.StringVar(value="mean")
        self.source_folder = tk.StringVar()
        self.output_folder = tk.StringVar()
        self.filename = tk.StringVar(value="Raport pomiarów.pdf")
        self.values = {key: tk.StringVar() for key in FIELDS}
        self.values["title"].set("Raport z pomiarów jakości energii elektrycznej")
        self.status = tk.StringVar(value="Wskaż folder pomiarów i folder zapisu PDF.")
        self.info = tk.StringVar(value="Nie wczytano pomiarów.")
        self.measurement_period = tk.StringVar(value="Nie wczytano pomiarów.")
        self._build()
        self.source_folder.trace_add("write", self._source_changed)
        self.time_offset.trace_add("write", self._source_changed)
        root.protocol("WM_DELETE_WINDOW", self._close)
        root.after(100, self._poll)

    def _button(self, parent, text, command, **grid):
        widget = ttk.Button(parent, text=text, command=command)
        widget.grid(**grid)
        self.controls.append(widget)
        return widget

    def _entry(self, parent, variable, **grid):
        widget = ttk.Entry(parent, textvariable=variable)
        widget.grid(**grid)
        self.controls.append(widget)
        return widget

    def _build(self):
        outer = ttk.Frame(self.root, padding=14)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(2, weight=1)
        ttk.Label(outer, text="LOPI  /  RAPORT POMIAROWY", font=("Segoe UI", 17, "bold")).grid(row=0, column=0, sticky="w")
        toolbar = ttk.Frame(outer)
        toolbar.grid(row=1, column=0, sticky="ew", pady=(10, 12))
        self._button(toolbar, "Otwórz projekt…", self.load_project, row=0, column=0, padx=(0, 8))
        self._button(toolbar, "Zapisz projekt…", self.save_project, row=0, column=1)
        ttk.Label(toolbar, text="Lokalnie • bez AI i połączeń sieciowych").grid(row=0, column=2, padx=20)
        self.tabs = ttk.Notebook(outer)
        self.tabs.grid(row=2, column=0, sticky="nsew")
        files, details, channels_host = (ttk.Frame(self.tabs, padding=16) for _ in range(3))
        self.tabs.add(files, text="1. Pliki i pomiary")
        self.tabs.add(details, text="2. Dane raportu i wnioski")
        self.tabs.add(channels_host, text="3. Kanały i PDF")
        # Keep the controls' requested sizes at high DPI; scroll when they do not fit.
        channels_host.columnconfigure(0, weight=1)
        channels_host.rowconfigure(0, weight=1)
        self.channels_canvas = tk.Canvas(channels_host, highlightthickness=0)
        self.channels_canvas.grid(row=0, column=0, sticky="nsew")
        vertical = ttk.Scrollbar(channels_host, command=self.channels_canvas.yview)
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal = ttk.Scrollbar(channels_host, orient="horizontal", command=self.channels_canvas.xview)
        horizontal.grid(row=1, column=0, sticky="ew")
        self.channels_canvas.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        channels = ttk.Frame(self.channels_canvas)
        content = self.channels_canvas.create_window(0, 0, window=channels, anchor="nw")

        def fit_channels(event=None):
            self.channels_canvas.itemconfigure(
                content, width=max(channels.winfo_reqwidth(), self.channels_canvas.winfo_width()),
                height=max(channels.winfo_reqheight(), self.channels_canvas.winfo_height()))
            self.channels_canvas.configure(scrollregion=self.channels_canvas.bbox("all"))

        self.channels_canvas.bind("<Configure>", fit_channels)
        channels.bind("<Configure>", fit_channels)
        files.columnconfigure(1, weight=1)
        for row, (label, variable, picker) in enumerate([
            ("Folder plików PQBox", self.source_folder, self.pick_source),
            ("Folder wynikowy PDF", self.output_folder, self.pick_output),
        ]):
            ttk.Label(files, text=label).grid(row=row, column=0, sticky="w", pady=8)
            self._entry(files, variable, row=row, column=1, sticky="ew", padx=10)
            self._button(files, "Wybierz…", picker, row=row, column=2)
        ttk.Label(files, text="Nazwa pliku PDF").grid(row=2, column=0, sticky="w", pady=8)
        self._entry(files, self.filename, row=2, column=1, sticky="ew", padx=10)
        self._button(files, "Wczytaj pomiary PQBox", self.load_measurements, row=3, column=1, sticky="w", padx=10, pady=12)
        self._button(files, "Wczytaj CSV (Sonel / WinPQ)…", self.pick_csv, row=4, column=1, sticky="w", padx=10)
        ttk.Label(files, text="CSV: program rozpoznaje eksport Sonel Analysis lub WinPQ mobil.\nSonel: Pomiary → zaznacz dane → Raporty → Raport CSV (bez dzielenia pliku).\nDane i opisy zapisane w projekcie nie zawierają kopii pomiarów.", wraplength=670).grid(row=5, column=0, columnspan=3, sticky="w", pady=18)
        ttk.Label(files, text="Przesunięcie czasu PQF [h]").grid(row=6, column=0, sticky="w", pady=8)
        self._entry(files, self.time_offset, row=6, column=1, sticky="ew", padx=10)
        ttk.Label(files, text="Dla dostarczonej sesji +2 h. Porównaj zakres czasu z WinPQ; inne ustawienia zegara wymagają weryfikacji. Po zmianie przesunięcia wczytaj pomiary ponownie.", wraplength=740).grid(row=7, column=0, columnspan=3, sticky="w", pady=8)
        ttk.Label(files, textvariable=self.info, wraplength=740, justify="left").grid(row=8, column=0, columnspan=3, sticky="w", pady=12)
        details.columnconfigure(1, weight=1)
        details.columnconfigure(3, weight=1)
        for i, (key, label) in enumerate(FIELDS.items()):
            row, col = divmod(i, 2)
            ttk.Label(details, text=label).grid(row=row, column=col * 2, sticky="w", padx=(0, 8), pady=5)
            self._entry(details, self.values[key], row=row, column=col * 2 + 1, sticky="ew", padx=(0, 12))
        self.texts = {}
        for row, key, label in [(4, "description", "Opis pomiarów"), (6, "conclusions", "Wnioski / podsumowanie autora")]:
            ttk.Label(details, text=label).grid(row=row, column=0, columnspan=4, sticky="w", pady=(12, 4))
            frame = ttk.Frame(details)
            frame.grid(row=row + 1, column=0, columnspan=4, sticky="nsew")
            text = tk.Text(frame, height=6, wrap="word", font=("Segoe UI", 10), undo=True)
            scroll = ttk.Scrollbar(frame, command=text.yview)
            text.configure(yscrollcommand=scroll.set)
            text.pack(side="left", fill="both", expand=True)
            scroll.pack(side="right", fill="y")
            self.texts[key] = text
            self.controls.append(text)
            details.rowconfigure(row + 1, weight=1)
        channels.columnconfigure(0, weight=1)
        channels.rowconfigure(4, weight=3)
        channels.rowconfigure(7, weight=1)
        self.dates_check = ttk.Checkbutton(channels, text="Sprawdzono daty i zakres pomiaru w WinPQ (wymagane dla PQF)", variable=self.dates_verified)
        self.dates_check.grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.controls.append(self.dates_check)
        ttk.Label(channels, textvariable=self.measurement_period, wraplength=700).grid(row=1, column=0, sticky="w", pady=(0, 8))
        ttk.Label(channels, text="Zaznacz kanały do wykresów i tabel (Ctrl / Shift dla wielu pozycji).").grid(row=2, column=0, sticky="w")
        selection_bar = ttk.Frame(channels)
        selection_bar.grid(row=3, column=0, sticky="w", pady=8)
        self._button(selection_bar, "Podstawowe + widma", self.select_defaults, row=0, column=0)
        self._button(selection_bar, "Wszystkie", lambda: self._select_all(True), row=0, column=1, padx=8)
        self._button(selection_bar, "Wyczyść wybór", lambda: self._select_all(False), row=0, column=2)
        self._button(selection_bar, "Tylko THD(A) i widma", self.select_harmonics, row=0, column=3, padx=8)
        frame = ttk.Frame(channels)
        frame.grid(row=4, column=0, sticky="nsew")
        self.channel_list = tk.Listbox(frame, selectmode="extended", exportselection=False, height=4, font=("Segoe UI", 10))
        scroll = ttk.Scrollbar(frame, command=self.channel_list.yview)
        self.channel_list.configure(yscrollcommand=scroll.set)
        self.channel_list.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.controls.append(self.channel_list)
        self.selected_info = tk.StringVar(value="Wybrano 0 kanałów")
        ttk.Label(channels, textvariable=self.selected_info).grid(row=5, column=0, sticky="w", pady=4)
        self.channel_list.bind("<<ListboxSelect>>", lambda event: self._selection_info())
        ttk.Label(channels, text="Uwagi do danych (uwzględniane w raporcie)").grid(row=6, column=0, sticky="w", pady=(8, 4))
        warning_frame = ttk.Frame(channels)
        warning_frame.grid(row=7, column=0, sticky="nsew")
        self.warnings = tk.Text(warning_frame, width=1, height=3, wrap="word", state="disabled", font=("Segoe UI", 9))
        warning_scroll = ttk.Scrollbar(warning_frame, command=self.warnings.yview)
        self.warnings.configure(yscrollcommand=warning_scroll.set)
        self.warnings.pack(side="left", fill="both", expand=True)
        warning_scroll.pack(side="right", fill="y")
        spectrum_options = ttk.Frame(channels)
        spectrum_options.grid(row=8, column=0, sticky="w", pady=4)
        ttk.Label(spectrum_options, text="Statystyka słupków widma:").pack(side="left", padx=(0, 12))
        for label, value in (("Średnia", "mean"), ("Maksimum", "max"), ("Percentyl 95", "p95")):
            option = ttk.Radiobutton(spectrum_options, text=label, value=value, variable=self.spectrum_statistic)
            option.pack(side="left", padx=5)
            self.controls.append(option)
        ttk.Label(channels, text="Widma: harmoniczne 2–50 z CSV; kolory oznaczają fazy. Brak kanału nie oznacza zera.",
                  wraplength=700).grid(row=9, column=0, sticky="w", pady=4)
        footer = ttk.Frame(outer)
        footer.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        self._button(footer, "Generuj PDF", self.generate, row=0, column=0)
        self.open_pdf_button = self._button(footer, "Otwórz PDF", self.open_pdf, row=0, column=1, padx=8)
        self._button(footer, "Otwórz folder wyników", self.open_output, row=0, column=2)
        self._button(footer, "Eksport danych CSV…", self.export_data, row=0, column=3, padx=8)
        self.progress = ttk.Progressbar(outer, mode="indeterminate")
        self.progress.grid(row=4, column=0, sticky="ew", pady=(10, 5))
        ttk.Label(outer, textvariable=self.status, wraplength=960).grid(row=5, column=0, sticky="w")
        self.open_pdf_button.configure(state="disabled")

    def _selection_info(self):
        self.selected_info.set(f"Wybrano {len(self.channel_list.curselection())} kanałów")

    def _select_all(self, select):
        if select:
            self.channel_list.selection_set(0, "end")
        else:
            self.channel_list.selection_clear(0, "end")
        self._selection_info()

    def _offset(self):
        try:
            offset = float(self.time_offset.get().strip().replace(",", "."))
            if not -14 <= offset <= 14:
                raise ValueError()
            return offset
        except ValueError:
            raise ValueError("Przesunięcie czasu musi być liczbą od −14 do +14 godzin.")

    def _close(self):
        if self.busy:
            messagebox.showinfo("Trwa praca", "Poczekaj na zakończenie odczytu lub generowania raportu.")
        else:
            self.root.destroy()

    def _work(self, operation, success):
        if self.busy:
            return
        self.busy = True
        for control in self.controls:
            control.configure(state="disabled")
        self.progress.start(12)
        def run():
            try:
                result = operation()
                self.events.put(("done", (success, result)))
            except Exception as exc:
                self.events.put(("error", str(exc)))
        threading.Thread(target=run, daemon=True).start()

    def _poll(self):
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "progress":
                    self.status.set(payload)
                    continue
                self.busy = False
                self.progress.stop()
                for control in self.controls:
                    control.configure(state="normal")
                self.open_pdf_button.configure(state="normal" if self.last_pdf else "disabled")
                if kind == "error":
                    self.status.set("Operacja nie powiodła się.")
                    messagebox.showerror("Nie można zakończyć operacji", payload)
                else:
                    callback, result = payload
                    callback(result)
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    def pick_source(self):
        path = filedialog.askdirectory(title="Wybierz folder plików PQBox")
        if path:
            self.source_folder.set(path)

    def pick_output(self):
        path = filedialog.askdirectory(title="Wybierz folder zapisu PDF", mustexist=True)
        if path:
            self.output_folder.set(path)

    def _reset_dataset(self):
        self.dataset = None
        self.dates_verified.set(False)
        self.channel_list.delete(0, "end")
        self.info.set("Nie wczytano pomiarów.")
        self.measurement_period.set("Nie wczytano pomiarów.")
        self._selection_info()
        self.warnings.configure(state="normal")
        self.warnings.delete("1.0", "end")
        self.warnings.configure(state="disabled")

    def _source_changed(self, *_):
        # Output destination and report text do not change the measurement source.
        # Source settings do: retain no dataset that could silently refer to the old input.
        had_data = self.dataset is not None
        self._reset_dataset()
        if had_data:
            self.pending_selection = None
            self.status.set("Zmieniono źródło lub przesunięcie czasu. Wczytaj pomiary ponownie.")

    def load_measurements(self):
        folder = Path(self.source_folder.get().strip())
        if not self.source_folder.get().strip() or not folder.is_dir():
            messagebox.showerror("Folder pomiarów", "Wskaż istniejący folder z plikami PQBox.")
            return
        try:
            offset = self._offset()
        except ValueError as exc:
            messagebox.showerror("Przesunięcie czasu", str(exc))
            return
        self.source_kind = "pqf"
        self.csv_path = ""
        self._reset_dataset()
        self.status.set("Odczyt plików PQBox…")
        def operation():
            from .pqf import import_pqf
            return import_pqf(folder, time_offset_hours=offset)
        self._work(operation, self._loaded)

    def pick_csv(self):
        path = filedialog.askopenfilename(title="Wybierz eksport CSV z Sonel Analysis lub WinPQ mobil", filetypes=[("Pliki CSV", "*.csv"), ("Wszystkie pliki", "*.*")])
        if path:
            self.source_kind = "csv"
            self.csv_path = path
            self._load_csv(path)

    def _load_csv(self, path):
        self._reset_dataset()
        self.status.set("Odczyt eksportu CSV…")
        def operation():
            from .csv_import import import_csv
            return import_csv(Path(path))
        self._work(operation, self._loaded)

    def _loaded(self, dataset):
        self.dates_verified.set(False)
        self.measurement_period.set(f"Okres do sprawdzenia: {dataset.times[0]:%Y-%m-%d %H:%M:%S} — {dataset.times[-1]:%Y-%m-%d %H:%M:%S}")
        self.dataset = dataset
        self.channel_names = list(dataset.channels)
        for name in self.channel_names:
            unit = dataset.units.get(name, "")
            self.channel_list.insert("end", f"{name}  [{unit}]" if unit else name)
        if self.pending_selection is not None:
            selected = self.pending_selection
            self.pending_selection = None
            for i, name in enumerate(self.channel_names):
                if name in selected:
                    self.channel_list.selection_set(i)
        else:
            self.select_defaults()
        self._selection_info()
        self.info.set(f"Format: {dataset.metadata.get('import_type', 'PQBox')}\n"
                      f"Źródło: {'PQBox' if self.source_kind == 'pqf' else self.csv_path}\n"
                      f"Okres: {dataset.times[0]:%Y-%m-%d %H:%M:%S} — {dataset.times[-1]:%Y-%m-%d %H:%M:%S}\n"
                      f"Próbki: {len(dataset.times):,}  •  Kanały: {len(dataset.channels)}  •  Pliki źródłowe: {len(dataset.source_files)}".replace(",", " "))
        self.warnings.configure(state="normal")
        self.warnings.delete("1.0", "end")
        self.warnings.insert("1.0", "\n\n".join(dataset.warnings) or "Brak ostrzeżeń importu. Nie jest to ocena zgodności z normą.")
        self.warnings.configure(state="disabled")
        self.status.set("Pomiary wczytane. Uzupełnij dane raportu i wybierz kanały.")

    def select_defaults(self):
        if not self.dataset:
            return
        from .csv_import import default_channels
        selected = default_channels(self.dataset)
        self.channel_list.selection_clear(0, "end")
        for i, name in enumerate(self.channel_names):
            if name in selected:
                self.channel_list.selection_set(i)
        self._selection_info()

    def metadata(self):
        result = {key: value.get().strip() for key, value in self.values.items()}
        result.update({key: text.get("1.0", "end-1c").strip() for key, text in self.texts.items()})
        result["spectrum_statistic"] = self.spectrum_statistic.get()
        return result

    def select_harmonics(self):
        if not self.dataset:
            return
        from .csv_import import harmonic_report_channels
        selected = set(harmonic_report_channels(self.dataset))
        self.channel_list.selection_clear(0, "end")
        for i, name in enumerate(self.channel_names):
            if name in selected:
                self.channel_list.selection_set(i)
        self._selection_info()
        if not selected:
            self.status.set("Brak kanałów THD(A) i harmonicznych. Wczytaj pełny CSV z WinPQ mobil.")

    def generate(self):
        if self.dataset is None:
            messagebox.showerror("Brak danych", "Najpierw wczytaj pomiary.")
            return
        if self.source_kind == "pqf" and not self.dates_verified.get():
            self.tabs.select(2)
            self.channels_canvas.yview_moveto(0)
            self.channels_canvas.xview_moveto(0)
            self.dates_check.focus_set()
            messagebox.showerror("Sprawdź daty", f"{self.measurement_period.get()}\n\nPorównaj ten zakres z WinPQ. Następnie zaznacz „Sprawdzono daty i zakres pomiaru” na górze zakładki Kanały i PDF.")
            return
        names = [self.channel_names[i] for i in self.channel_list.curselection()]
        if not names:
            messagebox.showerror("Brak kanałów", "Wybierz co najmniej jeden kanał do raportu.")
            return
        try:
            filename = validate_filename(self.filename.get())
            folder = Path(self.output_folder.get().strip())
            if not self.output_folder.get().strip() or not folder.is_dir():
                raise ValueError("Wskaż istniejący folder zapisu PDF.")
            metadata = self.metadata()
            if not metadata["title"]:
                raise ValueError("Wpisz tytuł raportu.")
            destination = folder / filename
            if destination.exists() and not messagebox.askyesno("Raport już istnieje", f"Czy nadpisać plik?\n{destination}"):
                return
            dataset = self.dataset.subset(names)
        except ValueError as exc:
            messagebox.showerror("Sprawdź dane", str(exc))
            return
        self.filename.set(filename)
        self.status.set("Tworzenie wykresów i raportu PDF…")
        def operation():
            from .pdf_report import generate_report
            return generate_report(dataset, metadata, destination, progress=lambda message: self.events.put(("progress", message)))
        self._work(operation, self._generated)

    def _generated(self, path):
        self.last_pdf = Path(path)
        self.open_pdf_button.configure(state="normal")
        self.status.set(f"PDF zapisany: {path}")
        messagebox.showinfo("Raport gotowy", f"Zapisano raport PDF:\n{path}")

    def _open_path(self, path):
        try:
            os.startfile(str(path))
        except Exception as exc:
            messagebox.showerror("Nie można otworzyć", str(exc))

    def open_pdf(self):
        if self.last_pdf:
            self._open_path(self.last_pdf)

    def open_output(self):
        folder = Path(self.output_folder.get().strip())
        if not self.output_folder.get().strip() or not folder.is_dir():
            messagebox.showerror("Folder wyników", "Wskaż istniejący folder wyników.")
            return
        self._open_path(folder)

    def save_project(self):
        try:
            filename = validate_filename(self.filename.get())
            offset = self._offset()
        except ValueError as exc:
            messagebox.showerror("Nazwa PDF", str(exc))
            return
        path = filedialog.asksaveasfilename(title="Zapisz projekt (opisy i ustawienia)", defaultextension=".json", filetypes=[("Projekt LOPI", "*.json")])
        if not path:
            return
        data = {"format": "lopi-pq-project", "version": 1, "metadata": self.metadata(),
                "source_folder": self.source_folder.get(), "output_folder": self.output_folder.get(),
                "filename": filename, "source_kind": self.source_kind, "csv_path": self.csv_path,
                "time_offset_hours": offset,
                "selected_channels": [self.channel_names[i] for i in self.channel_list.curselection()] if self.dataset else (self.pending_selection or [])}
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=Path(path).parent, suffix=".tmp", delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(data, stream, ensure_ascii=False, indent=2)
            os.replace(temporary, path)
            self.status.set(f"Projekt zapisany: {path}")
        except Exception as exc:
            messagebox.showerror("Błąd zapisu projektu", str(exc))
        finally:
            if temporary and temporary.exists():
                temporary.unlink()

    def load_project(self):
        path = filedialog.askopenfilename(title="Otwórz projekt LOPI", filetypes=[("Projekt LOPI", "*.json")])
        if not path:
            return
        try:
            if Path(path).stat().st_size > 2_000_000:
                raise ValueError("Plik projektu jest zbyt duży.")
            data = validate_project(json.loads(Path(path).read_text(encoding="utf-8-sig")))
        except Exception as exc:
            messagebox.showerror("Błąd projektu", str(exc))
            return
        self._reset_dataset()
        self.pending_selection = data.get("selected_channels", [])
        self.source_folder.set(data.get("source_folder", ""))
        self.output_folder.set(data.get("output_folder", ""))
        self.filename.set(data["filename"])
        self.source_kind = data.get("source_kind", "pqf")
        self.csv_path = data.get("csv_path", "")
        self.time_offset.set(str(data.get("time_offset_hours", 2)))
        self.spectrum_statistic.set(data["metadata"].get("spectrum_statistic", "mean"))
        for key, variable in self.values.items():
            variable.set(data["metadata"].get(key, ""))
        for key, text in self.texts.items():
            text.delete("1.0", "end")
            text.insert("1.0", data["metadata"].get(key, ""))
        self.status.set("Projekt otwarty. Ponownie wczytaj pomiary, aby sprawdzić aktualne pliki źródłowe.")
        self.tabs.select(0)
        if self.source_kind == "csv":
            self.info.set(f"Projekt używał eksportu CSV:\n{self.csv_path}\nUżyj przycisku „Wczytaj CSV (Sonel / WinPQ)…”.")

    def export_data(self):
        if self.dataset is None:
            messagebox.showerror("Brak danych", "Najpierw wczytaj pomiary.")
            return
        try:
            filename = Path(validate_filename(self.filename.get())).stem + "_dane.csv"
        except ValueError as exc:
            messagebox.showerror("Nazwa pliku", str(exc))
            return
        path = filedialog.asksaveasfilename(title="Eksport wszystkich wczytanych kanałów do CSV", initialdir=self.output_folder.get() or None, initialfile=filename, defaultextension=".csv", filetypes=[("CSV", "*.csv")], confirmoverwrite=True)
        if not path:
            return
        dataset = self.dataset
        self.status.set("Eksport danych CSV…")
        def operation():
            from .csv_import import export_csv
            export_csv(dataset, Path(path))
            return path
        self._work(operation, lambda result: self.status.set(f"CSV zapisany: {result}"))


def main():
    root = tk.Tk()
    style = ttk.Style(root)
    if "vista" in style.theme_names():
        style.theme_use("vista")
    style.configure("TLabel", font=("Segoe UI", 10))
    style.configure("TButton", padding=(10, 5))
    Application(root)
    root.mainloop()
