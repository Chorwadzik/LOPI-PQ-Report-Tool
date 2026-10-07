"""Exercise both frozen CSV-to-PDF pipelines with synthetic data."""
import csv
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def sonel_fixture():
    stream = io.StringIO(newline='')
    writer = csv.writer(stream, delimiter=';')
    writer.writerows([
        ['Analizator:', 'PQM-710'],
        ['Data rozpoczęcia rejestracji:', '2025-01-01 00:00:10'],
        ['Data zakończenia rejestracji:', '2025-01-01 00:00:20'],
        ['Czas:', '(UTC+1)'],
        ['', ''] + [f"'{f} / {f}f'" for f in 'EPGTA'] + ['Data', 'Czas (UTC+1)', 'U L1 śred. 10 s [V]']
            + [f'tg(φ){variant} L1 śred. 10 s [---]' for variant in ('L+', 'C-', 'L-', 'C+')],
        ['', '', '', '', "'G '", '', '', '2025-01-01', '00:00:10', '230', '0.3', '0', '0', '-0.1'],
        ['', '', '', '', "'G '", '', '', '2025-01-01', '00:00:20', '231', '0.4', '0', '0', '-0.05'],
    ])
    return stream.getvalue()


def check_exe(executable):
    fixtures = {
        'winpq': 'Interwał:60sek\nData;Czas;Flagowanie;UL1_[V]\n01.10.2026;12:01:00;;230\n01.10.2026;12:02:00;;231\n01.10.2026;12:03:00;;229\n',
        'sonel': sonel_fixture(),
    }
    with tempfile.TemporaryDirectory(prefix='lopi-pdf-test-') as folder:
        root = Path(folder)
        metadata = root / 'metadata.json'
        metadata.write_text(json.dumps({'title': 'Test PDF — Łódź', 'authors': 'Test syntetyczny'}, ensure_ascii=False), encoding='utf-8')
        for kind, content in fixtures.items():
            source = root / (kind + '.csv')
            source.write_text(content, encoding='utf-8-sig')
            output, status = root / (kind + '.pdf'), root / (kind + '.json')
            result = subprocess.run([str(Path(executable).resolve()), '--input', str(source),
                                     '--metadata', str(metadata), '--output', str(output),
                                     '--status-file', str(status)], cwd=root, timeout=120,
                                    capture_output=True)
            report = json.loads(status.read_text(encoding='utf-8')) if status.exists() else {}
            if result.returncode or report.get('ok') is not True:
                raise RuntimeError(f'EXE {kind} test failed ({result.returncode}): {report or result.stderr!r}')
            data = output.read_bytes()
            if not data.startswith(b'%PDF-') or b'%%EOF' not in data[-1024:] or len(data) < 1000:
                raise RuntimeError('EXE did not produce a complete PDF')
            expected_samples = 2 if kind == 'sonel' else 3
            expected_channels = 2 if kind == 'sonel' else 1
            if report.get('samples') != expected_samples or report.get('channels') != expected_channels:
                raise RuntimeError(f'Unexpected imported data: {report}')
            print(f'EXE {kind} PDF test passed: {len(data)} bytes, {report["samples"]} samples')


if __name__ == '__main__':
    check_exe(sys.argv[1])
