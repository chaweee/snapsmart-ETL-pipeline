# CSV extraction (issue #2)

Current scope: **extraction -> cleaning -> transformation**. Loading into
Supabase is a later stage (issue #5). Extraction reads local source exports;
it does not change database records. The optional source export command
automatically downloads those CSVs from the demo Supabase project first.

## Automatic source export + extraction

1. Install dependencies: `python -m pip install -r requirements.txt`.
2. Copy `.env.example` to `.env` in the repository root.
3. In the **new demo project**, get its project URL and backend secret key
   (or legacy `service_role` key) from the project's API settings/Connect UI.
4. Fill `SUPABASE_SOURCE_URL` and `SUPABASE_SOURCE_KEY` in `.env` locally.
   Do not paste the key into chat or commit it; `.env` is ignored by Git.
5. Run:

```powershell
python src/export_supabase.py
```

This reads both `public` source tables through the Supabase Data API,
downloads all pages in ID order to `data/raw`, then runs CSV extraction.
It requests only the scoped columns and saves `output/extracted.json`.
It makes only GET requests; no database load step runs.
Use the server key for full extraction: a public/anon key may hide rows
under RLS. The script rejects the known original capstone project URL.
Keep the demo source unchanged during the export: paginated REST reads do
not provide a transaction snapshot across pages or tables.

## Export the demo source

In the new Supabase project's SQL Editor, run each query separately and
download each result as CSV, including its column headers:

```sql
SELECT * FROM public.bookings ORDER BY id;
```

Save as `data/raw/bookings.csv`.

```sql
SELECT * FROM public.payments ORDER BY id;
```

Save as `data/raw/payments.csv`. Create `data/raw` locally if needed.
Export the `public` source tables, not the empty `analytics` destinations.
Include the synthetic `is_test = true` bookings for this demo.

## Run from the repository root

Python 3 is required. Extraction uses only the standard library.

```powershell
python src/extract.py --bookings data/raw/bookings.csv --payments data/raw/payments.csv --output output/extracted.json
```

The seeded dataset should report **6 bookings and 6 payments**.
The output JSON contains `bookings` and `payments` arrays for subsequent
cleaning/transformation scripts. Successful reruns replace the output.
Local CSV exports and extracted JSON artifacts are ignored by Git.

## Extraction behavior

- Accept UTF-8 CSV, including a UTF-8 BOM and quoted commas/newlines.
- Select only scoped columns; preserve string values, spaces, empty fields,
  and duplicate rows. Extra input columns are ignored.
- Do not parse amounts as floats, normalize statuses, or calculate balances.
- Require the source headers needed for the agreed transformation contract.
- Reject missing files, invalid encoding, missing/duplicate/empty headers,
  and rows with inconsistent field counts with a nonzero exit code.
- Header-only exports yield empty arrays. Physically blank lines are skipped.

These are file-structure checks. Required-value checks, duplicate IDs,
foreign-key checks, date parsing, and financial rules belong to the later
cleaning/validation stage. Raw CSV empty fields are preserved as empty
strings; CSV alone cannot reliably distinguish SQL NULL from empty text.

### Scoped columns

- Bookings: `id`, `client_name`, `event_date`, `package_id`, `status`, `total_amount`.
- Payments: `id`, `booking_id`, `amount`, `status`, `created_at`.

All rows are extracted on every run without status/date filtering.
The automatic JSON-to-CSV export represents SQL NULL as an empty field.
