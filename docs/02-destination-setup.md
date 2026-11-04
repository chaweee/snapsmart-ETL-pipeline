# Issue #1: Supabase ETL destination

The new demo Supabase project contains both the source and destination:

- `public`: capstone source tables populated using `demo/seed.sql`.
- `analytics`: simplified destination tables populated by the later Python ETL.

## Apply once

Open the **new demo project** SQL Editor and run
`supabase/migrations/202611040001_create_analytics_tables.sql`.
The migration expects the destination tables not to exist and runs in a
transaction. No rows are loaded by this migration.

## Data contract

`analytics.bookings` has one row per source booking:

| Destination | Source |
| --- | --- |
| booking_id | public.bookings.id |
| client_name | public.bookings.client_name |
| event_date | public.bookings.event_date |
| package_id | public.bookings.package_id (nullable) |
| booking_status | public.bookings.status |

`analytics.payments` has **one summary per booking**, including bookings
without payments. Its unique booking foreign key enforces that granularity.

| Destination | Transformation |
| --- | --- |
| payment_id | Source booking UUID, reused as a stable summary ID |
| booking_id | Source booking UUID |
| down_payment | First Verified payment by created_at, then id; zero if none |
| remaining_balance | Booking total minus sum of all Verified payments |
| total_amount | public.bookings.total_amount |

Only `Verified` payments count under this demo contract. Required down
payment is an obligation, not a collected amount. Negative remaining
balances preserve overpayment credits. Include `is_test = true` bookings
for this demo. Cancelled bookings remain available for status reporting;
their balances are arithmetic balances, not automatically collectible debt.

The first-verified-payment rule is a demo convention, not a general inference
about real-world payment intent. Deterministic IDs allow later upserts.

## Verify after applying

```sql
SELECT table_name, column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'analytics'
  AND table_name IN ('bookings', 'payments')
ORDER BY table_name, ordinal_position;

SELECT conrelid::regclass AS table_name, conname,
       pg_get_constraintdef(oid) AS definition
FROM pg_constraint
WHERE conrelid IN ('analytics.bookings'::regclass, 'analytics.payments'::regclass)
ORDER BY table_name, conname;
```

Expected: five columns per table, both primary keys, a unique payments
booking ID, and a foreign key from payments to bookings.

The custom schema can be accessed through a PostgreSQL connection. If issue
#5 uses the Supabase Data API instead, configure schema exposure and access
grants for the intended server role as part of that connection setup.
