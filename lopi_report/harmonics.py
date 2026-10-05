"""Explicit WinPQ harmonic channels; no normative limits or unit conversion."""
import math
import re
from statistics import fmean


def harmonic_channel(name, unit):
    """Recognise only phase voltage (%) and phase/neutral current (A), H2–H50."""
    match = re.fullmatch(r'H([2-9]|[1-4][0-9]|50)_(UL[123]|I[123]|IN)', name)
    if not match:
        return None
    order, conductor = match.groups()
    kind = 'U' if conductor.startswith('U') else 'I'
    expected = '%' if kind == 'U' else 'A'
    if unit != expected:
        raise ValueError(f'Kanał {name}: oczekiwano jednostki {expected}, otrzymano {unit!r}.')
    phase = 'N' if conductor == 'IN' else 'L' + conductor[-1]
    return kind, phase, int(order)


def validate_thda(name, unit):
    """THD(A) is a separate source channel, never an alias for percentage THDI."""
    if not re.fullmatch(r'THD_\(A\)_I[123N]', name):
        return False
    if unit != 'A':
        raise ValueError(f'Kanał {name}: oczekiwano jednostki A, otrzymano {unit!r}.')
    return True


def spectrum_groups(dataset, statistic='mean'):
    """Summarise full valid series by order; missing samples never become zero.

    p95 uses linear interpolation at position (n-1)*0.95. Negative or nonfinite
    measured amplitudes are rejected, not silently excluded. Input is unchanged.
    """
    if statistic not in ('mean', 'max', 'p95'):
        raise ValueError('Statystyka widma musi być mean, max albo p95.')
    collected = {}
    for name, samples in dataset.channels.items():
        channel = harmonic_channel(name, dataset.units.get(name, ''))
        if channel is None:
            continue
        kind, phase, order = channel
        if len(samples) != len(dataset.times):
            raise ValueError(f'Niezgodna liczba próbek kanału {name}.')
        valid = []
        for sample in samples:
            if sample is None:
                continue
            try:
                value = float(sample)
            except (TypeError, ValueError, OverflowError) as error:
                raise ValueError(f'Nieprawidłowa amplituda harmonicznej w kanale {name}.') from error
            if not math.isfinite(value) or value < 0:
                raise ValueError(f'Ujemna lub niefinitywna amplituda harmonicznej w kanale {name}.')
            valid.append(value)
        result = None
        if valid:
            if statistic == 'mean':
                result = fmean(valid)
            elif statistic == 'max':
                result = max(valid)
            else:
                ordered = sorted(valid)
                position = (len(ordered) - 1) * 0.95
                lower = math.floor(position)
                upper = math.ceil(position)
                result = ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)
        collected.setdefault(kind, {})[(phase, order)] = (name, result, len(valid))
    groups = []
    for kind in ('U', 'I'):
        if kind not in collected:
            continue
        phases = ['L1', 'L2', 'L3'] + (['N'] if kind == 'I' else [])
        rows = []
        absent = empty = partial = 0
        for order in range(2, 51):
            row = {'order': order, 'values': {}, 'counts': {}, 'names': {}}
            for phase in phases:
                name, value, count = collected[kind].get((phase, order), (None, None, 0))
                row['values'][phase] = value
                row['counts'][phase] = count
                row['names'][phase] = name
                absent += name is None
                empty += name is not None and count == 0
                partial += name is not None and 0 < count < len(dataset.times)
            rows.append(row)
        warnings = []
        if absent:
            warnings.append(f'Brak kanałów harmonicznych: {absent}. Brak nie oznacza zera.')
        if empty:
            warnings.append(f'Kanały harmoniczne bez ważnych próbek: {empty}.')
        if partial:
            warnings.append(f'Kanały z niepełną liczbą ważnych próbek: {partial}; statystyki pomijają braki.')
        groups.append({'kind': kind, 'unit': '%' if kind == 'U' else 'A',
                       'statistic': statistic, 'phases': phases, 'rows': rows,
                       'warnings': warnings})
    return groups
