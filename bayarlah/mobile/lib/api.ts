import Constants from 'expo-constants';
import { supabase } from './supabase';
import type { Bill, Participant, Payment, PaymentDetails } from '../types';

const API_URL = (Constants.expoConfig?.extra?.apiUrl as string) ?? 'http://localhost:8000';

async function authHeaders(): Promise<Record<string, string>> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  return token
    ? { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }
    : { 'Content-Type': 'application/json' };
}

async function req<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, options);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function createBill(payload: {
  title: string;
  total_amount: number;
  description?: string;
  due_date?: string;
  emoji_tag: string;
  game_mode: string;
  participants: { name: string; phone?: string }[];
  payment_details?: PaymentDetails;
}): Promise<Bill> {
  const headers = await authHeaders();
  return req('/api/bills', { method: 'POST', headers, body: JSON.stringify(payload) });
}

export async function getBill(billId: string): Promise<Bill> {
  return req(`/api/bills/${billId}`);
}

export async function listBills(): Promise<Bill[]> {
  const headers = await authHeaders();
  return req('/api/bills', { headers });
}

export async function confirmPayment(payload: {
  participant_id: string;
  bill_id: string;
  amount: number;
  method: string;
}): Promise<Payment> {
  return req('/api/payments/confirm', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function nudgeParticipant(
  participantId: string,
): Promise<{ nudged: boolean; whatsapp_link?: string }> {
  const headers = await authHeaders();
  return req(`/api/payments/nudge/${participantId}`, { method: 'POST', headers });
}

// ── Game ──────────────────────────────────────────────────────────────────────

export interface TanggaGenerateResponse {
  seed: string;
  rungs: { lane: number; y: number }[];
  n_lanes: number;
}

export async function generateTangga(payload: {
  bill_id: string;
  participant_ids: string[];
  outcome_labels: string[];
}): Promise<TanggaGenerateResponse> {
  const headers = await authHeaders();
  return req('/api/game/tangga/generate', {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
  });
}

export async function lockTangga(payload: {
  bill_id: string;
  result: Record<string, string>;
}): Promise<void> {
  const headers = await authHeaders();
  return req('/api/game/tangga/lock', {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
  });
}

export interface RouletteSpinResponse {
  seed: string;
  angular_velocity: number;
}

export async function spinRoulette(payload: {
  bill_id: string;
  participant_ids: string[];
  include_belanja_segment: boolean;
}): Promise<RouletteSpinResponse> {
  const headers = await authHeaders();
  return req('/api/game/roulette/spin', {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
  });
}

export async function lockRoulette(payload: {
  bill_id: string;
  winner_participant_id: string;
  outcome: string;
}): Promise<void> {
  const headers = await authHeaders();
  return req('/api/game/roulette/lock', {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
  });
}


// ── Payment QR Upload ─────────────────────────────────────────────────────────

export async function uploadPaymentQR(
  billId: string,
  imageUri: string,
): Promise<{ duitnow_qr_url: string }> {
  const headers = await authHeaders();
  // Remove Content-Type so fetch sets multipart/form-data with boundary
  delete headers['Content-Type'];

  const formData = new FormData();
  const filename = imageUri.split('/').pop() ?? 'qr.png';
  const ext = filename.split('.').pop()?.toLowerCase() ?? 'png';
  const mimeType = ext === 'jpg' || ext === 'jpeg' ? 'image/jpeg' : 'image/png';

  formData.append('file', {
    uri: imageUri,
    name: filename,
    type: mimeType,
  } as any);

  const res = await fetch(`${API_URL}/api/bills/${billId}/payment-qr`, {
    method: 'POST',
    headers,
    body: formData,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
