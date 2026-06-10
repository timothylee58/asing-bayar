export interface Participant {
  id: string;
  bill_id: string;
  name: string;
  phone?: string;
  amount_owed: number;
  is_organiser: boolean;
  created_at: string;
}

export interface Payment {
  id: string;
  participant_id: string;
  bill_id: string;
  amount: number;
  method: 'duitnow' | 'tng' | 'bank' | 'cash';
  confirmed_at: string;
  status: string;
}

export interface Bill {
  id: string;
  organiser_id: string;
  title: string;
  description?: string;
  total_amount: number;
  per_person: number;
  due_date?: string;
  emoji_tag: string;
  status: 'active' | 'completed' | 'cancelled';
  game_mode: 'equal' | 'tangga' | 'roulette' | 'toss';
  created_at: string;
  share_url?: string;
  participants?: Participant[];
  payments?: Payment[];
}

export interface GameResult {
  id: string;
  bill_id: string;
  game_type: 'tangga' | 'roulette' | 'toss';
  seed?: string;
  result_json: Record<string, string>;
  played_at: string;
  is_locked: boolean;
}

export type PaymentMethod = 'duitnow' | 'tng' | 'bank' | 'cash';
