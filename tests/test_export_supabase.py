import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

from src.export_supabase import fetch_table


class ExportTests(unittest.TestCase):
    @patch('src.export_supabase.urlopen')
    def test_reads_short_pages_until_empty_and_requests_only_scoped_columns(self, open_url):
        open_url.side_effect = [
            io.StringIO(json.dumps([{"id": "a", "amount": 1}])),
            io.StringIO(json.dumps([{"id": "b", "amount": None}])),
            io.StringIO('[]'),
        ]
        rows = fetch_table('https://demo.supabase.co', 'sb_secret_test', 'payments', ['id', 'amount'])
        self.assertEqual(len(rows), 2)
        self.assertIsNone(rows[1]['amount'])
        requests = [call.args[0] for call in open_url.call_args_list]
        self.assertEqual([parse_qs(urlsplit(r.full_url).query)['offset'][0] for r in requests], ['0', '1', '2'])
        for request in requests:
            self.assertEqual(request.get_method(), 'GET')
            self.assertEqual(parse_qs(urlsplit(request.full_url).query)['select'], ['id,amount'])
            self.assertNotIn('Authorization', request.headers)

    @patch('src.export_supabase.urlopen')
    def test_http_failure_does_not_expose_key(self, open_url):
        open_url.side_effect = HTTPError('https://demo.supabase.co', 401, 'secret', {}, None)
        with self.assertRaises(ValueError) as error:
            fetch_table('https://demo.supabase.co', 'private-key', 'payments', ['id'])
        self.assertIn('401', str(error.exception))
        self.assertNotIn('private-key', str(error.exception))

    @patch('src.export_supabase.urlopen')
    def test_repeated_page_fails_instead_of_looping(self, open_url):
        open_url.side_effect = [io.StringIO('[{"id":"a"}]'), io.StringIO('[{"id":"a"}]')]
        with self.assertRaisesRegex(ValueError, 'duplicate ID'):
            fetch_table('https://demo.supabase.co', 'sb_secret_test', 'bookings', ['id'])


if __name__ == '__main__':
    unittest.main()
