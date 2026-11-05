-- Lock down direct database access.
--
-- Before this migration the public (anon) API key shipped inside the web bundle and
-- the mobile app could read EVERY bill, participant (name + phone number) and
-- payment in the database, insert arbitrary payments, and delete other people's push
-- tokens. Clients no longer talk to these tables directly: the FastAPI backend does
-- all reads and writes with the service-role key (which bypasses RLS) and enforces
-- authorisation itself. RLS is now defence in depth: deny by default, with
-- read-only access for a signed-in organiser to their own rows.

-- ── Remove the open policies ────────────────────────────────────────────────
DROP POLICY IF EXISTS "public_read_bills"            ON bills;
DROP POLICY IF EXISTS "public_read_participants"     ON participants;
DROP POLICY IF EXISTS "anyone_confirm_payment"       ON payments;
DROP POLICY IF EXISTS "public_read_payments"         ON payments;
DROP POLICY IF EXISTS "public_read_game_results"     ON game_results;
DROP POLICY IF EXISTS "anyone_register_push_token"   ON push_tokens;
DROP POLICY IF EXISTS "owner_delete_push_token"      ON push_tokens;

-- ── Writes only via the API (it validates; a direct write would not) ────────
-- Organisers could previously write their own bills/participants/game_results rows
-- straight through PostgREST, skipping validation and the server-authoritative
-- game logic. Make those read-only.
DROP POLICY IF EXISTS "organisers_manage_bills"        ON bills;
DROP POLICY IF EXISTS "organiser_manage_participants"  ON participants;
DROP POLICY IF EXISTS "organiser_write_game_results"   ON game_results;

CREATE POLICY "organiser_read_own_bills"
  ON bills FOR SELECT
  USING (auth.uid() = organiser_id);

CREATE POLICY "organiser_read_own_participants"
  ON participants FOR SELECT
  USING (EXISTS (
    SELECT 1 FROM bills WHERE bills.id = participants.bill_id AND bills.organiser_id = auth.uid()
  ));

CREATE POLICY "organiser_read_own_payments"
  ON payments FOR SELECT
  USING (EXISTS (
    SELECT 1 FROM bills WHERE bills.id = payments.bill_id AND bills.organiser_id = auth.uid()
  ));

CREATE POLICY "organiser_read_own_game_results"
  ON game_results FOR SELECT
  USING (EXISTS (
    SELECT 1 FROM bills WHERE bills.id = game_results.bill_id AND bills.organiser_id = auth.uid()
  ));

CREATE POLICY "owner_manage_push_token"
  ON push_tokens FOR ALL
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

-- ── Storage ─────────────────────────────────────────────────────────────────
-- The old SELECT policy let anyone LIST every receipt (and so enumerate bill ids).
-- Public buckets serve files by URL without any policy, so dropping it only removes
-- listing. Uploads go through the API (service role), so the broad INSERT policy goes too.
DROP POLICY IF EXISTS "Public read receipts"     ON storage.objects;
DROP POLICY IF EXISTS "Organiser upload receipt" ON storage.objects;

-- The QR upload endpoint writes to this bucket but no migration ever created it.
INSERT INTO storage.buckets (id, name, public)
VALUES ('payment-qr', 'payment-qr', true)
ON CONFLICT (id) DO NOTHING;

-- Defence in depth behind the API's own size/type checks.
UPDATE storage.buckets
SET file_size_limit = 5242880,
    allowed_mime_types = ARRAY['image/png', 'image/jpeg', 'image/webp', 'image/gif']
WHERE id IN ('receipts', 'payment-qr');
