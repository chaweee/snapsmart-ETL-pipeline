import csv
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from validate import validate


class ValidationTests(unittest.TestCase):
    def test_duplicate_ids_and_invalid_references_are_rejected(self):
        bookings = [{'id': 'a'}, {'id': ' a '}, {'id': 'b'}, {'id': ''}]
        payments = [
            {'id': 'p', 'booking_id': 'a'}, {'id': 'q', 'booking_id': 'b'},
            {'id': 'dup', 'booking_id': 'b'}, {'id': 'dup', 'booking_id': 'b'},
            {'id': '', 'booking_id': 'missing'},
        ]
        valid_bookings, valid_payments, rejected = validate(bookings, payments)
        self.assertEqual([r['id'] for r in valid_bookings], ['b'])
        self.assertEqual([r['id'] for r in valid_payments], ['q'])
        self.assertEqual(len(rejected), 7)
        self.assertIn('booking reference', rejected[3][3])

    def test_cli_writes_valid_rows_and_report_and_fails_for_rejections(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            bookings = tmp / 'bookings.csv'
            payments = tmp / 'payments.csv'
            bookings.write_text('id,client_name,event_date,package_id,status,total_amount\nb1,A,2026-01-01,p,Pending,100\n', encoding='utf-8')
            payments.write_text('id,booking_id,amount,status,created_at\np1,missing,10,Verified,2026-01-01\n', encoding='utf-8')
            cmd = [sys.executable, str(root / 'src/validate.py'), '--bookings', str(bookings), '--payments', str(payments), '--output-dir', str(tmp / 'out')]
            result = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1, result.stderr)
            with (tmp / 'out/validation_report.csv').open(encoding='utf-8', newline='') as file:
                report = list(csv.DictReader(file))
            self.assertEqual(len(report), 1)
            self.assertIn('booking reference', report[0]['reason'])
            payments.unlink()
            self.assertEqual(subprocess.run(cmd, capture_output=True).returncode, 1)


if __name__ == '__main__':
    unittest.main()
