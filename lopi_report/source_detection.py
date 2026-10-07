"""Identify input containers, without interpreting or validating measurements.

Recognition is not proof that a device profile or binary payload is supported.
In particular, Sonel SNLAR20 requires a verified external export before import.
"""
import codecs
import csv
from dataclasses import dataclass
from pathlib import Path
import re

from .pqf import SIGNATURE, _folder


@dataclass(frozen=True)
class SourceInfo:
    kind: str
    path: Path


def _file_kind(path):
    with path.open('rb') as stream:
        prefix = stream.read(18)
        if prefix.startswith(b'SNLAR20\x00'):
            return 'sonel_native'
        if path.name.lower() == 'info.pqf' and prefix == SIGNATURE + b'\x00\x00':
            return 'pqbox_pqf'
        stream.seek(0)
        raw = stream.read(65536)
    encodings = ('utf-16',) if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else ('utf-8-sig', 'cp1250')
    for encoding in encodings:
        try:
            # Ignore only an incomplete final codepoint at the sniffing boundary.
            text = codecs.getincrementaldecoder(encoding)().decode(raw, final=False)
        except UnicodeError:
            continue
        if '\x00' in text:
            continue
        sonel = False
        for line in text.splitlines():
            for delimiter in ('\t', ';', ','):
                fields = next(csv.reader([line], delimiter=delimiter))
                clean = [field.strip().strip("'\"").strip() for field in fields]
                if len(clean) == 2 and clean[0].rstrip(':').strip().lower() in ('analizator', 'analyzer'):
                    sonel = True
                if (sonel and len(clean) > 9 and clean[7].lower() in ('data', 'date')
                        and re.fullmatch(r'(?:Czas|Time)\s*\(UTC(?:[+-]\d{1,2}(?::\d{2})?)?\)', clean[8], re.I)):
                    return 'sonel_csv'
                if (len(fields) > 2 and fields[0].strip().lower() in ('data', 'date')
                        and fields[1].strip().lower() in ('czas', 'time')
                        and any(re.fullmatch(r'.+\[[^\]]+\]', value.strip()) for value in fields[2:])):
                    return 'winpq_csv'
    return None


def detect_source(path):
    """Return a source kind and import path; reject unknown/ambiguous inputs.

    The CSV kind means the recognized WinPQ-compatible Date/Time + unit-header
    layout, not authenticated provenance. The importer must still validate rows.
    Directory selection never silently chooses between multiple measurements.
    """
    path = Path(path).resolve()
    if not path.exists():
        raise ValueError('Wskazany plik lub folder pomiaru nie istnieje.')
    if path.is_dir():
        candidates = []
        for child in path.rglob('*'):
            if not child.is_file():
                continue
            if not child.resolve().is_relative_to(path):
                raise ValueError('Folder zawiera dowiązanie poza wskazany katalog. Wybierz oryginalny plik pomiaru.')
            # PQBox includes large raw waveform files; only inspect input names.
            if (child.name.lower() != 'info.pqf' and child.suffix.lower() not in ('.csv', '.txt')
                    and not re.fullmatch(r'\.pqm7\d\d', child.suffix.lower())):
                continue
            kind = _file_kind(child)
            if kind:
                candidates.append(SourceInfo(kind, child.parent if kind == 'pqbox_pqf' else child))
        if len(candidates) != 1:
            raise ValueError('Wybierz jeden plik lub folder pojedynczego pomiaru; liczba rozpoznanych źródeł: ' + str(len(candidates)))
        result = candidates[0]
        if result.kind == 'pqbox_pqf':
            return SourceInfo(result.kind, _folder(path))
        return result
    if not path.is_file():
        raise ValueError('Wskaż zwykły plik lub folder pomiaru.')
    kind = _file_kind(path)
    if kind:
        return SourceInfo(kind, path.parent if kind == 'pqbox_pqf' else path)
    if re.fullmatch(r'\.pqm7\d\d', path.suffix.lower()):
        raise ValueError('Plik ma rozszerzenie Sonel, ale nie ma rozpoznanej sygnatury SNLAR20. Plik może być niekompletny lub w innej wersji formatu.')
    raise ValueError('Nie rozpoznano źródła pomiaru. Wskaż folder PQBox, natywny plik Sonel SNLAR20 lub CSV z nagłówkiem Data / Czas i jednostkami.')
