"""Restricted PQBox150 4.708 decoder verified against one complete WinPQ export.

No inferred firmware compatibility, timezone, transformer scaling or flag bits.
The caller must explicitly choose the clock offset and verify new configurations.
"""
from datetime import datetime, timedelta
import hashlib
import math
from pathlib import Path
import struct

from .model import Dataset
from .pqf_profile import CHANNELS, LAYOUT

RECORD_SIZE = 10852
SIGNATURE = b'PQBOX150 V4.708 '
EPOCH = datetime(1990, 1, 1)
# Conservative validation boundary: unknown scaling/configuration is not inferred.
# Payload may include changing fields: reject them until independently validated.
VERIFIED_INFO_PAYLOAD_SHA256 = '382af6285d974bcc1e17fb271a503c231f0130e0e008b9c6f3e9a0443e7023d8'


def _folder(folder):
    root = Path(folder)
    if not root.is_dir():
        raise ValueError('Wskaż istniejący folder pomiaru PQBox.')
    root = root.resolve()
    infos = list(root.rglob('info.pqf'))
    if any(not p.resolve().is_relative_to(root) for p in infos):
        raise ValueError('Folder zawiera dowiązanie do pomiaru poza wskazanym katalogiem. Wybierz bezpośredni folder pomiaru.')
    if len(infos) != 1:
        raise ValueError('Wybierz folder zawierający dokładnie jeden pomiar info.pqf; znaleziono: ' + str(len(infos)))
    return infos[0].parent


def _read(path, kind, measurement_id=None):
    if path.resolve().parent != path.parent.resolve():
        raise ValueError(f'Plik {path.name} jest dowiązaniem poza folder pomiaru. Wybierz oryginalny komplet danych.')
    if not path.is_file():
        raise ValueError(f'Brak wymaganego pliku {path.name}. Wykonaj kompletny odczyt pomiaru w WinPQ mobil.')
    data = path.read_bytes()
    if len(data) < 48 or data[:16] != SIGNATURE or data[16:18] != bytes((0, kind)):
        raise ValueError(f'Nieobsługiwany model, firmware lub nagłówek {path.name}. Obsługiwany profil: PQBox150 V4.708. Użyj eksportu CSV WinPQ mobil.')
    try:
        identity = data[18:32].decode('ascii')
        datetime.strptime(identity, '%Y%m%d%H%M%S')
    except (UnicodeError, ValueError) as exc:
        raise ValueError('Nieprawidłowy identyfikator pomiaru PQF.') from exc
    if data[32:48] != b'\xff' * 16:
        raise ValueError('Nieobsługiwana odmiana nagłówka PQF.')
    if measurement_id is not None and identity != measurement_id:
        raise ValueError(f'Plik {path.name} należy do innego pomiaru.')
    return data, identity


def inspect_pqf(folder):
    folder = _folder(folder)
    info, identity = _read(folder / 'info.pqf', 0)
    if hashlib.sha256(info[48:]).hexdigest() != VERIFIED_INFO_PAYLOAD_SHA256:
        raise ValueError('Konfiguracja info.pqf nie odpowiada zweryfikowanemu profilowi dostarczonej konfiguracji PQBox150 V4.708 / 60 s. Nie można potwierdzić przekładni i skalowania. Użyj eksportu CSV WinPQ mobil; nowy profil wymaga porównania z CSV.')
    cyc, _ = _read(folder / 'cyc.pqf', 1, identity)
    if len(info) != 2060 or info[48:52] != bytes.fromhex('00020064') or struct.unpack_from('<I', info, 60)[0] != 60:
        raise ValueError('Nieobsługiwana konfiguracja info.pqf lub interwał inny niż zweryfikowane 60 s. Użyj CSV.')
    if len(cyc) <= 48 or (len(cyc) - 48) % RECORD_SIZE:
        raise ValueError('Niepełny plik cyc.pqf albo nieobsługiwany układ rekordów.')
    return {'folder': str(folder.resolve()), 'measurement_id': identity,
            'firmware': '4.708', 'device': 'PQBox150',
            'record_count': (len(cyc) - 48) // RECORD_SIZE, 'interval_seconds': 60}


def _stamp(data, offset):
    seconds, quality = struct.unpack_from('<II', data, offset)
    if quality != 0x01040000:
        raise ValueError('Nieobsługiwane bity znacznika czasu PQF. Użyj CSV WinPQ mobil.')
    return seconds


def _state(data, offset):
    flag, b, c, d = struct.unpack_from('<IIII', data, offset)
    if flag not in (0, 0x8000) or b or c or d:
        raise ValueError('Nieznane flagi jakości PQF. Użyj CSV WinPQ mobil; nie można bezpiecznie pominąć tych flag.')
    return bool(flag)


def import_pqf(folder, *, time_offset_hours=None):
    if time_offset_hours is None or not isinstance(time_offset_hours, (int, float)) or not math.isfinite(time_offset_hours) or not -14 <= time_offset_hours <= 14:
        raise ValueError('Podaj jawne przesunięcie czasu PQF w godzinach (-14 do 14). Dla zweryfikowanej sesji wrzesień–październik 2026 wynosi +2 h. Porównaj czas z WinPQ mobil.')
    meta = inspect_pqf(folder)
    directory = Path(meta['folder'])
    data, _ = _read(directory / 'cyc.pqf', 1, meta['measurement_id'])
    twohour, _ = _read(directory / 'cyc2h.pqf', 0x43, meta['measurement_id'])
    if (len(twohour) - 48) % 172:
        raise ValueError('Nieobsługiwany lub niepełny plik cyc2h.pqf.')
    flags_2h = set()
    previous = None
    for start in range(48, len(twohour), 172):
        if struct.unpack_from('>HH', twohour, start) != (600, 24) or struct.unpack_from('>HH', twohour, start + 28) != (602, 140):
            raise ValueError('Nieobsługiwany układ rekordów cyc2h.pqf.')
        stamp = _stamp(twohour, start + 4)
        if _stamp(twohour, start + 32) != stamp or (previous is not None and stamp <= previous):
            raise ValueError('Niezgodne lub niemonotoniczne czasy cyc2h.pqf.')
        previous = stamp
        if _state(twohour, start + 12):
            flags_2h.add(stamp)
    channels = {name: [] for name in CHANNELS}
    times, flagged, invalid = [], 0, 0
    gaps = 0
    previous = None
    for start in range(48, len(data), RECORD_SIZE):
        stamp = _stamp(data, start + 4)
        if previous is not None:
            if stamp <= previous or (stamp - previous) % 60:
                raise ValueError('Nieprawidłowe, powtórzone lub niemonotoniczne czasy interwałów PQF.')
            if stamp - previous > 60:
                gaps += (stamp - previous) // 60 - 1
        previous = stamp
        cursor = start
        state_bad = False
        for kind, size in LAYOUT:
            if struct.unpack_from('>HH', data, cursor) != (kind, size):
                raise ValueError('Nieobsługiwany układ bloków PQF. Użyj CSV WinPQ mobil.')
            if _stamp(data, cursor + 4) != stamp:
                raise ValueError('Niezgodne znaczniki czasu wewnątrz interwału PQF.')
            if kind in (150, 152):
                state_bad = _state(data, cursor + 12) or state_bad
            cursor += 4 + size
        bad = state_bad or stamp in flags_2h
        flagged += int(bad)
        times.append(EPOCH + timedelta(seconds=stamp, hours=time_offset_hours))
        for name, (offset, _) in CHANNELS.items():
            value = struct.unpack_from('<f', data, start + offset)[0]
            if not math.isfinite(value):
                invalid += 1
                value = None
            channels[name].append(None if bad else value)
    warnings = [
        'Bezpośredni import PQF: profil dostarczonej konfiguracji PQBox150 V4.708 / 60 s; zweryfikowany względem jednej sesji WinPQ. Cały payload info.pqf musi mieć zgodny SHA256. Inne konfiguracje i przekładnie wymagają nowego porównania z CSV.',
        f'Czas PQF: założono epokę 1990-01-01 i jawne przesunięcie użytkownika {time_offset_hours:+g} h. Nie wykrywano automatycznie strefy ani zmiany czasu. Sprawdź zakres z WinPQ mobil.',
        'Wspólne flagi jakości z interwałów 60 s i 2 h konserwatywnie wykluczają wszystkie kanały w tym samym znaczniku czasu.',
        'Pominięto harmoniczne, flicker, rekordery zdarzeń i pozostałe klasy czasu; raport obejmuje wyłącznie zweryfikowane kanały profilu.',
        'Kanały min/max zachowują wartości eksportowane przez WinPQ; parser nie ustala dokładnego czasu wystąpienia ekstremum ani nie nadaje im interpretacji półokresowej.',
    ]
    if flagged:
        warnings.append(f'Wykluczono {flagged} oflagowanych interwałów z obliczeń i wykresów.')
    if invalid:
        warnings.append(f'Pominięto {invalid} niefinitywnych wartości pomiarowych.')
    if gaps:
        warnings.append(f'W danych brakuje {gaps} interwałów 60 s; nie zastępowano ich zerami.')
    files = [directory / name for name in ('info.pqf', 'cyc.pqf', 'cyc2h.pqf')]
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    meta.update(import_type='PQF / profil zweryfikowany WinPQ', source_sha256=hashes['cyc.pqf'],
                source_hashes=hashes, flagged_intervals=flagged, time_offset_hours=time_offset_hours,
                verified_config_sha256=VERIFIED_INFO_PAYLOAD_SHA256,
                timestamp_meaning='Koniec interwału; epoka 1990-01-01 z jawnym przesunięciem użytkownika. Walidacja jednej sesji WinPQ.',
                measurement_start=(times[0]-timedelta(seconds=60)).isoformat(' '),
                measurement_end=times[-1].isoformat(' '))
    return Dataset(times, channels, {name: spec[1] for name, spec in CHANNELS.items()}, meta, warnings,
                   [str(p.resolve()) for p in files]).validate()
