import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from contextlib import closing

from src.transform import process, transform

BOOKING = '10000000-0000-4000-8000-000000000001'
PAYMENT = '20000000-0000-4000-8000-000000000001'
BATCH = '30000000-0000-4000-8000-000000000001'


def booking():
    return {'id': BOOKING, 'client_name': ' Ana ', 'event_date': '2026-10-10',
            'package_id': '', 'status': 'Confirmed', 'total_amount': '10000.00'}


def payment():
    return {'id': PAYMENT, 'booking_id': BOOKING, 'amount': '3000.00',
            'status': 'Verified', 'created_at': '2026-01-01T08:00:00+00:00'}


class TransformationTests(unittest.TestCase):
    def test_reconciliation_quarantine_and_deterministic_rerun(self):
        orphan = dict(payment(), id='20000000-0000-4000-8000-000000000002', booking_id='10000000-0000-4000-8000-000000000002')
        snapshot = {'run_id': BATCH, 'extraction_started_utc': '2026-01-01T00:00:00Z',
                    'extraction_mode': 'full', 'records': {'bookings': [booking()], 'payments': [payment(), orphan]}}
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            report = transform(snapshot, directory)
            self.assertEqual(report['status'], 'REVIEW')
            self.assertEqual(report['tables']['payments'], {'input': 2, 'accepted': 1, 'rejected': 1, 'reconciled': True})
            self.assertIn('7000.00', (directory / 'transformed_payments.csv').read_text())
            before = (directory / 'transformed_payments.csv').read_bytes()
            transform(snapshot, directory)
            self.assertEqual(before, (directory / 'transformed_payments.csv').read_bytes())
            with closing(sqlite3.connect(directory / 'quality.sqlite3')) as db:
                self.assertEqual(db.execute('SELECT batch_id, rule_id FROM quarantine').fetchall(), [(BATCH, 'C07')])

    def test_duplicate_and_bad_values_quarantined(self):
        bad = dict(booking(), event_date='not-a-date', total_amount='NaN')
        clean_b, clean_p, rejected = process([booking(), bad], [payment()])
        self.assertEqual((clean_b, clean_p), ([], []))
        self.assertEqual({entry['rule_id'] for entry in rejected}, {'C02', 'C04', 'C05', 'C07'})

    def test_first_verified_and_overpayment(self):
        later = dict(payment(), id='20000000-0000-4000-8000-000000000002', amount='8000', created_at='2026-02-01T00:00:00+00:00')
        pending = dict(payment(), id='20000000-0000-4000-8000-000000000003', amount='999', status='Rejected')
        snapshot = {'run_id': BATCH, 'extraction_started_utc': '2026-01-01T00:00:00Z', 'extraction_mode': 'full',
                    'records': {'bookings': [booking()], 'payments': [later, pending, payment()]}}
        with tempfile.TemporaryDirectory() as temp:
            report = transform(snapshot, Path(temp))
            self.assertEqual(report['status'], 'PASS')
            self.assertIn('3000.00,-1000.00,10000.00', (Path(temp) / 'transformed_payments.csv').read_text())


if __name__ == '__main__':
    unittest.main()
