-- Run in the SQL Editor of a NEW Supabase demo-source project.
-- Copies the supplied source definitions, not the issue #1 ETL destination.
-- Auth users, existing data, grants, and source RLS policies are not copied.
-- This script intentionally fails if these tables already exist.
BEGIN;

CREATE TABLE public.profiles (
  id uuid NOT NULL,
  full_name text NOT NULL DEFAULT '',
  phone text,
  role text NOT NULL DEFAULT 'client',
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT profiles_pkey PRIMARY KEY (id),
  CONSTRAINT profiles_id_fkey FOREIGN KEY (id) REFERENCES auth.users (id) ON DELETE CASCADE,
  CONSTRAINT profiles_role_check CHECK (role = ANY (ARRAY['client', 'admin', 'photographer', 'videographer']))
);

CREATE TABLE public.packages (
  id text NOT NULL,
  name text NOT NULL,
  subtitle text NOT NULL DEFAULT '',
  coverage_type text NOT NULL,
  price numeric(12, 2) NOT NULL,
  required_down_payment numeric(12, 2) NOT NULL,
  inclusions jsonb NOT NULL DEFAULT '[]'::jsonb,
  requires_photographer boolean NOT NULL DEFAULT true,
  requires_videographer boolean NOT NULL DEFAULT false,
  is_popular boolean NOT NULL DEFAULT false,
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT packages_pkey PRIMARY KEY (id),
  CONSTRAINT packages_check CHECK (required_down_payment >= 0 AND required_down_payment <= price),
  CONSTRAINT packages_coverage_type_check CHECK (coverage_type = ANY (ARRAY['photo', 'photo_video', 'soft_copy'])),
  CONSTRAINT packages_inclusions_check CHECK (jsonb_typeof(inclusions) = 'array'),
  CONSTRAINT packages_price_check CHECK (price >= 0)
);

CREATE TABLE public.bookings (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  client_id uuid,
  client_name text NOT NULL,
  client_email text,
  client_phone text,
  package_id text,
  package_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,
  event_type text NOT NULL,
  event_date date NOT NULL,
  start_time time without time zone,
  end_time time without time zone,
  event_location text NOT NULL,
  theme_motif text,
  status text NOT NULL DEFAULT 'Pending',
  total_amount numeric(12, 2) NOT NULL,
  required_down_payment numeric(12, 2) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  public_gallery_permission boolean NOT NULL DEFAULT false,
  is_test boolean NOT NULL DEFAULT false,
  client_address text,
  bride_name text,
  groom_name text,
  notes text,
  test_consent_text text,
  request_notice text,
  request_notice_accepted_at timestamptz,
  marketing_choice_text text,
  marketing_choice_at timestamptz,
  preferred_photographer_id uuid,
  preferred_videographer_id uuid,
  church_location text,
  other_event_type text,
  booking_source text NOT NULL DEFAULT 'online',
  walk_in_created_by uuid,
  CONSTRAINT bookings_pkey PRIMARY KEY (id),
  CONSTRAINT bookings_client_id_fkey FOREIGN KEY (client_id) REFERENCES public.profiles (id) ON DELETE RESTRICT,
  CONSTRAINT bookings_package_id_fkey FOREIGN KEY (package_id) REFERENCES public.packages (id) ON DELETE RESTRICT,
  CONSTRAINT bookings_preferred_photographer_id_fkey FOREIGN KEY (preferred_photographer_id) REFERENCES public.profiles (id) ON DELETE SET NULL,
  CONSTRAINT bookings_preferred_videographer_id_fkey FOREIGN KEY (preferred_videographer_id) REFERENCES public.profiles (id) ON DELETE SET NULL,
  CONSTRAINT bookings_walk_in_created_by_fkey FOREIGN KEY (walk_in_created_by) REFERENCES public.profiles (id) ON DELETE RESTRICT,
  CONSTRAINT bookings_status_check CHECK (status = ANY (ARRAY[
    'Pending', 'Awaiting Payment Verification', 'Confirmed',
    'Payment Insufficient', 'Completed', 'Cancelled'
  ])),
  CONSTRAINT bookings_total_amount_check CHECK (total_amount >= 0),
  CONSTRAINT bookings_check CHECK (required_down_payment >= 0 AND required_down_payment <= total_amount)
);

CREATE INDEX bookings_client_id_idx ON public.bookings (client_id);
CREATE INDEX bookings_event_date_idx ON public.bookings (event_date);

CREATE OR REPLACE FUNCTION public.snapshot_booking_team_requirements()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO ''
AS $function$
DECLARE
  package_row public.packages%rowtype;
BEGIN
  IF new.package_id IS NULL THEN RETURN new; END IF;
  SELECT * INTO package_row FROM public.packages WHERE id = new.package_id;
  IF found THEN
    new.package_snapshot := coalesce(new.package_snapshot, '{}'::jsonb) || jsonb_build_object(
      'requires_photographer', package_row.requires_photographer,
      'requires_videographer', package_row.requires_videographer
    );
  END IF;
  RETURN new;
END;
$function$;

CREATE TRIGGER booking_team_requirement_snapshot
BEFORE INSERT ON public.bookings
FOR EACH ROW EXECUTE FUNCTION public.snapshot_booking_team_requirements();

CREATE TABLE public.payments (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  booking_id uuid NOT NULL,
  amount numeric(12, 2) NOT NULL,
  method text NOT NULL,
  reference_number text,
  proof_path text,
  status text NOT NULL DEFAULT 'For Verification',
  verified_by uuid,
  verified_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT payments_pkey PRIMARY KEY (id),
  CONSTRAINT payments_booking_id_fkey FOREIGN KEY (booking_id) REFERENCES public.bookings (id) ON DELETE RESTRICT,
  CONSTRAINT payments_verified_by_fkey FOREIGN KEY (verified_by) REFERENCES public.profiles (id) ON DELETE RESTRICT,
  CONSTRAINT payments_amount_check CHECK (amount > 0),
  CONSTRAINT payments_status_check CHECK (status = ANY (ARRAY['For Verification', 'Verified', 'Insufficient', 'Rejected']))
);

CREATE INDEX payments_booking_id_idx ON public.payments (booking_id);

COMMIT;
