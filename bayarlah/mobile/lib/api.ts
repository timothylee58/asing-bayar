import { API_URL } from './config';
import { supabase } from './supabase';
import type { Bill, PaymentDetails } from '../types';

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

/** FastAPI errors are `{detail: string}` or, for validation, `{detail: [{msg, loc}]}`. */
async function errorMessage(res: Response): Promise<string> {
  const body = await res.json().catch(() => null);
  const detail = body?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0];
    const field = Array.isArray(first?.loc) ? first.loc.filter((p: unknown) => p !== 'body').join('.') : '';
    return field ? `${field}: ${first.msg}` : String(first?.msg ?? 'Invalid request');
  }
  return res.status === 401 ? 'Please sign in again.' : `Request failed (${res.status})`;
}

async function authHeaders(json = true): Promise<Record<string, string>> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  return {
    ...(json ? { 'Content-Type': 'application/json' } : {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

async function req<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, options);
  if (!res.ok) throw new ApiError(await errorMessage(res), res.status);
  return res.json();
}

async function authed<T>(path: string, init: RequestInit = {}): Promise<T> {
  return req<T>(path, { ...init, headers: await authHeaders() });
}

// ── Bills ─────────────────────────────────────────────────────────────────────

export function createBill(payload: {
  title: string;
  total_amount: number;
  description?: string;
  due_date?: string;
  emoji_tag: string;
  game_mode: string;
  participants: { name: string; phone?: string }[];
  payment_details?: PaymentDetails;
}): Promise<Bill> {
  return authed('/api/bills', { method: 'POST', body: JSON.stringify(payload) });
}

/** The organiser's full view of one of their bills (the API checks ownership). */
export function getBill(billId: string): Promise<Bill> {
  return authed(`/api/bills/${billId}`);
}

export function listBills(): Promise<Bill[]> {
  return authed('/api/bills');
}

export function nudgeParticipant(
  participantId: string,
): Promise<{ nudged: boolean; whatsapp_link?: string | null }> {
  return authed(`/api/payments/nudge/${participantId}`, { method: 'POST' });
}

// ── Game (the server decides every outcome) ───────────────────────────────────

export interface TanggaGenerateResponse {
  seed: string;
  rungs: { lane: number; y: number }[];
  n_lanes: number;
}

export function generateTangga(payload: {
  bill_id: string;
  participant_ids: string[];
  outcome_labels: string[];
}): Promise<TanggaGenerateResponse> {
  return authed('/api/game/tangga/generate', { method: 'POST', body: JSON.stringify(payload) });
}

export interface GameResultRow {
  id: string;
  result_json: Record<string, string>;
}

/** Players pick lanes; the server derives who gets which outcome from its own ladder. */
export function lockTangga(payload: {
  bill_id: string;
  lanes: Record<string, number>; // participant id -> lane
}): Promise<GameResultRow> {
  return authed('/api/game/tangga/lock', { method: 'POST', body: JSON.stringify(payload) });
}

export interface RouletteSpinResponse {
  seed: string;
  angular_velocity: number;
  /** Chosen by the server when the spin starts; the wheel animates to land on it. */
  winner_participant_id: string;
  /** Where inside the winning slice (0..1) the pointer should come to rest. */
  landing_fraction: number;
}

export function spinRoulette(payload: {
  bill_id: string;
  participant_ids: string[];
}): Promise<RouletteSpinResponse> {
  return authed('/api/game/roulette/spin', { method: 'POST', body: JSON.stringify(payload) });
}

export function lockRoulette(payload: {
  bill_id: string;
  winner_participant_id: string;
  outcome: string;
}): Promise<GameResultRow> {
  return authed('/api/game/roulette/lock', { method: 'POST', body: JSON.stringify(payload) });
}

// ── Payment QR upload ─────────────────────────────────────────────────────────

export async function uploadPaymentQR(
  billId: string,
  imageUri: string,
): Promise<{ duitnow_qr_url: string }> {
  // No Content-Type: fetch must set multipart/form-data with its own boundary.
  const headers = await authHeaders(false);

  const formData = new FormData();
  const filename = imageUri.split('/').pop() ?? 'qr.png';
  const ext = filename.split('.').pop()?.toLowerCase() ?? 'png';
  const mimeType = ext === 'jpg' || ext === 'jpeg' ? 'image/jpeg' : 'image/png';

  formData.append('file', {
    uri: imageUri,
    name: filename,
    type: mimeType,
  } as unknown as Blob);

  const res = await fetch(`${API_URL}/api/bills/${billId}/payment-qr`, {
    method: 'POST',
    headers,
    body: formData,
  });
  if (!res.ok) throw new ApiError(await errorMessage(res), res.status);
  return res.json();
}

// ── Push notifications (organiser device) ─────────────────────────────────────

export function registerPushToken(token: string): Promise<{ registered: boolean }> {
  return authed('/api/notifications/register', { method: 'POST', body: JSON.stringify({ token }) });
}

export function unregisterPushToken(): Promise<{ unregistered: boolean }> {
  return authed('/api/notifications/unregister', { method: 'DELETE' });
}
