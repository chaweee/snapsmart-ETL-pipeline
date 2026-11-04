import json
from pathlib import Path
import tempfile
import unittest

from src.extract import extract_csv, main


class ExtractionTests(unittest.TestCase):
    def test_only_scoped_columns_are_returned(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.csv"
            path.write_text('id,extra\n1,ignored\n2,ignored\n', encoding="utf-8")
            self.assertEqual(extract_csv(path, {"id"}), [{"id": "1"}, {"id": "2"}])

    def test_preserves_bom_unicode_quotes_empty_values_and_duplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.csv"
            path.write_text('id,name,amount\n001,"Peña, Ana",001.20\n001,"Peña, Ana",\n', encoding="utf-8-sig")
            rows = extract_csv(path, {"id", "name", "amount"})
            self.assertEqual(rows, [
                {"id": "001", "name": "Peña, Ana", "amount": "001.20"},
                {"id": "001", "name": "Peña, Ana", "amount": ""},
            ])

    def test_rejects_ambiguous_structure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.csv"
            for content in ('', 'id,id\n1,2\n', 'name\nAna\n', 'id,name\n1\n', 'id\n1,2\n'):
                with self.subTest(content=content):
                    path.write_text(content, encoding="utf-8")
                    with self.assertRaises(ValueError):
                        extract_csv(path, {"id"})

    def test_end_to_end_and_failed_input_preserves_previous_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bookings = root / "bookings.csv"
            payments = root / "payments.csv"
            output = root / "output.json"
            bookings.write_text('id,client_name,event_date,package_id,status,total_amount\nb1,Ana,2026-01-01,,Pending,100.00\n', encoding="utf-8")
            payments.write_text('id,booking_id,amount,status,created_at\n', encoding="utf-8")
            args = ['--bookings', str(bookings), '--payments', str(payments), '--output', str(output)]
            self.assertEqual(main(args), 0)
            result = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(len(result['bookings']), 1)
            self.assertEqual(result['payments'], [])
            previous = output.read_bytes()
            payments.write_text('wrong_header\n', encoding="utf-8")
            with self.assertRaises(SystemExit) as error:
                main(args)
            self.assertEqual(error.exception.code, 1)
            self.assertEqual(output.read_bytes(), previous)


if __name__ == '__main__':
    unittest.main()
