"""Read the demo Supabase source, save scoped CSVs, then run extraction."""

import csv
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from dotenv import load_dotenv

if __package__:
    from .extract import REQUIRED_COLUMNS, extract
    from .run_log import LoggingParser, logged_run
else:
    from extract import REQUIRED_COLUMNS, extract
    from run_log import LoggingParser, logged_run


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ORIGINAL_PROJECT = "yvsdlnuaqeqzmrsbubkq.supabase.co"


def fetch_table(url, key, table, columns):
    """Fetch every page in stable ID order; never send database write requests."""
    headers = {"apikey": key, "Accept-Profile": "public"}
    # New secret API keys are not JWTs; only legacy keys use Bearer auth.
    if not key.startswith("sb_secret_"):
        headers["Authorization"] = f"Bearer {key}"
    records = []
    seen = set()
    while True:
        query = urlencode({
            "select": ",".join(columns), "order": "id.asc",
            "limit": 1000, "offset": len(records),
        })
        request = Request(f"{url}/rest/v1/{table}?{query}", headers=headers)
        try:
            with urlopen(request, timeout=30) as response:
                page = json.load(response, parse_float=str)
        except HTTPError as error:
            raise ValueError(f"{table}: Supabase HTTP {error.code}; check project URL, server key, and table access") from None
        except URLError:
            raise ValueError(f"{table}: cannot reach Supabase; check network and project URL") from None
        if not isinstance(page, list):
            raise ValueError(f"{table}: expected a JSON array")
        if not page:
            break
        for row in page:
            if not isinstance(row, dict) or not set(columns).issubset(row):
                raise ValueError(f"{table}: response is missing scoped columns")
            if row["id"] in seen:
                raise ValueError(f"{table}: duplicate ID across pages; source may have changed, retry export")
            seen.add(row["id"])
        records.extend(page)
        # Advance by actual returned rows, even when server caps page size.
    return records


def export(argv, run):
    parser = LoggingParser(description=__doc__, run=run)
    parser.add_argument("--raw-dir", type=Path, default=PROJECT_ROOT / "data" / "raw")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "output" / "extracted.json")
    args = parser.parse_args(argv)
    load_dotenv(PROJECT_ROOT / ".env")
    url = os.getenv("SUPABASE_SOURCE_URL", "").strip().rstrip("/")
    key = os.getenv("SUPABASE_SOURCE_KEY", "").strip()
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or not parsed.hostname
            or not parsed.hostname.endswith(".supabase.co")
            or parsed.username or parsed.password or parsed.port
            or parsed.path or parsed.query or parsed.fragment):
        parser.exit(1, "Set SUPABASE_SOURCE_URL to the demo project's https://<ref>.supabase.co URL in .env\n")
    if parsed.hostname == ORIGINAL_PROJECT:
        parser.exit(1, "Use the NEW demo project, not the original capstone project.\n")
    if not key:
        parser.exit(1, "Set SUPABASE_SOURCE_KEY in local .env (do not share the key in chat).\n")
    paths = {table: args.raw_dir / f"{table}.csv" for table in REQUIRED_COLUMNS}
    if args.output.resolve() in {path.resolve() for path in paths.values()}:
        parser.exit(1, "Output must not overwrite a source CSV.\n")
    try:
        # Fetch both before replacing any local CSVs.
        tables = {
            table: fetch_table(url, key, table, sorted(columns))
            for table, columns in REQUIRED_COLUMNS.items()
        }
        args.raw_dir.mkdir(parents=True, exist_ok=True)
        for table, rows in tables.items():
            with paths[table].open("w", encoding="utf-8", newline="") as destination:
                writer = csv.DictWriter(destination, fieldnames=sorted(REQUIRED_COLUMNS[table]), extrasaction="ignore")
                writer.writeheader()
                writer.writerows(rows)
            print(f"Exported public.{table}: {len(rows)} rows")
    except (OSError, ValueError) as error:
        parser.exit(1, f"Export failed: {error}\n")
    return extract([
        "--bookings", str(paths["bookings"]),
        "--payments", str(paths["payments"]), "--output", str(args.output),
    ], run)


def main(argv=None):
    return logged_run(lambda run: export(argv, run))


if __name__ == "__main__":
    raise SystemExit(main())
