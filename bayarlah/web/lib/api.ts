import type { Bill } from '../types';

/**
 * Base URL of the Bayar.lah API.
 *
 * On the server (rendering the page) API_URL may point at a private/internal address;
 * in the browser only the public NEXT_PUBLIC_API_URL is available.
 */
export function apiBase(): string {
  const url =
    typeof window === 'undefined'
      ? (process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL)
      : process.env.NEXT_PUBLIC_API_URL;
  return (url ?? 'http://localhost:8000').replace(/\/$/, '');
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function failure(res: Response): Promise<ApiError> {
  const body = await res.json().catch(() => ({}));
  const detail = typeof body?.detail === 'string' ? body.detail : 'Something went wrong';
  return new ApiError(detail, res.status);
}

/** The sanitised, shareable view of a bill, or null if it does not exist. */
export async function fetchPublicBill(billId: string): Promise<Bill | null> {
  const res = await fetch(`${apiBase()}/api/public/bills/${encodeURIComponent(billId)}`, {
    cache: 'no-store',
  });
  if (res.status === 404 || res.status === 422) return null;
  if (!res.ok) throw await failure(res);
  return res.json();
}

/**
 * "I paid". The server decides the amount (what the participant owes), so none is
 * sent; it also rejects participants that are not on this bill.
 */
export async function confirmPayment(input: {
  billId: string;
  participantId: string;
  method: string;
}): Promise<void> {
  const res = await fetch(`${apiBase()}/api/payments/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      bill_id: input.billId,
      participant_id: input.participantId,
      method: input.method,
    }),
  });
  if (!res.ok) throw await failure(res);
}
