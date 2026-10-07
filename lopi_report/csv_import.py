"""Import jawnego eksportu WinPQ mobil; pierwszy blok pomiarów interwałowych.

Nie scala różnych czasów agregacji. Nagłówki z powtarzającymi się nazwami
nie pozwalają rozróżnić wielkości, dlatego są pomijane.
"""
import csv
import hashlib
import math
import re
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from .model import Dataset


def _decode(path):
    raw = Path(path).read_bytes()
    for encoding in ('utf-8-sig', 'utf-16', 'cp1250'):
        try:
            text = raw.decode(encoding)
            if '\x00' not in text:
                return text, hashlib.sha256(raw).hexdigest()
        except UnicodeError:
            pass
    raise ValueError('Nieznane kodowanie CSV. Wykonaj ponowny eksport w WinPQ mobil.')


def import_csv(path):
    """Automatically select the Sonel or existing WinPQ text importer."""
    from .source_detection import _file_kind
    path = Path(path)
    kind = _file_kind(path)
    if kind == 'sonel_native' or re.fullmatch(r'\.pqm7\d\d', path.suffix.lower()):
        raise ValueError('To natywny plik Sonel. W Sonel Analysis wybierz Pomiary → Raporty → Raport CSV, a następnie wskaż wyeksportowany CSV.')
    if kind == 'sonel_csv':
        from .sonel_csv import import_sonel_csv
        return import_sonel_csv(path)
    # Retain support for historical WinPQ files without units or with long preambles.
    return _import_winpq_csv(path)


def _import_winpq_csv(path):
    path = Path(path)
    text, digest = _decode(path)
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        for delimiter in ('\t', ';', ','):
            fields = next(csv.reader([line], delimiter=delimiter))
            if len(fields) > 2 and fields[0].strip().lower() in ('data', 'date') and fields[1].strip().lower() in ('czas', 'time'):
                start = i
                break
        if start is not None:
            break
    if start is None:
        raise ValueError('Nie znaleziono nagłówka Data / Czas. Wyeksportuj CSV z nagłówkiem i opcją „Z interwałem”.')
    reader = csv.reader(lines[start:], delimiter=delimiter)
    header = [s.strip() for s in next(reader)]
    counts = Counter(header)
    flag_index = next((i for i, h in enumerate(header) if h.lower() in ('flagowanie', 'flagging', 'flag')), None)
    warnings = []
    if flag_index is None:
        warnings.append('CSV nie zawiera flag jakości. Nie można potwierdzić poprawności interwałów na podstawie znaczników analizatora.')
    duplicates = [h for h, n in counts.items() if n > 1]
    if duplicates:
        warnings.append(f'Pominięto {len(duplicates)} niejednoznacznych, powtarzających się nazw kolumn (m.in. energie).')
    columns = []
    for i, h in enumerate(header):
        if i < 2 or i == flag_index or not h or counts[h] > 1:
            continue
        match = re.fullmatch(r'(.*?)_?\[([^]]+)\]', h)
        name, unit = (match.group(1).rstrip('_'), match.group(2)) if match else (h, '')
        if name in [c[1] for c in columns]:
            raise ValueError(f'Niejednoznaczna nazwa kanału po odczycie jednostki: {name}.')
        columns.append((i, name, unit))
    channels = {name: [] for _, name, _ in columns}
    units = {name: unit for _, name, unit in columns}
    times = []
    flagged = 0
    invalid = Counter()
    section_ended = False
    further_rows = False
    for line_no, row in enumerate(reader, start + 2):
        if not row or not any(s.strip() for s in row):
            continue
        # A blank line is not a section boundary. WinPQ starts subsequent
        # blocks with explicit range/interval metadata or a repeated header.
        first = row[0].strip().lower()
        if times and (first in ('data', 'date') or first.startswith(('data/czas:', 'date/time:', 'interwał:', 'interval:'))):
            section_ended = True
        if section_ended:
            further_rows = True
            continue
        if len(row) != len(header):
            raise ValueError(f'CSV wiersz {line_no}: {len(row)} kolumn zamiast {len(header)}. Plik może być niekompletny.')
        stamp = f'{row[0].strip()} {row[1].strip()}'.replace(',', '.')
        moment = None
        for fmt in ('%d.%m.%Y %H:%M:%S.%f', '%d.%m.%Y %H:%M:%S', '%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S'):
            try:
                moment = datetime.strptime(stamp, fmt)
                break
            except ValueError:
                pass
        if moment is None:
            raise ValueError(f'CSV wiersz {line_no}: nieprawidłowa data/czas {stamp}.')
        times.append(moment)
        flag = row[flag_index].strip() if flag_index is not None else ''
        bad = flag not in ('', '0')
        if bad:
            flagged += 1
        for index, name, _ in columns:
            raw = row[index].strip().replace('\u00a0', '').replace(',', '.')
            value = None
            if raw and not bad:
                try:
                    candidate = float(raw)
                    if math.isfinite(candidate):
                        value = candidate
                    else:
                        invalid[name] += 1
                except ValueError:
                    invalid[name] += 1
            channels[name].append(value)
    if further_rows:
        warnings.append('Zaimportowano pierwszy blok interwałów CSV. Dalsze bloki (np. 10 s i 15 min) nie są łączone z tymi danymi.')
    if flagged:
        warnings.append(f'Wykluczono {flagged} oflagowanych interwałów z obliczeń i wykresów; zachowano przerwy w czasie.')
    if invalid:
        warnings.append(f'Pominięto {sum(invalid.values())} nieprawidłowych/nieliczbowych wartości w {len(invalid)} kanałach.')
    preamble = '\n'.join(lines[:start])
    # WinPQ declares the first and last sample in the preamble. This catches
    # interrupted exports even when the last complete row happens to parse.
    declared = re.search(r'(?:Data/Czas|Date/Time)\s*:\s*(\d{2}\.\d{2}\.\d{4})\s+(\d{2}:\d{2}:\d{2}(?:[.,]\d+)?)\s*-\s*(\d{2}\.\d{2}\.\d{4})\s+(\d{2}:\d{2}:\d{2}(?:[.,]\d+)?)', preamble, re.I)
    if declared and times:
        endpoints = []
        for date, clock in ((declared[1], declared[2]), (declared[3], declared[4])):
            value = (date + ' ' + clock).replace(',', '.')
            endpoints.append(datetime.strptime(value, '%d.%m.%Y %H:%M:%S.%f' if '.' in clock or ',' in clock else '%d.%m.%Y %H:%M:%S'))
        if times[0] != endpoints[0] or times[-1] != endpoints[1]:
            raise ValueError('Zakres wierszy CSV różni się od zakresu zadeklarowanego w nagłówku. Eksport może być ucięty lub niekompletny.')
    interval_match = re.search(r'(?:Interwał|Interval)\s*:\s*(\d+(?:[.,]\d+)?)\s*(?:sek|sec|s)', preamble, re.I)
    interval = float(interval_match.group(1).replace(',', '.')) if interval_match else None
    metadata = {'import_type': 'WinPQ mobil CSV', 'source_sha256': digest,
                'flagged_intervals': flagged, 'interval_seconds': interval,
                'source_header': preamble, 'timestamp_meaning': 'Koniec interwału eksportu WinPQ mobil; czas lokalny zapisany w pliku.'}
    if times and interval:
        metadata['measurement_start'] = (times[0] - timedelta(seconds=interval)).isoformat(' ')
    metadata['measurement_end'] = times[-1].isoformat(' ') if times else ''
    empty = [k for k, v in channels.items() if not any(x is not None for x in v)]
    for k in empty:
        del channels[k]
        del units[k]
    if empty:
        warnings.append(f'Pominięto {len(empty)} kanałów bez ważnych wartości w tym bloku interwałów.')
    return Dataset(times, channels, units, metadata, warnings, [str(path.resolve())]).validate()


def default_channels(dataset):
    """Krótki raport porównywalny zakresem do wzorca; bez 900 wykresów."""
    if dataset.metadata.get('import_type') == 'Sonel Analiza CSV':
        from .sonel_csv import default_sonel_channels
        return default_sonel_channels(dataset)
    patterns = [r'UL[123](?:_(?:min|max))?', r'IL[123](?:_(?:min|max))?',
                r'PL[123]', r'Ptotal', r'QL[123]', r'Qtotal', r'DL[123]', r'Dtotal',
                r'THDL[123]', r'THD_I[123]', r'tg_\(fi\)(?:_L[123]|_)?', r'f']
    extra = set(harmonic_report_channels(dataset))
    from .sonel_csv import default_sonel_channels
    extra.update(default_sonel_channels(dataset))
    return [k for k in dataset.channels if k in extra or any(re.fullmatch(p, k, re.I) for p in patterns)]


def harmonic_report_channels(dataset):
    """Explicit CSV channels for THD(A) and spectra; units validated by report builder."""
    return [name for name in dataset.channels if
            re.fullmatch(r'THD_\(A\)_I[123N]', name) or
            re.fullmatch(r'H(?:[2-9]|[1-4][0-9]|50)_(?:UL[123]|I[123N])', name)]


def export_csv(dataset, path):
    """Przenośny CSV UTF-8 BOM; surowe jednostki bez zaokrąglania statystyk."""
    dataset.validate()
    with Path(path).open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerow(['Data', 'Czas'] + [f'{k}_[{dataset.units[k]}]' if dataset.units.get(k) else k for k in dataset.channels])
        for i, stamp in enumerate(dataset.times):
            writer.writerow([stamp.strftime('%d.%m.%Y'), stamp.strftime('%H:%M:%S.%f')[:-3]] +
                            ['' if values[i] is None else repr(values[i]) for values in dataset.channels.values()])
