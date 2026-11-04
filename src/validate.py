"""Validate extracted CSV source rows and produce clean CSVs and a report."""

import argparse
from collections import Counter
import csv
from pathlib import Path

from extract import REQUIRED_COLUMNS, extract_csv


def validate(bookings, payments):
    """Reject all copies of duplicate IDs and payments without a valid booking."""
    booking_counts = Counter(row['id'].strip() for row in bookings)
    payment_counts = Counter(row['id'].strip() for row in payments)
    valid_bookings, valid_payments, rejected = [], [], []

    for index, row in enumerate(bookings, 1):
        key = row['id'].strip()
        reason = 'missing booking id' if not key else ('duplicate booking id' if booking_counts[key] > 1 else '')
        if reason:
            rejected.append(('bookings', index, row['id'], reason))
        else:
            valid_bookings.append(row)

    booking_ids = {row['id'].strip() for row in valid_bookings}
    for index, row in enumerate(payments, 1):
        key = row['id'].strip()
        booking_id = row['booking_id'].strip()
        reasons = []
        if not key:
            reasons.append('missing payment id')
        elif payment_counts[key] > 1:
            reasons.append('duplicate payment id')
        if not booking_id or booking_id not in booking_ids:
            reasons.append('booking reference missing or invalid')
        if reasons:
            rejected.append(('payments', index, row['id'], '; '.join(reasons)))
        else:
            valid_payments.append(row)
    return valid_bookings, valid_payments, rejected


def write_csv(path, columns, rows):
    with path.open('w', encoding='utf-8', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(columns)
        writer.writerows(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bookings', type=Path, default=Path('data/raw/bookings.csv'))
    parser.add_argument('--payments', type=Path, default=Path('data/raw/payments.csv'))
    parser.add_argument('--output-dir', type=Path, default=Path('output'))
    args = parser.parse_args(argv)
    try:
        outputs = [args.output_dir / name for name in ('cleaned_bookings.csv', 'cleaned_payments.csv', 'validation_report.csv')]
        inputs = {args.bookings.resolve(), args.payments.resolve()}
        if any(path.resolve() in inputs for path in outputs):
            raise ValueError('Output files must not overwrite input CSVs')
        bookings = extract_csv(args.bookings, REQUIRED_COLUMNS['bookings'])
        payments = extract_csv(args.payments, REQUIRED_COLUMNS['payments'])
        clean_bookings, clean_payments, rejected = validate(bookings, payments)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        for path, table, records in ((outputs[0], 'bookings', clean_bookings), (outputs[1], 'payments', clean_payments)):
            columns = sorted(REQUIRED_COLUMNS[table])
            write_csv(path, columns, ([record[column] for column in columns] for record in records))
        write_csv(outputs[2], ['source', 'record_number', 'id', 'reason'], rejected)
    except (OSError, UnicodeError, csv.Error, ValueError) as error:
        parser.exit(1, f'Validation failed: {error}\n')
    print(f'Valid bookings: {len(clean_bookings)}/{len(bookings)}; valid payments: {len(clean_payments)}/{len(payments)}; rejected: {len(rejected)}')
    if rejected:
        print(f'See {outputs[2]}; resolve rejected records before downstream processing.')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
