"""Local PDF reports; no network access and no automatic technical conclusions."""
from __future__ import annotations

import math
import os
import re
import sys
import tempfile
from io import BytesIO
from pathlib import Path
from statistics import fmean, median
from xml.sax.saxutils import escape
from datetime import datetime


def _sonel_channel(name):
    """Read only the explicit label structure, retaining quantity definitions."""
    return re.fullmatch(
        r"(?P<quantity>.+?) (?P<wire>\*?L[123]|L12|L23|L31|\*?N|N-PE|Σ) "
        r"(?P<statistic>śred\.|min\.|maks\.|chwil\.) (?P<aggregation>\d+(?:[.,]\d+)? (?:s|min|h))", name)


def _family(name):
    sonel = _sonel_channel(name)
    if sonel:
        quantity, wire, statistic, aggregation = sonel.groups()
        if re.fullmatch(r"\*?L[123]", wire):
            wire = "*L*" if wire.startswith("*") else "L*"
        elif wire in ("L12", "L23", "L31"):
            wire = "L**"
        return f"sonel:{quantity} {wire} {statistic} {aggregation}"
    name = name.rstrip("_")
    if re.fullmatch(r"THD_\(A\)_I[123N]", name, re.I):
        return "THD_(A)_I*"
    family = re.sub(r"(?i)L[123](?!\d)", "L*", name)
    family = re.sub(r"(?i)^(THD_I)[123](?!\d)", r"\1*", family)
    if re.fullmatch(r"[PQD]total", name, re.I):
        return name[0].upper() + "total"
    if re.fullmatch(r"Stotal", name, re.I):
        return name[0].upper() + "L*"
    if name.lower() == "tg_(fi)":
        return "tg_(fi)_total"
    return family


def section_title(names):
    sonel = _sonel_channel(names[0])
    if sonel:
        quantity, wire, statistic, aggregation = sonel.groups()
        titles = {"U": "Napięcia", "U DC": "Napięcia DC", "I": "Prądy",
                  "P": "Moc czynna P", "Q1": "Moc bierna Q1", "QB": "Moc bierna QB",
                  "Q": "Moc bierna Q", "D": "Moc D", "SN": "Moc SN", "Sn": "Moc Sn", "S": "Moc pozorna S",
                  "THD U": "THD napięcia", "THD I": "THD prądu",
                  "f": "Częstotliwość", "PF": "Współczynnik PF", "cos(φ)": "Współczynnik cosφ"}
        title = titles.get(quantity, quantity)
        if quantity.startswith("tg(φ)"):
            title = "Współczynnik " + quantity
        wire_label = ("suma Σ" if wire == "Σ" else "międzyfazowe" if wire in ("L12", "L23", "L31")
                      else wire if wire in ("N", "*N", "N-PE") else "fazy")
        return f"{title} — {wire_label}, {statistic} {aggregation}"
    family = _family(names[0]).lower()
    suffix = ""
    totals = {"ptotal": "pl*", "qtotal": "ql*", "dtotal": "dl*", "tg_(fi)_total": "tg_(fi)_l*"}
    if family in totals:
        family, suffix = totals[family], " — total"
    if family.endswith("_min"):
        family, suffix = family[:-4], " — kanały minimum"
    elif family.endswith("_max"):
        family, suffix = family[:-4], " — kanały maksimum"
    titles = {"ul*": "Napięcia fazowe", "il*": "Prądy fazowe",
              "thdl*": "Odkształcenia harmoniczne napięcia",
              "thd_i*": "Odkształcenia harmoniczne prądu",
              "thd_(a)_i*": "Prąd harmonicznych THD(A)",
              "pl*": "Moc czynna", "ql*": "Moc bierna",
              "dl*": "Moc dystorsji", "sl*": "Moc pozorna",
              "tg_(fi)_l*": "Współczynnik tgφ", "f": "Częstotliwość",
              "pfl*": "Współczynnik mocy"}
    return titles.get(family, " / ".join(names)) + suffix


def presentation_scale(name, unit):
    """Scale for presentation only; original imported values remain unchanged."""
    if unit.lower() in ("w", "var", "va"):
        return 0.001, {"w": "kW", "var": "kvar", "va": "kVA"}[unit.lower()]
    if not unit and (name.lower().startswith(("tg_", "pf", "cos"))):
        return 1.0, "1"
    return 1.0, unit


def channel_color(name, index=0):
    palette = ["#c62d36", "#23833f", "#235bb2", "#8b54a2"]
    phase = re.search(r"(?i)(?:L|THD_I|THD_\(A\)_I)([123])(?!\d)", name)
    if phase:
        return palette[int(phase.group(1)) - 1]
    if name in ("THD_(A)_IN", "THD_IN") or "total" in name.lower() or name.rstrip("_").lower() == "tg_(fi)" or "Σ" in name:
        return palette[3]
    return palette[index % len(palette)]


def channel_groups(channels, units, max_size=4):
    """Keep quantities/units separate and combine only identically named phases."""
    buckets = {}
    for name in channels:
        # UL1/UL2, U L1/U L2, THD UL1, etc. Retain min/max and every other token.
        family = _family(name)
        key = (family, units.get(name, ""))
        buckets.setdefault(key, []).append(name)
    result = []
    for names in buckets.values():
        result.extend(names[i:i + max_size] for i in range(0, len(names), max_size))
    return result


def channel_statistics(values):
    valid = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    return {"count": len(valid), "missing": len(values) - len(valid),
            "min": min(valid) if valid else None,
            "mean": fmean(valid) if valid else None,
            "max": max(valid) if valid else None}


def report_group_order(names):
    """Presentation order only; retain unknown channels after known quantities."""
    sonel = _sonel_channel(names[0])
    if sonel:
        quantity, wire, statistic, aggregation = sonel.groups()
        order = {"U": 0, "U DC": 0, "I": 1, "P": 2, "Q": 3, "Q1": 3, "QB": 3,
                 "D": 4, "SN": 4, "Sn": 4, "S": 5, "THD U": 6, "THD I": 7, "f": 9}
        rank = 8 if quantity.startswith("tg(φ)") else order.get(quantity, 10)
        return rank, 0, False, quantity, {"śred.": 0, "maks.": 1, "min.": 2, "chwil.": 3}[statistic], aggregation, wire == "Σ", wire
    family = _family(names[0]).lower()
    suffix = 1 if family.endswith("_max") else 2 if family.endswith("_min") else 0
    base = re.sub(r"_(min|max)$", "", family)
    totals = {"ptotal": "pl*", "qtotal": "ql*", "dtotal": "dl*", "tg_(fi)_total": "tg_(fi)_l*"}
    total = base in totals
    base = totals.get(base, base)
    order = {"ul*": 0, "il*": 1, "pl*": 2, "ql*": 3, "dl*": 4,
             "sl*": 5, "thdl*": 6, "thd_i*": 7, "thd_(a)_i*": 7, "tg_(fi)_l*": 8, "f": 9}
    return order.get(base, 10), suffix, total


def _is_tangent_channel(name):
    sonel = _sonel_channel(name)
    return (sonel is not None and sonel.group("quantity").startswith("tg(φ)")) or _family(name).lower() in ("tg_(fi)_l*", "tg_(fi)_total")


def central_plot_range(series):
    """Linear-interpolated P1/P99 across plotted values and count outside them."""
    values = sorted(float(v) for channel in series for v in channel
                    if v is not None and math.isfinite(float(v)))
    if not values:
        return None
    def percentile(p):
        position = (len(values) - 1) * p
        lower = int(position)
        upper = min(lower + 1, len(values) - 1)
        return values[lower] + (values[upper] - values[lower]) * (position - lower)
    low, high = percentile(0.01), percentile(0.99)
    return low, high, sum(v < low or v > high for v in values)


def plot_samples(times, values, expected_interval=None):
    """Insert NaNs at missing samples and gaps; never interpolate across outages."""
    if len(times) != len(values):
        raise ValueError("Liczba wartości kanału nie odpowiada liczbie znaczników czasu.")
    deltas = [(b - a).total_seconds() for a, b in zip(times, times[1:])]
    positive = [d for d in deltas if d > 0]
    interval = expected_interval or (median(positive) if positive else None)
    xs, ys = [], []
    for i, (time, value) in enumerate(zip(times, values)):
        if i and interval and deltas[i - 1] > interval * 1.5:
            xs.append(time)
            ys.append(float("nan"))
        xs.append(time)
        ys.append(float(value) if value is not None and math.isfinite(float(value)) else float("nan"))
    return xs, ys


def isolated_plot_samples(xs, ys):
    """Return finite points with no finite neighbour after gap insertion."""
    finite = [math.isfinite(y) for y in ys]
    indices = [i for i, valid in enumerate(finite) if valid
               and (i == 0 or not finite[i - 1])
               and (i == len(finite) - 1 or not finite[i + 1])]
    return [xs[i] for i in indices], [ys[i] for i in indices]


def _font_setup():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import matplotlib
    font_dir = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
    # DejaVu ships with matplotlib and has Polish letters; no platform font required.
    normal, bold = font_dir / "DejaVuSans.ttf", font_dir / "DejaVuSans-Bold.ttf"
    pdfmetrics.registerFont(TTFont("LopiBody", str(normal)))
    pdfmetrics.registerFont(TTFont("LopiBold", str(bold)))
    pdfmetrics.registerFontFamily("LopiBody", normal="LopiBody", bold="LopiBold", italic="LopiBody", boldItalic="LopiBold")


def generate_report(dataset, metadata: dict, output_path: Path, progress=None) -> Path:
    """Build a standalone PDF. progress receives a short Polish status string."""
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    import matplotlib.dates as mdates
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, KeepTogether
    from reportlab.platypus.tableofcontents import TableOfContents
    from .harmonics import harmonic_channel, validate_thda, spectrum_groups

    side_margin = 15 * mm
    content_width = A4[0] - 2 * side_margin

    if not dataset.times or not dataset.channels:
        raise ValueError("Brak pomiarów do raportu.")
    if any(b <= a for a, b in zip(dataset.times, dataset.times[1:])):
        raise ValueError("Znaczniki czasu muszą być uporządkowane i unikalne.")
    for values in dataset.channels.values():
        if len(values) != len(dataset.times):
            raise ValueError("Kanały mają różną liczbę próbek.")
    # Validate dimensions before creating a PDF or rendering any chart.
    for name in dataset.channels:
        if validate_thda(name, dataset.units.get(name, "")):
            if any(value is not None and math.isfinite(value) and value < 0
                   for value in dataset.channels[name]):
                raise ValueError(f"Kanał {name}: amplituda THD(A) nie może być ujemna.")
    spectra = spectrum_groups(dataset, statistic=metadata.get("spectrum_statistic", "mean"))
    time_channels = [n for n in dataset.channels if harmonic_channel(n, dataset.units.get(n, "")) is None]
    spectrum_warnings = [warning for group in spectra for warning in group.get("warnings", [])]
    all_warnings = list(dataset.warnings) + spectrum_warnings
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _font_setup()
    body = ParagraphStyle("body", fontName="LopiBody", fontSize=10.5, leading=14, spaceAfter=7,
                          allowWidows=0, allowOrphans=0)
    title = ParagraphStyle("title", parent=body, fontName="LopiBold", fontSize=23, leading=30, spaceAfter=18)
    heading = ParagraphStyle("heading", parent=body, fontName="LopiBold", fontSize=15, leading=20, spaceBefore=8, spaceAfter=13, keepWithNext=True)
    subheading = ParagraphStyle("subheading", parent=heading, fontSize=11.5, leading=16, spaceAfter=8)
    small = ParagraphStyle("small", parent=body, fontSize=9, leading=12, spaceAfter=6, textColor=colors.HexColor("#444444"))
    cell = ParagraphStyle("cell", parent=body, fontSize=9, leading=12, spaceAfter=0)
    numeric_cell = ParagraphStyle("numeric_cell", parent=cell, alignment=TA_RIGHT)
    header_cell = ParagraphStyle("header_cell", parent=cell, fontName="LopiBold")
    caption = ParagraphStyle("caption", parent=small, alignment=TA_CENTER)

    def para(value, style=body):
        return Paragraph(escape(str(value)).replace("\n", "<br/>"), style)

    def chapter(value, level=0):
        p = para(value, heading if level == 0 else subheading)
        p.toc_level = level
        p.bookmark = "section_" + str(len(bookmarks))
        bookmarks.append(p.bookmark)
        return p

    bookmarks = []

    def text_value(key):
        value = metadata.get(key, "")
        if key == "instrument" and not str(value).strip():
            value = dataset.metadata.get("instrument", "")
        if isinstance(value, (list, tuple)):
            value = ", ".join(str(v) for v in value)
        return str(value).strip() or "Nie podano"

    def author_text(key):
        # Keep author paragraphs independent so page breaks respect paragraph boundaries.
        return [para(block.strip()) for block in re.split(r"\n\s*\n", text_value(key)) if block.strip()]

    def table(rows, widths, header=True, numeric=False, numeric_from=2):
        cells = [[para(v, header_cell if header and r == 0 else numeric_cell if numeric and c >= numeric_from else cell)
                  for c, v in enumerate(row)] for r, row in enumerate(rows)]
        widths = [width * content_width / sum(widths) for width in widths]
        t = Table(cells, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT", splitInRow=1)
        commands = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#BFBFBF")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]
        if header:
            commands.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E0E0E0")))
            commands.append(("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F7F7")]))
        else:
            commands.append(("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F1F1F1")))
        t.setStyle(TableStyle(commands))
        return t

    def format_time(value):
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value)
            except ValueError:
                return value
        return value.strftime("%d.%m.%Y %H:%M:%S")

    measurement_start = dataset.metadata.get("measurement_start") or dataset.times[0]
    measurement_end = dataset.metadata.get("measurement_end") or dataset.times[-1]
    interval_value = dataset.metadata.get("interval_seconds")
    try:
        interval = float(interval_value) if interval_value else None
        if interval is not None and (not math.isfinite(interval) or interval <= 0):
            interval = None
    except (ValueError, TypeError):
        interval = None
    story = []
    asset_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    logo = asset_root / "assets" / "lopi-logo.png"
    if logo.exists():
        image = Image(str(logo), width=48 * mm, height=48 * mm * 314 / 735)
        image.hAlign = "LEFT"
        story.extend([image, Spacer(1, 22 * mm)])
    story.append(para("RAPORT Z POMIARÓW", small))
    story.append(para(text_value("title"), title))
    story.append(Spacer(1, 8 * mm))
    story.append(table([
        ["Numer raportu", text_value("report_number")],
        ["Wykonawca", text_value("company")], ["Obiekt", text_value("object_name")],
        ["Adres", text_value("address")], ["Autorzy", text_value("authors")],
        ["Analizator", text_value("instrument")],
        ["Okres pomiaru", f"{format_time(measurement_start)} – {format_time(measurement_end)}"],
        ["Interwał eksportu", f"{interval:g} s" if interval else "Nie potwierdzono"],
        ["Liczba próbek / kanałów", f"{len(dataset.times)} / {len(dataset.channels)}"],
    ], [42 * mm, 118 * mm], header=False))
    story.append(Spacer(1, 10 * mm))
    story.append(para("Opracowanie wyników pomiarów instalacji elektrycznej", small))
    story.extend([PageBreak(), para("Spis treści", heading)])
    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle("toc_chapter", parent=body, fontName="LopiBold", fontSize=11, leading=17, spaceBefore=10),
        ParagraphStyle("toc_section", parent=body, fontSize=9.5, leading=15, leftIndent=12, firstLineIndent=0, spaceBefore=3),
    ]
    story.append(toc)
    story.extend([PageBreak(), chapter("1. Wstęp")])
    if metadata.get("purpose"):
        story.extend([para("Cel pomiarów", subheading), *author_text("purpose")])
    story.extend([para("Opis pomiarów", subheading), *author_text("description")])
    if metadata.get("method"):
        story.extend([para("Metoda pomiaru — opis autora", subheading), *author_text("method")])
    story.extend([para("Okres i zakres opracowania", subheading),
                  para(f"Okres pomiaru: {format_time(measurement_start)} – {format_time(measurement_end)}. Opracowanie obejmuje {len(dataset.channels)} kanałów oraz {len(dataset.times)} znaczników próbek."),
                  para("Sposób prezentacji wyników", subheading),
                  para("Statystyki obliczono z wszystkich prawidłowych wartości każdego kanału. Braki i wartości nieprawidłowe pominięto w obliczeniach, a na wykresie pozostawiono przerwy. Średnia jest średnią arytmetyczną próbek, bez ważenia czasem. Minimum i maksimum opisują dostarczony kanał; nie są automatycznie ekstremami półokresowymi."),
                  para("Wykresy zawierają wszystkie próbki, bez redukcji liczby punktów. Interpretację i wnioski wprowadza autor. Szczegółowe informacje o źródłach, znacznikach czasu i ograniczeniach importu znajdują się w załączniku A.")])
    story.extend([para("Zakres ograniczeń", subheading),
                  para("Raport nie stanowi automatycznej oceny zgodności z normą. Ta wersja aplikacji nie obsługuje odczytu zdarzeń PQ, matrycy zdarzeń ani automatycznej oceny normatywnej. Brak tych sekcji nie oznacza braku zdarzeń ani zgodności z normą.")])
    if all_warnings:
        story.append(para(f"Uwagi do danych i prezentacji: {len(all_warnings)}. Ich pełna treść znajduje się w załączniku A; należy uwzględnić je przy interpretacji wyników.", small))

    groups = sorted(channel_groups(time_channels, dataset.units), key=report_group_order)
    buffers = []
    deltas = [(b - a).total_seconds() for a, b in zip(dataset.times, dataset.times[1:])]
    typical = interval or (median(deltas) if deltas else None)
    for index, names in enumerate(groups, start=1):
        if progress:
            progress(f"Wykres {index} z {len(groups)}")
        friendly_title = section_title(names)
        story.append(PageBreak())
        if index == 1:
            story.append(chapter("2. Wyniki pomiarów"))
        story.append(chapter(f"2.{index}. {friendly_title}", level=1))
        if all(name in dataset.metadata.get('combined_tangent_channels', []) for name in names):
            story.append(para("Kanał połączony: suma wartości tgφ L+, C−, L− i C+ z zachowaniem znaków. Suma Σ pochodzi z kanałów Σ analizatora, nie z sumy faz. Brak składowej oznacza brak wyniku.", small))
        unit = dataset.units.get(names[0], "")
        scale, display_unit = presentation_scale(names[0], unit)
        zoom_range = central_plot_range([dataset.channels[n] for n in names]) if _is_tangent_channel(names[0]) else None
        fig = Figure(figsize=(content_width / 72, 5.25 if zoom_range else 4.65), dpi=180, layout="constrained")
        FigureCanvasAgg(fig)
        axes = list(fig.subplots(2, 1, sharex=True)) if zoom_range else [fig.add_subplot(111)]
        ax = axes[0]
        for j, name in enumerate(names):
            xs, ys = plot_samples(dataset.times, dataset.channels[name], typical)
            ys = [y * scale for y in ys]
            isolated_x, isolated_y = isolated_plot_samples(xs, ys)
            color = channel_color(name, j)
            label = name if _sonel_channel(name) or len(name) < 50 else name[:47] + "…"
            for target_ax in axes:
                target_ax.plot(xs, ys, color=color, linewidth=0.65, label=label,
                               marker="." if len(xs) < 3 else None, markersize=3)
                if isolated_x:
                    target_ax.plot(isolated_x, isolated_y, color=color, linestyle="None",
                                   marker="o", markersize=3, label="_nolegend_")
        locator = mdates.AutoDateLocator(minticks=3, maxticks=6)
        axes[-1].xaxis.set_major_locator(locator)
        axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%d.%m\n%H:%M"))
        for target_ax in axes:
            target_ax.tick_params(labelsize=9)
            target_ax.set_ylabel(display_unit or "Jednostka niepodana", fontsize=9)
            target_ax.grid(True, color="#dddddd", linewidth=0.5)
            for spine in target_ax.spines.values():
                spine.set_color("#bbbbbb")
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.32 if zoom_range else 1.17), ncol=2, fontsize=9, frameon=False)
        if zoom_range:
            low, high, outside = zoom_range
            ax.set_title("Pełny zakres — wszystkie wartości", fontsize=9, loc="left")
            if low == high:
                padding = max(abs(low) * 0.05, 0.01)
                axes[1].set_ylim(low - padding, high + padding)
            else:
                axes[1].set_ylim(low, high)
            axes[1].set_title("Powiększenie — zakres P1–P99", fontsize=9, loc="left")
        buf = BytesIO()
        fig.savefig(buf, format="png", dpi=180)
        buf.seek(0)
        buffers.append(buf)
        story.append(KeepTogether([Image(buf, width=content_width, height=(133.3 if zoom_range else 118.1) * mm),
                                 para(f"Wykres {index}. {friendly_title}", caption)]))
        if zoom_range:
            low, high, outside = zoom_range
            story.append(para(f"Dolny panel pokazuje zakres P1–P99 wyznaczony łącznie dla serii: {low:.6g} do {high:.6g}. Poza tym zakresem: {outside} wartości kanałów (liczone oddzielnie dla każdej serii). Wszystkie wartości i ekstrema pozostają w górnym panelu oraz w statystykach tabeli.", small))
        rows = [["Kanał", "Jednostka", "Min", "Średnia", "Max", "Poprawne / braki"]]
        def number(v):
            if v is None:
                return "brak"
            rounded = round(v * scale, 2)
            return f"{0.0 if rounded == 0 else rounded:.2f}".replace(".", ",")
        for name in names:
            stats = channel_statistics(dataset.channels[name])
            rows.append([name, presentation_scale(name, dataset.units.get(name, ""))[1] or "—", number(stats["min"]),
                         number(stats["mean"]), number(stats["max"]), f'{stats["count"]} / {stats["missing"]}'])
        story.extend([Spacer(1, 4 * mm), para(f"Tabela {index}. Statystyki kanałów z pełnego zbioru danych", caption),
                      table(rows, [37 * mm, 22 * mm, 23 * mm, 25 * mm, 23 * mm, 30 * mm], numeric=True),
                      Spacer(1, 4 * mm)])
        if typical:
            story.append(para(f"Typowy odstęp znaczników czasu: {typical:g} s. Przerwy dłuższe niż 1,5 tego odstępu rozdzielają linię wykresu. Odstęp nie potwierdza czasu agregacji urządzenia.", small))
        if scale != 1:
            story.append(para(f"Jednostka eksportu: {unit}. Wykres i tabela przedstawiają wartości w {display_unit} (podzielone przez 1000).", small))
        story.append(para("Brakujące wartości nie oznaczają zera. Statystyki dotyczą kanału źródłowego; jednostka 1 oznacza wielkość bezwymiarową.", small))

    statistic_labels = {"mean": "średnia arytmetyczna", "max": "maksimum",
                        "p95": "percentyl P95 (interpolacja liniowa)"}
    phase_colors = {"L1": "#c62d36", "L2": "#23833f", "L3": "#235bb2", "N": "#8b54a2"}
    for spectrum_index, spectrum in enumerate(spectra, start=1):
        index = len(groups) + spectrum_index
        if progress:
            progress(f"Widmo {spectrum_index} z {len(spectra)}")
        kind = spectrum["kind"]
        phases = ["L1", "L2", "L3"] + (["N"] if kind == "I" else [])
        display_unit = spectrum["unit"]
        statistic_label = statistic_labels[spectrum["statistic"]]
        friendly_title = "Widmo harmonicznych napięcia" if kind == "U" else "Widmo harmonicznych prądu"
        story.append(PageBreak())
        if index == 1:
            story.append(chapter("2. Wyniki pomiarów"))
        story.append(chapter(f"2.{index}. {friendly_title}", level=1))
        story.append(para(f"Statystyka: {statistic_label}. Okres: {format_time(dataset.times[0])} – {format_time(dataset.times[-1])}.", small))
        fig = Figure(figsize=(content_width / 72, 6.15), dpi=180, layout="constrained")
        FigureCanvasAgg(fig)
        axes = list(fig.subplots(len(phases), 1, sharex=True))
        orders = [row["order"] for row in spectrum["rows"]]
        for ax, phase in zip(axes, phases):
            values = [row["values"].get(phase) for row in spectrum["rows"]]
            valid = [(order, value) for order, value in zip(orders, values) if value is not None]
            if valid:
                ax.bar([x for x, _ in valid], [y for _, y in valid], width=0.75,
                       color=phase_colors[phase], label=phase, zorder=3)
            else:
                ax.text(0.5, 0.5, "Brak ważnych danych", transform=ax.transAxes,
                        ha="center", va="center", fontsize=10)
                ax.plot([], [], color=phase_colors[phase], linewidth=5, label=phase)
            missing = [order for order, value in zip(orders, values) if value is None]
            if missing and valid:
                # An x under the axis identifies missing bins independently of the data scale.
                ax.plot(missing, [-0.045] * len(missing), transform=ax.get_xaxis_transform(),
                        marker="x", linestyle="None", color="#666666", markersize=3, clip_on=False)
            ax.set_ylabel(f"[{display_unit}]", fontsize=9)
            ax.set_xlim(1, 51)
            ax.set_ylim(bottom=0)
            ax.grid(axis="y", color="#dddddd", linewidth=0.5, zorder=0)
            ax.tick_params(labelsize=9)
            ax.legend(loc="upper right", fontsize=9, frameon=False)
            for spine in ax.spines.values():
                spine.set_color("#bbbbbb")
        axes[-1].set_xticks([2, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50])
        axes[-1].set_xlabel("Rząd harmonicznej h", fontsize=9)
        buf = BytesIO()
        fig.savefig(buf, format="png", dpi=180)
        buf.seek(0)
        buffers.append(buf)
        story.append(Image(buf, width=content_width, height=156.2 * mm))
        story.append(para(f"Wykres {index}. {friendly_title} — {statistic_label}", caption))
        story.append(para("Kolory oznaczają fazy; N oznacza przewód neutralny. Każdy słupek przedstawia wybraną statystykę danej harmonicznej z ważnych próbek. Nie zastosowano progów normatywnych ani skali procentu limitu. Znak × pod osią oznacza brak wyniku dla danego rzędu; brak nie oznacza zera.", small))
        story.append(PageBreak())
        story.append(para(f"{friendly_title} — tabela wartości", subheading))
        story.append(para(f"Tabela {index}. Rzędy 2–50; {statistic_label}. n — liczba ważnych próbek użytych do wyznaczenia wyniku; N — przewód neutralny. Znak — oznacza brak wyniku. Obliczenia z pełnej dokładności danych; prezentacja do dwóch miejsc po przecinku.", small))
        rows = [["h"] + [label for phase in phases for label in (f"{phase} [{display_unit}]", f"n {phase}")]]
        for row in spectrum["rows"]:
            result = [str(row["order"])]
            for phase in phases:
                value = row["values"].get(phase)
                result.extend(["—" if value is None else f"{0.0 if round(value, 2) == 0 else value:.2f}".replace(".", ","),
                               str(row["counts"].get(phase, 0))])
            rows.append(result)
        pair_width = 148 / len(phases)
        story.append(table(rows, [12 * mm] + [width * mm for _ in phases for width in (pair_width * 0.56, pair_width * 0.44)], numeric=True, numeric_from=1))
        story.append(para("Wartości pominięte z powodu braków lub flag nie są liczone jako zera. Przedstawiona statystyka nie jest automatyczną oceną zgodności z normą.", small))

    story.extend([PageBreak(), chapter("3. Wnioski autora"), *author_text("conclusions")])
    story.extend([PageBreak(), chapter("Załącznik A. Informacje techniczne"),
                  para("Źródła i znaczniki czasu", subheading)])
    if dataset.metadata.get("import_type"):
        story.append(para(f"Format źródła: {dataset.metadata['import_type']}."))
    if dataset.metadata.get("instrument"):
        story.append(para(f"Analizator zapisany w eksporcie: {dataset.metadata['instrument']}."))
    meaning = dataset.metadata.get("timestamp_meaning")
    story.append(para(f"Znaczenie znaczników czasu: {meaning}" if meaning else
                      "Znaczenie znaczników czasu (początek lub koniec interwału) nie zostało potwierdzone w metadanych."))
    if dataset.metadata.get("measurement_start"):
        story.append(para("Początek pomiaru na stronie tytułowej pochodzi z metadanych importu i może poprzedzać znacznik pierwszej próbki."))
    story.append(para(f"Zakres znaczników próbek: {format_time(dataset.times[0])} – {format_time(dataset.times[-1])}."))
    for source in dataset.source_files:
        story.append(para(Path(source).name, small))
    if spectra:
        story.append(para("Metoda wyznaczania widm", subheading))
        story.append(para(f"Wybrana statystyka: {statistic_labels[metadata.get('spectrum_statistic', 'mean')]}. Każdy rząd i każda faza są obliczane niezależnie z wszystkich ważnych próbek kanału. Średnia oznacza średnią arytmetyczną bez ważenia czasem, a maksimum - największą ważną wartość.", small))
        if metadata.get("spectrum_statistic") == "p95":
            story.append(para("P95: wartości są sortowane rosnąco; pozycja wynosi (n - 1) × 0,95 przy indeksowaniu od zera. Wynik jest interpolowany liniowo między sąsiednimi wartościami. Przy jednej ważnej próbce jest równy tej próbce.", small))
        story.append(para("Źródła: H2_UL1–H50_UL1 oraz odpowiednie kanały UL2/UL3 [%]; H2_I1–H50_I1 oraz odpowiednie kanały I2/I3/IN [A]. Pierwsza harmoniczna nie jest częścią prezentowanego widma 2–50. THD(A) pochodzi z osobnych kanałów źródłowych, a nie z sumowania słupków widma.", small))
    if all_warnings:
        story.append(para("Pełna lista uwag do danych", subheading))
        for i, warning in enumerate(all_warnings, 1):
            story.append(para(f"{i}. {warning}", small))
    else:
        story.append(para("Importer nie zgłosił dodatkowych uwag do danych.", small))

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("LopiBody", 8)
        canvas.setFillColor(colors.HexColor("#555555"))
        if doc.page > 1:
            canvas.setStrokeColor(colors.HexColor("#BFBFBF"))
            canvas.setLineWidth(0.4)
            canvas.line(side_margin, A4[1] - 18 * mm, A4[0] - side_margin, A4[1] - 18 * mm)
            canvas.drawString(side_margin, A4[1] - 15 * mm, "LOPI | Raport z pomiarów")
            report_number = text_value("report_number")
            if len(report_number) <= 45:
                canvas.drawRightString(A4[0] - side_margin, A4[1] - 15 * mm, report_number)
        canvas.drawCentredString(A4[0] / 2, 12.5 * mm, str(doc.page))
        canvas.restoreState()

    class ReportDocument(BaseDocTemplate):
        def afterFlowable(self, flowable):
            if hasattr(flowable, "toc_level"):
                label = flowable.getPlainText()
                self.canv.bookmarkPage(flowable.bookmark)
                self.canv.addOutlineEntry(label, flowable.bookmark, level=flowable.toc_level, closed=False)
                self.notify("TOCEntry", (flowable.toc_level, escape(label), self.page, flowable.bookmark))

    fd, temp_name = tempfile.mkstemp(prefix="lopi_report_", suffix=".pdf", dir=output_path.parent)
    os.close(fd)
    try:
        doc = ReportDocument(temp_name, pagesize=A4, leftMargin=side_margin, rightMargin=side_margin,
                                topMargin=25 * mm, bottomMargin=25 * mm,
                                title=text_value("title"), author=text_value("authors"))
        frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height,
                      leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        doc.addPageTemplates(PageTemplate(id="report", frames=frame, onPage=footer))
        doc.multiBuild(story)
        os.replace(temp_name, output_path)
    finally:
        Path(temp_name).unlink(missing_ok=True)
        for buf in buffers:
            buf.close()
    return output_path
