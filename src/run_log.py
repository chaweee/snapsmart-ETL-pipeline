"""Persistent local audit records for extraction runs."""

import argparse
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import uuid


LOG_PATH = Path(__file__).resolve().parents[1] / 'logs' / 'pipeline_runs.sqlite3'


class Run:
    def __init__(self):
        self.pipeline_run_id = str(uuid.uuid4())
        self.start_timestamp = datetime.now(timezone.utc).isoformat()
        self.records_read = 0
        self.records_extracted = 0
        self.records_rejected = 0
        self.error_message = ''
        self.table_counts = {}


class LoggingParser(argparse.ArgumentParser):
    def __init__(self, *args, run, **kwargs):
        self.run = run
        super().__init__(*args, **kwargs)

    def exit(self, status=0, message=None):
        if status:
            self.run.error_message = (message or 'Invalid command arguments').strip()
        super().exit(status, message)


def log_run(run, status, path=LOG_PATH):
    """Append one final record; retain indefinitely (at least 90 days)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as db, db:
        db.execute('''CREATE TABLE IF NOT EXISTS extraction_runs (
            pipeline_run_id TEXT PRIMARY KEY, start_timestamp TEXT NOT NULL,
            end_timestamp TEXT NOT NULL, extraction_status TEXT NOT NULL,
            records_read INTEGER NOT NULL, records_extracted INTEGER NOT NULL,
            records_rejected INTEGER NOT NULL, error_message TEXT NOT NULL
        )''')
        db.execute('INSERT INTO extraction_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?)', (
            run.pipeline_run_id, run.start_timestamp, datetime.now(timezone.utc).isoformat(),
            status, run.records_read, run.records_extracted, run.records_rejected,
            run.error_message,
        ))
        db.execute('''CREATE TABLE IF NOT EXISTS extraction_table_counts (
            pipeline_run_id TEXT NOT NULL, table_name TEXT NOT NULL,
            records_read INTEGER NOT NULL, records_extracted INTEGER NOT NULL,
            PRIMARY KEY (pipeline_run_id, table_name)
        )''')
        db.executemany('INSERT INTO extraction_table_counts VALUES (?, ?, ?, ?)', [
            (run.pipeline_run_id, name, count, count if status == 'success' else 0)
            for name, count in run.table_counts.items()
        ])


def logged_run(operation):
    run = Run()
    status = 'failed'
    try:
        result = operation(run)
        status = 'success' if result == 0 else 'failed'
        if status == 'failed' and not run.error_message:
            run.error_message = f'Extraction exited with status {result}'
        return result
    except SystemExit as error:
        if error.code in (None, 0):
            status = 'success'
        elif not run.error_message:
            run.error_message = f'Extraction exited with status {error.code}'
        raise
    except Exception as error:
        # Avoid persisting potentially sensitive unexpected exception details.
        run.error_message = f'Unexpected error: {type(error).__name__}'
        raise
    finally:
        log_run(run, status)
