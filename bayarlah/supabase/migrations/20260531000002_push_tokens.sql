-- Push notification tokens
CREATE TABLE push_tokens (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  participant_id UUID REFERENCES participants(id) ON DELETE CASCADE,
  user_id        UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  token          TEXT NOT NULL,
  created_at     TIMESTAMPTZ DEFAULT NOW(),
  -- Either participant_id (member) or user_id (organiser), not both required
  CONSTRAINT push_tokens_has_owner CHECK (
    participant_id IS NOT NULL OR user_id IS NOT NULL
  )
);

-- One token per participant/user (upsert target)
CREATE UNIQUE INDEX push_tokens_participant_idx ON push_tokens(participant_id) WHERE participant_id IS NOT NULL;
CREATE UNIQUE INDEX push_tokens_user_idx ON push_tokens(user_id) WHERE user_id IS NOT NULL;

ALTER TABLE push_tokens ENABLE ROW LEVEL SECURITY;

-- Anyone can register their own token (no auth for member flow)
CREATE POLICY "anyone_register_push_token"
  ON push_tokens FOR INSERT
  WITH CHECK (true);

-- Owners can delete their token
CREATE POLICY "owner_delete_push_token"
  ON push_tokens FOR DELETE
  USING (
    auth.uid() = user_id OR participant_id IS NOT NULL
  );

-- Service role reads all (backend only, not exposed to frontend)
