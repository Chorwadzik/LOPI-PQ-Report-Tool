"""Streaming import of the explicit Polish Sonel Analiza measurement table.

No binary mapping, unit conversion or timezone correction is inferred.
Only the shortest declared aggregation is retained; other periods stay separate.
"""
import codecs
import csv
from collections import Counter
from datetime import datetime, timedelta
import hashlib
import math
from pathlib import Path
import re

from .model import Dataset


_COLUMN = re.compile(r'^(?P<base>.+?)\s+(?P<stat>min\.|maks\.|śred\.|chwil\.)\s+(?P<period>\d+(?:[.,]\d+)?)\s+(?P<scale>s|min|h)\s+\[(?P<unit>[^\]]+)\]$')
_CLOCK = re.compile(r'^Czas\s+\((UTC(?:[+-]\d{1,2}(?::\d{2})?)?)\)$')
_NUMBER = re.compile(r'^[+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+)(?:[eE][+-]?\d+)?$')
_FLAG_NAMES = ('E', 'P', 'G', 'T', 'A')
_BOUNDARY_TOLERANCE = timedelta(milliseconds=2)


def _basic_channel(base, stat):
    return bool((re.fullmatch(r'[UI] \*?L[123]', base) and stat in ('min.', 'maks.', 'śred.'))
                or (stat == 'śred.' and (re.fullmatch(r'f L[123]', base)
                    or re.fullmatch(r'THD [UI] L[123]', base)
                    or re.fullmatch(r'(?:P|Q\w*|D\w*|S|Sn) (?:L[123]|Σ)', base)
                    or re.fullmatch(r'tg\([^)]*\)\S* (?:L[123]|Σ)', base))))


def _validate_timezone(value):
    match = re.fullmatch(r'UTC(?:([+-])(\d{1,2})(?::(\d{2}))?)?', value)
    if not match:
        raise ValueError('Sonel CSV: nieprawidłowy zapis strefy czasu UTC.')
    hour, minute = int(match[2] or 0), int(match[3] or 0)
    if hour > 14 or minute >= 60 or (hour == 14 and minute):
        raise ValueError('Sonel CSV: przesunięcie UTC musi należeć do zakresu ±14 h; minuty poniżej 60.')


def _encoding(path):
    with path.open('rb') as stream:
        prefix = stream.read(16384)
    if prefix.startswith((b'\xff\xfe', b'\xfe\xff')):
        return 'utf-16'
    try:
        codecs.getincrementaldecoder('utf-8-sig')().decode(prefix, final=False)
        return 'utf-8-sig'
    except UnicodeError:
        return 'cp1250'


def _stamp(value):
    value = value.strip().replace(',', '.')
    for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', '%d.%m.%Y %H:%M:%S.%f', '%d.%m.%Y %H:%M:%S'):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    raise ValueError('Sonel CSV: nieprawidłowa data lub czas: ' + value)


def _flags(row):
    """G alone qualifies clock precision; every other or unknown flag excludes."""
    found = []
    unknown = False
    for base, value in zip(_FLAG_NAMES, row[2:7]):
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] == "'":
            value = value[1:-1].strip()
        if not value:
            continue
        # Sonel can put normal and fast flags in the same cell, e.g. 'G Gf'.
        parts = value.split()
        if any(part not in (base, base + 'f') for part in parts):
            unknown = True
        found.extend(parts)
    bad = unknown or any(flag not in ('G', 'Gf') for flag in found)
    return bad, unknown, found


def add_combined_tangent(dataset):
    """Add a signed sum of four exported quadrants; never invent missing terms.

    Sonel PQM-710 manual v1.52, printed p.79: each quadrant is normalized
    by positive active-energy increment EP+; inductive signs are positive,
    capacitive signs negative. This sum is not a replacement tariff assessment.
    """
    families = {}
    for name in list(dataset.channels):
        match = re.fullmatch(r'tg\(φ\)(L\+|C-|L-|C\+) (L[123]|Σ) śred\. (\d+(?:[.,]\d+)?) (s|min|h)', name)
        if not match:
            continue
        period = float(match[3].replace(',', '.')) * {'s': 1, 'min': 60, 'h': 3600}[match[4]]
        if not math.isfinite(period) or period <= 0:
            continue
        families.setdefault((match[2], period), {}).setdefault(match[1], []).append(name)
    info = dataset.metadata.setdefault('channel_info', {})
    derived = dataset.metadata.setdefault('derived_channels', {})
    combined = dataset.metadata.setdefault('combined_tangent_channels', [])
    for (phase, period), terms in families.items():
        target = f'tg(φ) {phase} śred. {period:g} s'
        if target in dataset.channels and target not in derived:
            dataset.warnings.append(f'Nie zastąpiono istniejącego kanału {target}; dodatkowe scalenie byłoby niejednoznaczne.')
            continue
        ordered = [terms.get(q, []) for q in ('L+', 'C-', 'L-', 'C+')]
        complete = all(len(names) == 1 for names in ordered)
        sources = [names[0] for names in ordered if len(names) == 1]
        good_units = complete and all(dataset.units.get(name, '').strip() in ('', '---', '1') for name in sources)
        valid_lengths = complete and all(len(dataset.channels[name]) == len(dataset.times) for name in sources)
        values = []
        invalid_signs = missing = overflow = 0
        for index in range(len(dataset.times)):
            if not (good_units and valid_lengths):
                values.append(None)
                missing += 1
                continue
            sample = [dataset.channels[name][index] for name in sources]
            if any(value is None or not math.isfinite(value) for value in sample):
                values.append(None)
                missing += 1
                continue
            if sample[0] < 0 or sample[2] < 0 or sample[1] > 0 or sample[3] > 0:
                values.append(None)
                invalid_signs += 1
                continue
            try:
                value = math.fsum(sample)
                if not math.isfinite(value):
                    raise OverflowError
            except (ValueError, OverflowError):
                values.append(None)
                overflow += 1
            else:
                values.append(value)
        dataset.channels[target] = values
        dataset.units[target] = '---'
        if target not in combined:
            combined.append(target)
        derived[target] = {'method': 'signed_sum_four_sonel_quadrants', 'derived_sources': sources,
                           'missing_samples': missing, 'invalid_sign_samples': invalid_signs,
                           'overflow_samples': overflow, 'complete_quadrants': complete,
                           'compatible_units': good_units}
        info[target] = {'base_name': f'tg(φ) {phase}', 'statistic': 'śred.',
                        'aggregation_seconds': period, 'method': 'signed_sum_four_sonel_quadrants',
                        'derived_sources': sources}
        problem = ''
        if not complete:
            problem = ' Brak pełnego, jednoznacznego kompletu czterech wariantów; brakujący kanał nie oznacza zera.'
        elif not good_units:
            problem = ' Niezgodne jednostki wariantów.'
        elif not valid_lengths:
            problem = ' Niezgodna długość serii źródłowych.'
        dataset.warnings.append(f'{target}: suma podpisanych wariantów L+, C−, L−, C+; wspólny mianownik ΔEP+ wg instrukcji Sonel. '
                                f'Nie jest to iloraz Q/P ani ocena rozliczeniowa kwadrantów. Zachowano serie źródłowe. '
                                f'Braki: {missing}; nieprawidłowe znaki: {invalid_signs}; przepełnienia: {overflow}.{problem}')
    return dataset


def import_sonel_csv(path):
    path = Path(path)
    before = path.stat()
    encoding = _encoding(path)
    preamble = {}
    with path.open(encoding=encoding, newline='') as stream:
        # The metadata line is small even for exports with thousands of columns.
        first = stream.readline()
        delimiter = next((d for d in (';', '\t', ',') if len(next(csv.reader([first], delimiter=d))) == 2), None)
        if delimiter is None:
            raise ValueError('Sonel CSV: nierozpoznany separator lub brak nagłówka Analizator.')
        stream.seek(0)
        reader = csv.reader(stream, delimiter=delimiter, strict=True)
        header = None
        try:
            for row in reader:
                cells = [x.strip() for x in row]
                if len(cells) > 9 and cells[7] == 'Data' and _CLOCK.fullmatch(cells[8]):
                    header = cells
                    break
                if len(cells) == 2 and cells[0].endswith(':'):
                    preamble[cells[0].rstrip(':').strip()] = cells[1]
                if reader.line_num > 100:
                    break
            if header is None or not preamble.get('Analizator'):
                raise ValueError('Sonel CSV: brak tabeli pomiarów z nagłówkiem Analizator, Data i Czas (UTC).')
            if header[:2] != ['', ''] or [x.strip("'").strip() for x in header[2:7]] != [f'{f} / {f}f' for f in _FLAG_NAMES]:
                raise ValueError('Sonel CSV: nierozpoznany układ kolumn flag E/P/G/T/A. Wykonaj pełny eksport tabeli.')
            timezone = _CLOCK.fullmatch(header[8])[1]
            _validate_timezone(timezone)
            if preamble.get('Czas', '').strip('() ') != timezone:
                raise ValueError('Sonel CSV: niezgodna lub brakująca deklaracja strefy czasu.')
            if len(set(header[9:])) != len(header[9:]):
                raise ValueError('Sonel CSV: powtarzające się nagłówki kanałów; nie można jednoznacznie przypisać danych.')
            columns = []
            unrecognized = 0
            for index, label in enumerate(header[9:], 9):
                match = _COLUMN.fullmatch(label)
                if not match:
                    unrecognized += 1
                    continue
                period = float(match['period'].replace(',', '.')) * {'s': 1, 'min': 60, 'h': 3600}[match['scale']]
                if not math.isfinite(period) or period <= 0:
                    raise ValueError('Sonel CSV: nieprawidłowy czas agregacji w nagłówku.')
                name = label[:label.rfind('[')].rstrip()
                columns.append((index, name, match['unit'], period, match['stat'], match['base'], label))
            if not columns:
                raise ValueError('Sonel CSV: brak rozpoznanych kanałów z jawną agregacją i jednostką.')
            period = min(c[3] for c in columns)
            skipped = sum(c[3] != period for c in columns)
            columns = [c for c in columns if c[3] == period]
            skipped_report = sum(not _basic_channel(c[5], c[4]) for c in columns)
            columns = [c for c in columns if _basic_channel(c[5], c[4])]
            if not columns:
                raise ValueError('Sonel CSV: brak kanałów podstawowego raportu w najkrótszej agregacji. Wyeksportuj napięcia, prądy, moce, tg(φ), THD lub częstotliwość.')
            names = [c[1] for c in columns]
            if len(set(names)) != len(names):
                raise ValueError('Sonel CSV: ta sama nazwa kanału ma więcej niż jedną jednostkę.')
            channels = {name: [] for name in names}
            units = {c[1]: c[2] for c in columns}
            channel_info = {c[1]: {'statistic': c[4], 'aggregation_seconds': c[3], 'base_name': c[5], 'source_header': c[6]} for c in columns}
            times = []
            flag_counts = Counter()
            invalid = Counter()
            excluded = unknown_flags = gps = missing = 0
            for row in reader:
                if not row or not any(cell.strip() for cell in row):
                    continue
                if len(row) != len(header):
                    raise ValueError(f'Sonel CSV wiersz {reader.line_num}: niezgodna liczba kolumn ({len(row)} zamiast {len(header)}). Eksport może być ucięty.')
                if any(value.strip() for value in row[:2]):
                    raise ValueError(f'Sonel CSV wiersz {reader.line_num}: nieznana zawartość dwóch kolumn poprzedzających flagi.')
                moment = _stamp(row[7].strip() + ' ' + row[8].strip())
                if times and moment <= times[-1]:
                    raise ValueError('Sonel CSV: znaczniki czasu muszą być rosnące i unikalne.')
                times.append(moment)
                bad, unknown, flags = _flags(row)
                flag_counts.update(flags)
                excluded += int(bad)
                unknown_flags += int(unknown)
                gps += int(any(flag in ('G', 'Gf') for flag in flags))
                for index, name, *_ in columns:
                    value = None
                    if not bad:
                        raw = row[index].strip()
                        if raw in ('', '---'):
                            missing += 1
                        elif _NUMBER.fullmatch(raw):
                            number = float(raw.replace(',', '.'))
                            if math.isfinite(number):
                                value = number
                            else:
                                invalid[name] += 1
                        else:
                            invalid[name] += 1
                    channels[name].append(value)
        except (csv.Error, UnicodeError) as exc:
            raise ValueError('Sonel CSV: uszkodzony format lub nieobsługiwane kodowanie. Wykonaj ponowny pełny eksport CSV.') from exc
    if not times:
        raise ValueError('Sonel CSV: brak wierszy pomiarowych.')
    for label, endpoint in (('Data rozpoczęcia rejestracji', times[0]), ('Data zakończenia rejestracji', times[-1])):
        if label not in preamble:
            raise ValueError('Sonel CSV: brak deklarowanego zakresu. Wykonaj pełny eksport z nagłówkiem, bez dzielenia pliku.')
        if abs(_stamp(preamble[label]) - endpoint) > _BOUNDARY_TOLERANCE:
            raise ValueError('Sonel CSV: zakres wierszy różni się od deklarowanego zakresu (tolerancja 2 ms). Eksport może być ucięty lub podzielony; wyeksportuj pełną tabelę bez dzielenia.')
    warnings = [f'Sonel: import jednej agregacji {period:g} s; zachowano nazwy, statystyki i jednostki eksportu. Nie wyznaczono zgodności z normą.',
                f'Czas Sonel: zachowano znaczniki {timezone} zapisane w CSV bez przesunięcia. Znacznik opisuje koniec przedziału uśredniania; tolerancja porównania granic eksportu wynosi 2 ms.',
                'Min./maks. zachowano zgodnie z etykietami Sonel; nie przypisano im automatycznie interpretacji półokresowej.']
    if skipped or unrecognized:
        warnings.append(f'Pominięto {skipped} kanałów o innej agregacji i {unrecognized} kanałów bez rozpoznanej jawnej agregacji. Nie scalono różnych czasów uśredniania.')
    if skipped_report:
        warnings.append(f'Import obejmuje podstawowy raport (U/I min., maks. i śred.; średnie moce, tg(φ), THD i f). Pominięto {skipped_report} pozostałych kanałów, w tym widma i energie; nie jest to pełne archiwum CSV.')
    if excluded:
        warnings.append(f'Konserwatywnie wykluczono {excluded} wierszy ze wszystkich kanałów: E/Ef (zdarzenie), P/Pf (PLL), T/Tf (resynchronizacja), A/Af (zakres A/D) lub nieznana flaga ({unknown_flags} wierszy). Zachowano przerwy.')
    if gps:
        warnings.append(f'G/Gf: {gps} wierszy bez synchronizacji GPS/UTC. Zachowano amplitudy, lecz precyzja czasu nie jest potwierdzona; nie stwierdzono spełnienia wymagań czasu klasy A.')
    if any('*' in name for name in channels):
        warnings.append('Gwiazdka w nagłówku Sonel (np. I *L1) oznacza włączone ograniczenie prądu: małe wartości mogły zostać wyzerowane przez urządzenie. Zachowano gwiazdki i wyeksportowane zera; progu nie odtworzono.')
    if invalid:
        warnings.append(f'Pominięto {sum(invalid.values())} nieprawidłowych lub niefinitywnych wartości; brak danych nie oznacza zera.')
    # Combine before removing empty source columns: a missing quadrant is not zero.
    tangent_data = add_combined_tangent(Dataset(times, channels, units, {'channel_info': channel_info}, warnings))
    derived_channels = tangent_data.metadata['derived_channels']
    tangent_sources = {name for item in derived_channels.values() for name in item['derived_sources']}
    empty = [name for name, values in channels.items() if name not in derived_channels and name not in tangent_sources and not any(v is not None for v in values)]
    for name in empty:
        del channels[name]
        del units[name]
        del channel_info[name]
    if empty:
        warnings.append(f'Pominięto {len(empty)} kanałów bez ważnych wartości.')
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('Sonel CSV zmienił się w czasie importu. Spróbuj ponownie po zakończeniu zapisu.')
    metadata = {'import_type': 'Sonel Analiza CSV', 'source_sha256': digest.hexdigest(),
                'instrument': preamble['Analizator'],
                'interval_seconds': period, 'source_timezone': timezone, 'channel_info': channel_info,
                'derived_channels': derived_channels,
                'combined_tangent_channels': tangent_data.metadata['combined_tangent_channels'],
                'source_header': '\n'.join(f'{k}: {v}' for k, v in preamble.items()),
                'flagged_intervals': excluded, 'gps_unsynchronized_intervals': gps,
                'quality_flag_counts': dict(flag_counts), 'unknown_flag_intervals': unknown_flags,
                'missing_values': missing, 'invalid_values': sum(invalid.values()),
                'measurement_start': times[0].isoformat(' '),
                'measurement_end': times[-1].isoformat(' '),
                'timestamp_meaning': f'Koniec interwału Sonel; czas {timezone} z CSV, bez przeliczenia.',
                'omitted_other_aggregation_channels': skipped, 'omitted_unrecognized_channels': unrecognized,
                'omitted_outside_report_channels': skipped_report}
    return Dataset(times, channels, units, metadata, warnings, [str(path.resolve())]).validate()


def default_sonel_channels(dataset):
    """Select explicit basic quantities, retaining every distinct power definition."""
    result = []
    combined_present = any(re.fullmatch(r'tg\(φ\) (?:L[123]|Σ) śred\. \d+(?:[.,]\d+)? (?:s|min|h)', name) for name in dataset.channels)
    for name in dataset.channels:
        info = dataset.metadata.get('channel_info', {}).get(name, {})
        base, stat = info.get('base_name', ''), info.get('statistic')
        if not info:
            match = _COLUMN.fullmatch(name + ' [' + dataset.units.get(name, '---') + ']')
            if match:
                base, stat = match['base'], match['stat']
        if combined_present and re.fullmatch(r'tg\(φ\)(?:L\+|C-|L-|C\+) (?:L[123]|Σ)', base):
            continue
        if _basic_channel(base, stat):
            result.append(name)
    return result
