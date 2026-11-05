-- Payment + game integrity.

-- ── 1. Pending gateway attempts were stored as status='confirmed' ───────────
-- (and so counted as money received everywhere). Fix existing rows.
UPDATE payments SET status = 'pending'
WHERE gateway_status = 'pending' AND status = 'confirmed';

UPDATE payments SET gateway_status = 'manual' WHERE gateway_status IS NULL;

-- ── 2. At most one live payment per participant per bill ────────────────────
-- Check-then-insert in the API was racy. First retire any pre-existing duplicates
-- (keep the earliest; non-destructive), then enforce it in the database.
UPDATE payments p
SET gateway_status = 'superseded', status = 'superseded'
WHERE p.gateway_status IN ('manual', 'pending', 'verified')
  AND EXISTS (
    SELECT 1 FROM payments q
    WHERE q.participant_id = p.participant_id
      AND q.bill_id = p.bill_id
      AND q.gateway_status IN ('manual', 'pending', 'verified')
      AND (q.confirmed_at < p.confirmed_at
           OR (q.confirmed_at = p.confirmed_at AND q.id < p.id))
  );

ALTER TABLE payments
  ALTER COLUMN gateway_status SET DEFAULT 'manual',
  ALTER COLUMN gateway_status SET NOT NULL;

ALTER TABLE payments
  ADD CONSTRAINT payments_gateway_status_check
    CHECK (gateway_status IN ('manual', 'pending', 'verified', 'failed', 'expired', 'superseded')),
  -- NOT VALID: enforced for new rows without failing on any odd historical row.
  ADD CONSTRAINT payments_status_check
    CHECK (status IN ('confirmed', 'pending', 'failed', 'expired', 'superseded')) NOT VALID,
  ADD CONSTRAINT payments_amount_positive
    CHECK (amount > 0) NOT VALID;

CREATE UNIQUE INDEX payments_one_live_per_participant
  ON payments (participant_id, bill_id)
  WHERE gateway_status IN ('manual', 'pending', 'verified');

-- ── 3. One game result per bill ─────────────────────────────────────────────
-- Fails loudly (rather than deleting history) if a bill was locked twice.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM game_results GROUP BY bill_id HAVING count(*) > 1) THEN
    RAISE EXCEPTION 'game_results has several rows for one bill; resolve manually, then re-run';
  END IF;
END $$;

CREATE UNIQUE INDEX game_results_one_per_bill ON game_results (bill_id);

-- ── 4. push_tokens upserts ──────────────────────────────────────────────────
-- PostgREST's on_conflict=<col> cannot target a PARTIAL unique index, so the old
-- upsert would have errored. A plain UNIQUE constraint allows multiple NULLs and
-- is what ON CONFLICT needs.
DROP INDEX IF EXISTS push_tokens_participant_idx;
DROP INDEX IF EXISTS push_tokens_user_idx;
ALTER TABLE push_tokens ADD CONSTRAINT push_tokens_user_id_key UNIQUE (user_id);
