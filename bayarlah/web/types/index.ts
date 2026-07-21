export interface Participant {
  id: string;
  bill_id: string;
  name: string;
  phone?: string;
  amount_owed: number;
  is_organiser: boolean;
}

export interface Payment {
  id: string;
  participant_id: string;
  bill_id: string;
  amount: number;
  method: string;
  confirmed_at: string;
  status: string;
  gateway_ref?: string;
  gateway_status?: string;
}

/** Organiser-provided payment destination details (Level 1). */
export interface PaymentDetails {
  duitnow_id?: string;
  duitnow_id_type?: 'phone' | 'nric' | 'business';
  duitnow_qr_url?: string;
  tng_phone?: string;
  bank_name?: string;
  bank_account?: string;
  bank_holder?: string;
}

export interface Bill {
  id: string;
  title: string;
  description?: string;
  total_amount: number;
  per_person: number;
  due_date?: string;
  emoji_tag: string;
  status: string;
  game_mode: string;
  created_at: string;
  participants?: Participant[];
  payments?: Payment[];
  payment_details?: PaymentDetails | null;
}
