// Mirrors the server's PublicBillResponse (GET /api/public/bills/{id}): everything a
// member needs to pay and nothing more - in particular no participant phone numbers.

export interface Participant {
  id: string;
  name: string;
  amount_owed: number | null;
}

/** A *settled* payment (confirmed by the member or verified by the gateway). */
export interface Payment {
  id: string;
  participant_id: string;
  amount: number;
  method: string;
  confirmed_at?: string | null;
}

/** Organiser-provided payment destination details (Level 1). */
export interface PaymentDetails {
  duitnow_id?: string | null;
  duitnow_id_type?: 'phone' | 'nric' | 'business' | null;
  duitnow_qr_url?: string | null;
  tng_phone?: string | null;
  bank_name?: string | null;
  bank_account?: string | null;
  bank_holder?: string | null;
}

export interface Bill {
  id: string;
  title: string;
  description?: string | null;
  total_amount: number;
  per_person: number | null; // null for custom splits: use each participant's amount_owed
  due_date?: string | null;
  emoji_tag: string;
  status: string;
  game_mode: string;
  receipt_url?: string | null;
  payment_details?: PaymentDetails | null;
  participants: Participant[];
  payments: Payment[];
  collected: number;
}
