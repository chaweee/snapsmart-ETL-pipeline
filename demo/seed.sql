-- Run once in the NEW demo-source project after source_schema.sql.
-- All records are fictional. Fixed IDs make expected results reproducible.
-- A second run fails on duplicate IDs and rolls back instead of duplicating data.
BEGIN;

INSERT INTO public.packages
  (id, name, coverage_type, price, required_down_payment,
   requires_photographer, requires_videographer)
VALUES
  ('demo-photo', 'Demo Photo Package', 'photo', 10000, 3000, true, false),
  ('demo-photo-video', 'Demo Photo and Video Package', 'photo_video', 20000, 6000, true, true);

INSERT INTO public.bookings
  (id, client_name, package_id, event_type, event_date, event_location,
   status, total_amount, required_down_payment, is_test, created_at)
VALUES
  ('10000000-0000-4000-8000-000000000001', 'Demo Client 01', 'demo-photo',
   'Birthday', '2026-09-05', 'Demo Venue A', 'Completed', 10000, 3000, true, '2026-08-01T08:00:00Z'),
  ('10000000-0000-4000-8000-000000000002', 'Demo Client 02', 'demo-photo-video',
   'Wedding', '2026-12-10', 'Demo Venue B', 'Confirmed', 20000, 6000, true, '2026-09-01T08:00:00Z'),
  ('10000000-0000-4000-8000-000000000003', 'Demo Client 03', 'demo-photo',
   'Birthday', '2026-12-15', 'Demo Venue C', 'Pending', 10000, 3000, true, '2026-10-01T08:00:00Z'),
  ('10000000-0000-4000-8000-000000000004', 'Demo Client 04', 'demo-photo-video',
   'Wedding', '2026-12-20', 'Demo Venue D', 'Awaiting Payment Verification', 20000, 6000, true, '2026-10-02T08:00:00Z'),
  ('10000000-0000-4000-8000-000000000005', 'Demo Client 05', 'demo-photo',
   'Birthday', '2026-12-22', 'Demo Venue E', 'Payment Insufficient', 10000, 3000, true, '2026-10-03T08:00:00Z'),
  ('10000000-0000-4000-8000-000000000006', 'Demo Client 06', 'demo-photo-video',
   'Wedding', '2026-11-25', 'Demo Venue F', 'Cancelled', 20000, 6000, true, '2026-10-04T08:00:00Z');

INSERT INTO public.payments
  (id, booking_id, amount, method, reference_number, status, created_at, verified_at)
VALUES
  ('20000000-0000-4000-8000-000000000001', '10000000-0000-4000-8000-000000000001',
   3000, 'demo_transfer', 'DEMO-001', 'Verified', '2026-08-02T08:00:00Z', '2026-08-02T09:00:00Z'),
  ('20000000-0000-4000-8000-000000000002', '10000000-0000-4000-8000-000000000001',
   7000, 'demo_transfer', 'DEMO-002', 'Verified', '2026-09-05T08:00:00Z', '2026-09-05T09:00:00Z'),
  ('20000000-0000-4000-8000-000000000003', '10000000-0000-4000-8000-000000000002',
   6000, 'demo_transfer', 'DEMO-003', 'Verified', '2026-09-02T08:00:00Z', '2026-09-02T09:00:00Z'),
  ('20000000-0000-4000-8000-000000000004', '10000000-0000-4000-8000-000000000004',
   6000, 'demo_transfer', 'DEMO-004', 'For Verification', '2026-10-03T08:00:00Z', NULL),
  ('20000000-0000-4000-8000-000000000005', '10000000-0000-4000-8000-000000000005',
   1000, 'demo_transfer', 'DEMO-005', 'Insufficient', '2026-10-04T08:00:00Z', NULL),
  ('20000000-0000-4000-8000-000000000006', '10000000-0000-4000-8000-000000000006',
   6000, 'demo_transfer', 'DEMO-006', 'Rejected', '2026-10-05T08:00:00Z', NULL);

COMMIT;

-- Verification: 6 bookings, 6 payment transactions, 16000 verified amount.
SELECT
  (SELECT count(*) FROM public.bookings WHERE id IN (
    '10000000-0000-4000-8000-000000000001', '10000000-0000-4000-8000-000000000002',
    '10000000-0000-4000-8000-000000000003', '10000000-0000-4000-8000-000000000004',
    '10000000-0000-4000-8000-000000000005', '10000000-0000-4000-8000-000000000006'
  )) AS demo_bookings,
  count(*) AS demo_payments,
  sum(amount) FILTER (WHERE status = 'Verified') AS verified_amount
FROM public.payments
WHERE reference_number IN ('DEMO-001', 'DEMO-002', 'DEMO-003', 'DEMO-004', 'DEMO-005', 'DEMO-006');
