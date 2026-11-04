# Data quality checks (issue #3)

From the repository root, first run `python src/export_supabase.py`, then:

```powershell
python src/validate.py
```

The validator reads `data/raw/bookings.csv` and `data/raw/payments.csv`.
Use `--bookings`, `--payments`, and `--output-dir` to override paths.
It checks file accessibility and CSV structure, including required headers,
before producing output. Source booking `id` is the booking primary key;
source payment `id` is the payment primary key. Payments reference bookings
through `booking_id`.

Empty IDs and **all copies** of duplicate IDs are rejected, rather than
arbitrarily selecting one. Payments without a matching valid booking are
rejected, including references to a rejected duplicate booking. IDs are
compared after trimming surrounding whitespace; output values are otherwise
preserved. The report's record number is one-based among data records, not
necessarily a physical file line number when CSV fields contain newlines.

The following local, Git-ignored CSV files can be opened in Excel:

- `output/cleaned_bookings.csv`: rows passing booking ID checks.
- `output/cleaned_payments.csv`: rows passing payment ID and reference checks.
- `output/validation_report.csv`: rejected row identifiers and reasons.

Exit code is zero only when all checks pass; a nonzero exit signals a source
file error or rejected records. On a source file error, existing output files
are not refreshed and must not be mistaken for the latest run. On rejection,
clean files and the report are written for inspection; resolve errors before
using them downstream. This stage does not check dates, amounts or statuses,
calculate balances, or load to Supabase. Transformation remains a later step.
