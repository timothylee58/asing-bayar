-- Add payment_details JSONB column to bills table
-- Stores organiser-provided payment destination info (DuitNow ID, TnG phone, bank account, QR URL)
-- Level 1: Members see where to send money on the share page
-- Level 2 (future): Gateway references stored here too

ALTER TABLE bills
  ADD COLUMN payment_details jsonb DEFAULT '{}';

-- Add gateway_ref to payments for Level 2 webhook reconciliation
ALTER TABLE payments
  ADD COLUMN gateway_ref text,
  ADD COLUMN gateway_status text DEFAULT 'manual';

-- Index for webhook lookups by gateway reference
CREATE INDEX idx_payments_gateway_ref ON payments (gateway_ref) WHERE gateway_ref IS NOT NULL;

COMMENT ON COLUMN bills.payment_details IS 'Organiser payment destinations: duitnow_id, tng_phone, bank details, QR image URL';
COMMENT ON COLUMN payments.gateway_ref IS 'External payment gateway reference ID (e.g. HitPay payment request ID)';
COMMENT ON COLUMN payments.gateway_status IS 'Payment verification status: manual (honor system) | pending | verified | failed';
