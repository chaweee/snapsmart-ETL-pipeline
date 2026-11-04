"""Validate and transform a specific immutable extraction snapshot."""

import argparse
from collections import Counter, defaultdict
from contextlib import closing
import csv
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import sqlite3
from uuid import UUID

BOOKING_STATUSES = {'Pending', 'Awaiting Payment Verification', 'Confirmed',
                    'Payment Insufficient', 'Completed', 'Cancelled'}
PAYMENT_STATUSES = {'For Verification', 'Verified', 'Insufficient', 'Rejected'}
RULES = {
    'C01': ('id', 'Missing or invalid UUID'),
    'C02': ('id', 'Duplicate primary key; all copies quarantined'),
    'C03': ('client_name', 'Missing client name'),
    'C04': ('event_date', 'Invalid event date'),
    'C05': ('total_amount', 'Invalid booking amount'),
    'C06': ('status', 'Invalid booking status'),
    'C07': ('booking_id', 'Invalid or orphan booking reference'),
    'C08': ('amount', 'Invalid payment amount'),
    'C09': ('status', 'Invalid payment status'),
    'C10': ('created_at', 'Invalid or timezone-free timestamp'),
}


def uuid_value(value):
    try:
        return str(UUID(value.strip()))
    except (ValueError, AttributeError):
        return None


def money(value, positive=False):
    try:
        amount = Decimal(value.strip())
        if not amount.is_finite() or amount < 0 or (positive and amount == 0):
            return None
        if amount.as_tuple().exponent < -2 or amount > Decimal('9999999999.99'):
            return None
        return amount.quantize(Decimal('0.01'))
    except (InvalidOperation, ValueError, AttributeError):
        return None


def timestamp(value):
    try:
        result = datetime.fromisoformat(value.strip().replace('Z', '+00:00'))
        return result.astimezone(timezone.utc) if result.utcoffset() is not None else None
    except (ValueError, AttributeError, OverflowError):
        return None


def process(bookings, payments):
    """Return normalized rows and quarantine entries with stable rule IDs."""
    counts = {name: Counter(uuid_value(r['id']) for r in rows if uuid_value(r['id']))
              for name, rows in [('bookings', bookings), ('payments', payments)]}
    quarantine = []
    cleaned_bookings, cleaned_payments = [], []

    def reject(table, number, row, reasons):
        for rule in sorted(set(reasons)):
            quarantine.append({'table_name': table, 'record_number': number,
                               'rule_id': rule, 'reason': RULES[rule][1], 'row': row})

    for number, original in enumerate(bookings, 1):
        row = {key: value.strip() for key, value in original.items()}
        reasons = []
        key = uuid_value(row['id'])
        if not key: reasons.append('C01')
        elif counts['bookings'][key] > 1: reasons.append('C02')
        if not row['client_name']: reasons.append('C03')
        try:
            day = date.fromisoformat(row['event_date'])
        except ValueError:
            day = None
            reasons.append('C04')
        amount = money(row['total_amount'])
        if amount is None: reasons.append('C05')
        if row['status'] not in BOOKING_STATUSES: reasons.append('C06')
        if reasons:
            reject('bookings', number, original, reasons)
        else:
            row.update(id=key, event_date=day.isoformat(), total_amount=str(amount))
            cleaned_bookings.append(row)

    booking_ids = {row['id'] for row in cleaned_bookings}
    for number, original in enumerate(payments, 1):
        row = {key: value.strip() for key, value in original.items()}
        reasons = []
        key, booking_id = uuid_value(row['id']), uuid_value(row['booking_id'])
        if not key: reasons.append('C01')
        elif counts['payments'][key] > 1: reasons.append('C02')
        if not booking_id or booking_id not in booking_ids: reasons.append('C07')
        amount = money(row['amount'], positive=True)
        if amount is None: reasons.append('C08')
        if row['status'] not in PAYMENT_STATUSES: reasons.append('C09')
        created = timestamp(row['created_at'])
        if created is None: reasons.append('C10')
        if reasons:
            reject('payments', number, original, reasons)
        else:
            row.update(id=key, booking_id=booking_id, amount=str(amount), created_at=created.isoformat())
            cleaned_payments.append(row)
    return cleaned_bookings, cleaned_payments, quarantine


def write_csv(path, columns, rows):
    with path.open('w', encoding='utf-8', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def transform(snapshot, directory):
    run_id = str(UUID(snapshot['run_id']))
    if snapshot.get('extraction_mode') != 'full':
        raise ValueError('Expected a full extraction snapshot')
    raw = snapshot['records']
    bookings, payments, rejected = process(raw['bookings'], raw['payments'])
    directory.mkdir(parents=True, exist_ok=True)
    write_csv(directory / 'cleaned_bookings.csv', ['id', 'client_name', 'event_date', 'package_id', 'status', 'total_amount'], bookings)
    write_csv(directory / 'cleaned_payments.csv', ['id', 'booking_id', 'amount', 'status', 'created_at'], payments)
    grouped = defaultdict(list)
    for row in payments:
        if row['status'] == 'Verified':
            grouped[row['booking_id']].append(row)
    summaries = []
    for booking in bookings:
        verified = sorted(grouped[booking['id']], key=lambda row: (timestamp(row['created_at']), row['id']))
        total = Decimal(booking['total_amount'])
        paid = sum((Decimal(row['amount']) for row in verified), Decimal('0.00'))
        summaries.append({'payment_id': booking['id'], 'booking_id': booking['id'],
                          'down_payment': verified[0]['amount'] if verified else '0.00',
                          'remaining_balance': str(total - paid), 'total_amount': str(total)})
    write_csv(directory / 'transformed_bookings.csv', ['booking_id', 'client_name', 'event_date', 'package_id', 'booking_status'],
              [{'booking_id': b['id'], 'client_name': b['client_name'], 'event_date': b['event_date'],
                'package_id': b['package_id'], 'booking_status': b['status']} for b in bookings])
    write_csv(directory / 'transformed_payments.csv', ['payment_id', 'booking_id', 'down_payment', 'remaining_balance', 'total_amount'], summaries)
    # One row per rule failure; reconciliation counts distinct rejected records.
    counts = Counter((r['table_name'], r['rule_id']) for r in rejected)
    profile = []
    for (table, rule), count in sorted(counts.items()):
        total = len(raw[table])
        profile.append({'table_name': table, 'column': RULES[rule][0], 'rule_id': rule,
                        'issue': RULES[rule][1], 'affected': count,
                        'percentage': f'{count * 100 / total:.2f}' if total else '0.00',
                        'sample_value': str(next(r['row'].get(RULES[rule][0], '') for r in rejected if r['table_name'] == table and r['rule_id'] == rule)),
                        'treatment': 'quarantine record; review source'})
    write_csv(directory / 'profiling.csv', ['table_name', 'column', 'rule_id', 'issue', 'affected', 'percentage', 'sample_value', 'treatment'], profile)
    with closing(sqlite3.connect(directory / 'quality.sqlite3')) as db, db:
        db.execute('''CREATE TABLE IF NOT EXISTS quarantine (
            batch_id TEXT NOT NULL, table_name TEXT NOT NULL, record_number INTEGER NOT NULL,
            rule_id TEXT NOT NULL, reason TEXT NOT NULL, row_json TEXT NOT NULL,
            PRIMARY KEY (batch_id, table_name, record_number, rule_id))''')
        db.execute('DELETE FROM quarantine WHERE batch_id = ?', (run_id,))
        db.executemany('INSERT INTO quarantine VALUES (?, ?, ?, ?, ?, ?)', [
            (run_id, r['table_name'], r['record_number'], r['rule_id'], r['reason'], json.dumps(r['row'], ensure_ascii=False)) for r in rejected])
    reject_counts = Counter(table for table, _ in {(r['table_name'], r['record_number']) for r in rejected})
    results = {}
    for table, clean in [('bookings', bookings), ('payments', payments)]:
        total, bad = len(raw[table]), reject_counts[table]
        results[table] = {'input': total, 'accepted': len(clean), 'rejected': bad,
                          'reconciled': total == len(clean) + bad}
    rejected_total = sum(reject_counts.values())
    checks = {
        'record_reconciliation': all(result['reconciled'] for result in results.values()),
        'booking_key_uniqueness': len(booking_ids := {b['id'] for b in bookings}) == len(bookings),
        'payment_key_uniqueness': len({p['id'] for p in payments}) == len(payments),
        'referential_integrity': all(p['booking_id'] in booking_ids for p in payments),
        'business_rule_summary_per_booking': len(summaries) == len(bookings),
    }
    report = {'batch_id': run_id, 'extraction_started_utc': snapshot['extraction_started_utc'],
              'batch_window': 'full snapshot', 'status': 'PASS' if not rejected_total and all(checks.values()) else 'REVIEW',
              'rejection_threshold_percent': 0, 'tables': results,
              'checks': {name: {'passed': passed, 'severity': 'critical'} for name, passed in checks.items()},
              'rejection_rate_percent': round(100 * rejected_total / sum(len(raw[t]) for t in results), 2) if any(raw[t] for t in results) else 0}
    (directory / 'quality_report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot', type=Path, help='output/batches/<run_id>/extracted.json')
    args = parser.parse_args()
    try:
        with args.snapshot.open(encoding='utf-8') as file:
            snapshot = json.load(file)
        if args.snapshot.name != 'extracted.json' or args.snapshot.parent.name != str(UUID(snapshot['run_id'])):
            raise ValueError('Snapshot must be inside the matching batch ID directory')
        report = transform(snapshot, args.snapshot.parent / 'transformed')
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as error:
        parser.exit(1, f'Transformation failed: {error}\n')
    print(f"Batch {report['batch_id']}: {report['status']}; results: {args.snapshot.parent / 'transformed'}")
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
