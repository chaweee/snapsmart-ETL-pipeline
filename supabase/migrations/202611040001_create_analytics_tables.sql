-- Issue #1: ETL destination in the same project as the public demo source.
BEGIN;

CREATE SCHEMA IF NOT EXISTS analytics;

CREATE TABLE analytics.bookings (
  booking_id uuid PRIMARY KEY,
  client_name text NOT NULL,
  event_date date NOT NULL,
  package_id text,
  booking_status text NOT NULL
);

-- One payment summary per booking, not one row per source transaction.
CREATE TABLE analytics.payments (
  payment_id uuid PRIMARY KEY,
  booking_id uuid NOT NULL UNIQUE REFERENCES analytics.bookings (booking_id),
  down_payment numeric(12, 2) NOT NULL CHECK (down_payment >= 0),
  remaining_balance numeric(12, 2) NOT NULL,
  total_amount numeric(12, 2) NOT NULL CHECK (total_amount >= 0)
);

COMMENT ON COLUMN analytics.payments.payment_id IS
  'Use the source booking UUID as a stable summary identifier for repeatable loads.';
COMMENT ON COLUMN analytics.payments.down_payment IS
  'First Verified source payment ordered by created_at, then id; zero if none.';
COMMENT ON COLUMN analytics.payments.remaining_balance IS
  'Booking total minus all Verified payments; negative values preserve overpayments.';

COMMIT;
