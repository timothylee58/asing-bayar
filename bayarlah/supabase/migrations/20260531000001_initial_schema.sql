-- Bayar.lah initial schema

CREATE TABLE bills (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organiser_id  UUID REFERENCES auth.users(id),
  title         TEXT NOT NULL,
  description   TEXT,
  total_amount  NUMERIC(10,2) NOT NULL,
  per_person    NUMERIC(10,2),
  due_date      DATE,
  emoji_tag     TEXT DEFAULT '🍽️',
  status        TEXT DEFAULT 'active',
  game_mode     TEXT DEFAULT 'equal',
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE participants (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  bill_id       UUID REFERENCES bills(id) ON DELETE CASCADE,
  name          TEXT NOT NULL,
  phone         TEXT,
  amount_owed   NUMERIC(10,2),
  is_organiser  BOOLEAN DEFAULT FALSE,
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE payments (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  participant_id  UUID REFERENCES participants(id),
  bill_id         UUID REFERENCES bills(id),
  amount          NUMERIC(10,2),
  method          TEXT,
  confirmed_at    TIMESTAMPTZ DEFAULT NOW(),
  status          TEXT DEFAULT 'confirmed'
);

CREATE TABLE game_results (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  bill_id     UUID REFERENCES bills(id),
  game_type   TEXT NOT NULL,
  seed        TEXT,
  result_json JSONB,
  played_at   TIMESTAMPTZ DEFAULT NOW(),
  is_locked   BOOLEAN DEFAULT TRUE
);

-- Indexes
CREATE INDEX idx_bills_organiser ON bills(organiser_id);
CREATE INDEX idx_participants_bill ON participants(bill_id);
CREATE INDEX idx_payments_bill ON payments(bill_id);
CREATE INDEX idx_payments_participant ON payments(participant_id);
CREATE INDEX idx_game_results_bill ON game_results(bill_id);

-- RLS
ALTER TABLE bills ENABLE ROW LEVEL SECURITY;
ALTER TABLE participants ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE game_results ENABLE ROW LEVEL SECURITY;

-- Bills: organiser full access; public read by id (for share page)
CREATE POLICY "organisers_manage_bills"
  ON bills FOR ALL
  USING (auth.uid() = organiser_id);

CREATE POLICY "public_read_bills"
  ON bills FOR SELECT
  USING (true);

-- Participants: read by bill (public share); write by organiser
CREATE POLICY "public_read_participants"
  ON participants FOR SELECT
  USING (true);

CREATE POLICY "organiser_manage_participants"
  ON participants FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM bills WHERE bills.id = participants.bill_id AND bills.organiser_id = auth.uid()
    )
  );

-- Payments: anyone can insert (no-login confirmation); organiser reads
CREATE POLICY "anyone_confirm_payment"
  ON payments FOR INSERT
  WITH CHECK (true);

CREATE POLICY "public_read_payments"
  ON payments FOR SELECT
  USING (true);

-- Game results: organiser writes; public reads
CREATE POLICY "public_read_game_results"
  ON game_results FOR SELECT
  USING (true);

CREATE POLICY "organiser_write_game_results"
  ON game_results FOR INSERT
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM bills WHERE bills.id = game_results.bill_id AND bills.organiser_id = auth.uid()
    )
  );
