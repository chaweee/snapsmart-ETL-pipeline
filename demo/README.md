# Demo source database

`source_schema.sql` reproduces the four supplied capstone table definitions
and booking snapshot trigger in dependency order. It is a source database
setup, separate from the simplified ETL destination requested in issue #1.

## Apply

1. Open the **new demo-source Supabase project**, then SQL Editor.
2. Paste the contents of `source_schema.sql` and run once.
3. Confirm `profiles`, `packages`, `bookings`, and `payments` appear.

The script runs in one transaction and expects these tables not to exist.
It does not delete or replace existing tables. It requires Supabase's
existing `auth.users` table and does not copy Auth accounts, Storage,
project settings, source RLS policies, or data.

For synthetic data, insert packages before bookings, then payments.
Bookings may leave `client_id`, `preferred_photographer_id`,
`preferred_videographer_id`, and `walk_in_created_by` NULL.
Payments may leave `verified_by` NULL. This allows a database-only demo
without creating Auth accounts. A non-NULL profile ID must reference an
actual user in the new project's `auth.users` table.

## Verify in SQL Editor

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('profiles', 'packages', 'bookings', 'payments')
ORDER BY table_name;

SELECT trigger_name, event_manipulation, action_timing
FROM information_schema.triggers
WHERE event_object_schema = 'public'
  AND event_object_table = 'bookings';
```

Expected: four tables, and `booking_team_requirement_snapshot` as a
`BEFORE INSERT` trigger.

## Source-to-destination mapping

- Source `bookings.id` maps to destination `booking_id` (UUID).
- Source `bookings.status` maps to destination `booking_status`.
- Source payments are individual transactions, potentially many per booking.
- `required_down_payment` is an obligation, not an actual collected payment.
- The destination uses one payment summary per booking. See
  `../docs/02-destination-setup.md` for the agreed payment rules.

## Seed synthetic records

Run `seed.sql` once in the demo-source SQL Editor after the schema script.
It inserts two packages, six bookings (one for each allowed status), and
six payment transactions spanning all four allowed payment statuses.
All bookings are marked `is_test = true`; include these records when
extracting this demo dataset. Profile references remain NULL.

The final verification query should return `demo_bookings = 6`,
`demo_payments = 6`, and `verified_amount = 16000.00`.
Booking 01 has two verified payments totaling 10000; booking 02 has one
verified payment of 6000. Booking 03 has no payments. Other payment
statuses are provided to exercise later transformation decisions, not to
define whether an insufficient payment counts as collected revenue.

The seed uses fixed primary keys and a transaction: rerunning it raises a
duplicate-key error and rolls back the attempted inserts. It does not
overwrite existing records. These are valid source rows; intentionally
malformed CSV fixtures belong to the later validation issue.
