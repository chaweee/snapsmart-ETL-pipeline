# Extraction run logging

Every invocation of `src/extract.py` or `src/export_supabase.py` records
one run in `logs/pipeline_runs.sqlite3`. The automatic export invokes the
extractor within the same run, so it does not create duplicate records.
The SQLite file is local and excluded from Git.

Each record contains `pipeline_run_id` (UUID), UTC `start_timestamp` and
`end_timestamp`, `extraction_status` (`success` or `failed`), `records_read`,
`records_extracted`, `records_rejected`, and `error_message`. Counts combine
bookings and payments. Read means rows successfully read from both input CSVs;
extracted means rows successfully written to JSON. If either input fails
before both are read, read is zero. Extraction has no row-level rejection:
`records_rejected` is zero; validation rejections are reported separately by
issue #3. Unexpected exception messages are not logged to avoid exposing
secrets. Normal file and API errors are recorded without the server key.

The `extraction_table_counts` table records counts by run ID and source table.
Each successful run also creates `output/batches/<run_id>/extracted.json` as
the Stage 2 handover. Transformation quality results are stored alongside that
batch, rather than in the extraction run table. See `05-stage-1-and-2.md`.

Logs are retained indefinitely, exceeding the 90-day minimum. Retention
depends on keeping the local SQLite file and backups; deleting the file loses
the audit history. A log write failure raises an error instead of silently
claiming a logged extraction.

To inspect using Python from the project root:

```powershell
python -c "import sqlite3; db=sqlite3.connect('logs/pipeline_runs.sqlite3'); print(*db.execute('SELECT * FROM extraction_runs ORDER BY start_timestamp DESC'), sep='\n')"
```
