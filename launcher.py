"""Desktop entry point; optional CLI for repeatable local report generation."""
import argparse
import json
import sys
from pathlib import Path


def main():
    if len(sys.argv) == 1:
        from lopi_report.app import main as desktop
        desktop()
        return
    parser = argparse.ArgumentParser(description='LOPI PQ Report Tool — lokalny generator PDF')
    parser.add_argument('--input', required=True, type=Path, help='Folder PQBox albo plik CSV')
    parser.add_argument('--output', required=True, type=Path, help='Docelowy PDF')
    parser.add_argument('--metadata', required=True, type=Path, help='JSON z metadanymi raportu')
    parser.add_argument('--time-offset', type=float, default=2, help='Jawne przesunięcie zegara PQF w godzinach')
    parser.add_argument('--status-file', type=Path, help='Opcjonalny zapis statusu do JSON')
    args = parser.parse_args()
    try:
        from lopi_report.csv_import import import_csv, default_channels
        from lopi_report.pqf import import_pqf
        from lopi_report.pdf_report import generate_report
        metadata = json.loads(args.metadata.read_text(encoding='utf-8-sig'))
        if not isinstance(metadata, dict) or not str(metadata.get('title', '')).strip():
            raise ValueError('Metadane muszą zawierać tytuł raportu.')
        if args.output.exists():
            raise ValueError('Plik wyjściowy istnieje. Wybierz inną nazwę.')
        data = import_csv(args.input) if args.input.suffix.lower() == '.csv' else import_pqf(args.input, time_offset_hours=args.time_offset)
        selected = data.subset(default_channels(data))
        generate_report(selected, metadata, args.output)
        result = {'ok': True, 'output': str(args.output.resolve()), 'samples': len(data.times),
                  'channels': len(selected.channels), 'warnings': data.warnings}
    except Exception as exc:
        result = {'ok': False, 'error': str(exc)}
    if args.status_file:
        args.status_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    if sys.stdout:
        print(json.dumps(result, ensure_ascii=False))
    if not result['ok']:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
