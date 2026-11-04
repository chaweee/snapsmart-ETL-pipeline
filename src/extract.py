"""Extract source CSVs without cleaning or converting source values."""

import csv
import json
from pathlib import Path

if __package__:
    from .run_log import LoggingParser, logged_run
else:
    from run_log import LoggingParser, logged_run


REQUIRED_COLUMNS = {
    "bookings": {"id", "client_name", "event_date", "package_id", "status", "total_amount"},
    "payments": {"id", "booking_id", "amount", "status", "created_at"},
}


def extract_csv(path, required_columns):
    """Return raw string records; reject ambiguous CSV structure."""
    path = Path(path)
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.reader(source, strict=True)
        header = next(reader, None)
        if not header:
            raise ValueError(f"{path}: missing CSV header")
        if any(not column.strip() for column in header) or len(set(header)) != len(header):
            raise ValueError(f"{path}: empty or duplicate column names")
        missing = set(required_columns) - set(header)
        if missing:
            raise ValueError(f"{path}: missing columns: {', '.join(sorted(missing))}")
        selected_columns = [column for column in header if column in required_columns]
        records = []
        for row in reader:
            if not row:  # Ignore physically blank lines, not rows with empty fields.
                continue
            if len(row) != len(header):
                raise ValueError(f"{path}: line {reader.line_num}: expected {len(header)} fields, got {len(row)}")
            record = dict(zip(header, row))
            records.append({column: record[column] for column in selected_columns})
        return records


def extract(argv, run):
    parser = LoggingParser(description=__doc__, run=run)
    parser.add_argument("--bookings", type=Path, required=True)
    parser.add_argument("--payments", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("output/extracted.json"))
    args = parser.parse_args(argv)
    try:
        if args.output.resolve() in {args.bookings.resolve(), args.payments.resolve()}:
            raise ValueError("Output must not overwrite an input CSV")
        # Read both inputs successfully before creating an output artifact.
        extracted = {
            "bookings": extract_csv(args.bookings, REQUIRED_COLUMNS["bookings"]),
            "payments": extract_csv(args.payments, REQUIRED_COLUMNS["payments"]),
        }
        run.records_read = sum(len(rows) for rows in extracted.values())
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", encoding="utf-8") as destination:
            json.dump(extracted, destination, ensure_ascii=False, indent=2)
            destination.write("\n")
        run.records_extracted = run.records_read
    except (OSError, UnicodeError, csv.Error, ValueError) as error:
        parser.exit(1, f"Extraction failed: {error}\n")
    print(f"Extracted {len(extracted['bookings'])} bookings and {len(extracted['payments'])} payments -> {args.output}")
    return 0


def main(argv=None):
    return logged_run(lambda run: extract(argv, run))


if __name__ == "__main__":
    raise SystemExit(main())
