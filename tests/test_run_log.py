from pathlib import Path
from contextlib import closing
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from src.run_log import log_run, logged_run


class RunLoggingTests(unittest.TestCase):
    def test_success_failure_and_retention(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'runs.sqlite3'
            def save(run, status):
                log_run(run, status, path)
            def success(run):
                run.records_read = 12
                run.records_extracted = 12
                return 0
            def failure(run):
                run.error_message = 'missing source file'
                raise SystemExit(1)
            with patch('src.run_log.log_run', side_effect=save):
                self.assertEqual(logged_run(success), 0)
                with self.assertRaises(SystemExit):
                    logged_run(failure)
            with closing(sqlite3.connect(path)) as db:
                rows = db.execute('SELECT extraction_status, records_read, records_extracted, records_rejected, error_message FROM extraction_runs ORDER BY start_timestamp').fetchall()
            self.assertEqual(rows, [('success', 12, 12, 0, ''), ('failed', 0, 0, 0, 'missing source file')])


if __name__ == '__main__':
    unittest.main()
