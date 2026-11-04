# Stage 1 and 2: pipeline documentation and demo contract

## Run and handover

From the repository root, with the demo project's credentials configured as
described in `01-data-source.md`, run:

```powershell
python src/pipeline.py
```

The batch ID printed in the terminal is the extraction run ID. Each run takes
a **full** snapshot, without a date filter; the batch window is the entire
source as observed during that run. Execution is currently **on demand**;
no scheduler is configured. The Supabase Data API is paginated, so its reads
are not a transactionally consistent cross-table snapshot. Keep the source
unchanged while the demo runs; schedule or snapshot isolation is future work.

Stage 1 produces `output/batches/<run_id>/extracted.json`, a run-ID-labelled
immutable-by-convention snapshot. Stage 2 consumes that snapshot, not the
source database. Keep the file unchanged for reproducible reruns:

```powershell
python src/transform.py output/batches/<run_id>/extracted.json
```

Rerunning replaces that batch's transformed output and quarantine entries,
not source data. Given the same snapshot and script version, results are
deterministic. A new extraction creates a new batch ID and may see new data.
An interrupted transformation should be rerun; output files are not written
as an atomic group. Treat results as complete only after `quality_report.json`
is generated and the process completes successfully. A prior report can
remain after a failed rerun; use the exit code, not that file alone.

## Stage 1: source and extraction contract

Source is the **SnapSmart demo copy** of the capstone booking system,
PostgreSQL on Supabase. Its purpose is to record bookings and payment
transactions; the copy contains synthetic data. Supabase REST GET requests
export the `public` tables to local UTF-8 CSV; Python's CSV library reads
all rows and keeps only the fields below. The demo extraction includes
`is_test` bookings. `public` is the source; `analytics` is a later
destination and is not needed for Stage 1 or 2.

| Table | Column (source type) | Key / reason |
| --- | --- | --- |
| bookings | id (uuid) | PK; identifies booking and summary |
| bookings | client_name (text) | booking descriptor |
| bookings | event_date (date) | event analysis |
| bookings | package_id (text, nullable) | package analysis |
| bookings | status (text) | booking status |
| bookings | total_amount (numeric(12,2)) | price and balance |
| payments | id (uuid) | PK; unique transaction and tie-break |
| payments | booking_id (uuid) | FK to bookings.id |
| payments | amount (numeric(12,2)) | payment totals |
| payments | status (text) | distinguish verified payments |
| payments | created_at (timestamptz) | ordering first payment |

The extraction naming contract preserves source snake_case names. Required
headers must exist; extra columns are ignored, missing/duplicate/blank headers
or malformed rows fail extraction rather than guessing a mapping. Review
source schema changes and update the contract and tests before rerunning.
CSV empty fields cannot distinguish SQL NULL from empty strings.

### Checks, thresholds and ownership

| ID | Check / target | Pass condition | Severity and action |
| --- | --- | --- | --- |
| E01 | API connectivity and both tables | Both GET exports succeed | Critical: fail run; operator checks connection, permissions, then reruns |
| E02 | Local CSV accessibility | Both files readable | Critical: fail; operator restores files |
| E03 | Required headers/row structure | All scoped columns and consistent field counts | Critical: fail; operator investigates schema drift |
| E04 | Record counts | Read and extracted counts are logged for each table | Critical: output error fails run; operator investigates |
| C01–C10 | Keys, references and field quality | No rejected source records | High: quarantine and REVIEW; operator corrects source and reruns |

Each extraction has a UUID, UTC start/end, status, combined counts and errors
in `logs/pipeline_runs.sqlite3`; `extraction_table_counts` records per-table
read/extracted counts for complete CSV reads. If a file fails before both
are read, counts are zero, not estimates of partially read rows. Extraction
does not itself reject individual rows. Stage 2 quality results and rejection
counts are recorded separately under the same batch ID in the batch's
`quality_report.json`, `profiling.csv` and `quality.sqlite3`.

Logs and batches are local, Git-ignored, and kept indefinitely by the scripts
(minimum target: 90 days). Restrict filesystem access to the project team;
the local operating system and backup practices enforce this, not the script.
The pipeline operator is responsible for backups, access review and deleting
expired artifacts only after at least 90 days and team approval. No automatic
deletion or permission management exists. Avoid including real client data in
demo artifacts. Credentials remain in `.env`, which is Git-ignored.

## Stage 2: profiling and cleaning contract

`profiling.csv` lists observed failures per table/column/rule, a sample,
affected count and percentage (per input table), and planned treatment. A
clean demo yields a header-only file; it does not imply the checks were
skipped. Quarantine stores the original row in a local SQLite table, with
batch ID, source table, record number, rule ID and reason. A record can have
multiple rule failures but counts once in reconciliation. `quality_report.json`
contains input, accepted, rejected, reconciliation and rejection rate.

| Rule | Target and condition | Action / justification |
| --- | --- | --- |
| C01 | Either `id` absent or not UUID | Quarantine; a usable PK is required |
| C02 | Either normalized UUID appears more than once | Quarantine **all copies**; no arbitrary winner |
| C03 | Booking client name blank after trimming | Quarantine; name required |
| C04 | Booking date not ISO date | Quarantine; don't guess dates |
| C05 | Booking total invalid, negative, >2 decimals or outside numeric(12,2) | Quarantine; preserve financial precision |
| C06 | Booking status not one of source schema's allowed values | Quarantine; do not invent status mapping |
| C07 | Payment booking ID invalid or references no accepted booking | Quarantine; referential integrity |
| C08 | Payment amount invalid, nonpositive, >2 decimals or outside numeric(12,2) | Quarantine; preserve financial precision |
| C09 | Payment status not one of source schema's allowed values | Quarantine; avoid invented mappings |
| C10 | Payment timestamp invalid or missing timezone | Quarantine; ordering must be unambiguous |

All string fields are trimmed; UUIDs become canonical lowercase UUIDs,
dates ISO `YYYY-MM-DD`, timestamps UTC ISO 8601, and money exact Decimal
with two decimals. Blank nullable `package_id` stays blank. Unknown status
codes are rejected, not mapped. IDs linked to rejected bookings are orphans.

### Business rules and output mapping

| Rule | Logic and output | Reason |
| --- | --- | --- |
| B01 | Rename bookings.id to booking_id and status to booking_status | Destination naming contract |
| B02 | One payment summary per accepted booking; payment_id = booking_id | Stable unique summary ID, including no-payment bookings |
| B03 | down_payment = first Verified payment by UTC created_at then UUID, else 0.00 | Agreed demo convention, not proof of real-world payment intent |
| B04 | remaining_balance = booking total - sum of Verified payments | Include only confirmed payments; negative preserves overpayment |
| B05 | Keep cancelled bookings and other payment statuses in cleaned data | Preserve source facts; cancelled balance is not necessarily collectible |

`transformed_bookings.csv` contains `booking_id` (PK), `client_name`,
`event_date`, `package_id`, `booking_status`. `transformed_payments.csv`
contains `payment_id` (PK), `booking_id` (unique FK to transformed
bookings), `down_payment`, `remaining_balance`, `total_amount`.
No dimension/fact prefixes or surrogate dimension keys are used for this
small demo. These CSVs match the destination contract in
`02-destination-setup.md`; this stage does not load them to Supabase.

### Acceptance and problems

Automatic pass requires zero rejected records (0% threshold) and per-table
input = accepted + rejected. Otherwise status is REVIEW and the command
returns nonzero; outputs are for inspection only. The pipeline operator
reviews quarantine, corrects the source or contract, and starts a new
extraction; the team owns final approval. A missing file, source outage or
schema drift causes a failed extraction and no Stage 2 handover. Source
changes during paginated reads may cause inconsistent snapshots; mitigate by
freezing demo writes. Orphan records and duplicate/invalid values can distort
financial summaries; quarantine them rather than silently repairing them.
Extraction preserves source values; cleaning and business calculations occur
only in Stage 2. There is no configured scheduler, external access control,
or automated 90-day backup in this demo.
