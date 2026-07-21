'use client';

import { useState, useEffect } from 'react';
import { createClient } from '@supabase/supabase-js';
import type { Bill, Participant, Payment, PaymentDetails } from '../../../types';

function useRealtimePayments(billId: string, initial: Payment[]) {
  const [payments, setPayments] = useState<Payment[]>(initial);

  useEffect(() => {
    const supabase = createClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
    );

    const channel = supabase
      .channel(`payments:bill:${billId}`)
      .on(
        'postgres_changes',
        { event: 'INSERT', schema: 'public', table: 'payments', filter: `bill_id=eq.${billId}` },
        (payload) => {
          setPayments((prev) => {
            if (prev.some((p) => p.id === payload.new.id)) return prev;
            return [...prev, payload.new as Payment];
          });
        }
      )
      .subscribe();

    return () => { supabase.removeChannel(channel); };
  }, [billId]);

  return payments;
}

const PAYMENT_METHODS = [
  { key: 'duitnow', label: 'DuitNow QR', emoji: '🇲🇾' },
  { key: 'tng', label: "Touch 'n Go", emoji: '💳' },
  { key: 'bank', label: 'Bank Transfer', emoji: '🏦' },
  { key: 'cash', label: 'Cash', emoji: '💵' },
] as const;

function ProgressBar({ collected, total }: { collected: number; total: number }) {
  const pct = total > 0 ? Math.min((collected / total) * 100, 100) : 0;
  return (
    <div className="my-4">
      <div className="flex justify-between text-sm text-stone-500 mb-1">
        <span>RM {collected.toFixed(2)} collected</span>
        <span>{Math.round(pct)}%</span>
      </div>
      <div className="h-3 rounded-full bg-stone-200 overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, backgroundColor: '#1D9E75' }}
        />
      </div>
      <div className="text-right text-sm text-stone-500 mt-1">
        RM {total.toFixed(2)} total
      </div>
    </div>
  );
}

// ── Payment Details Display (Level 1) ─────────────────────────────────────────

function PaymentInstructions({
  method,
  details,
  amount,
}: {
  method: string;
  details: PaymentDetails | null | undefined;
  amount: number;
}) {
  if (!details) return null;

  if (method === 'duitnow') {
    const hasInfo = details.duitnow_id || details.duitnow_qr_url;
    if (!hasInfo) return null;
    return (
      <div className="rounded-xl p-4 mb-4" style={{ backgroundColor: '#FEF9F0', border: '1px solid #F5E6D3' }}>
        <p className="text-xs font-bold text-stone-500 uppercase tracking-widest mb-2">
          Pay via DuitNow
        </p>
        {details.duitnow_qr_url && (
          <div className="flex justify-center mb-3">
            <img
              src={details.duitnow_qr_url}
              alt="DuitNow QR Code"
              className="w-48 h-48 rounded-lg border border-stone-200"
            />
          </div>
        )}
        {details.duitnow_id && (
          <div className="text-center">
            <p className="text-sm text-stone-600">
              {details.duitnow_id_type === 'phone' ? 'Phone' :
               details.duitnow_id_type === 'nric' ? 'NRIC' : 'ID'}:{' '}
              <span className="font-bold text-stone-900 font-mono">{details.duitnow_id}</span>
            </p>
          </div>
        )}
        <p className="text-center text-xs text-stone-500 mt-2">
          Transfer <strong>RM {amount.toFixed(2)}</strong> then confirm below
        </p>
      </div>
    );
  }

  if (method === 'tng') {
    if (!details.tng_phone) return null;
    return (
      <div className="rounded-xl p-4 mb-4" style={{ backgroundColor: '#F0F7FE', border: '1px solid #D3E6F5' }}>
        <p className="text-xs font-bold text-stone-500 uppercase tracking-widest mb-2">
          Pay via Touch &apos;n Go
        </p>
        <div className="text-center">
          <p className="text-sm text-stone-600">
            Send to:{' '}
            <span className="font-bold text-stone-900 font-mono">{details.tng_phone}</span>
          </p>
          <p className="text-xs text-stone-500 mt-2">
            Transfer <strong>RM {amount.toFixed(2)}</strong> via TnG eWallet, then confirm below
          </p>
        </div>
      </div>
    );
  }

  if (method === 'bank') {
    if (!details.bank_account) return null;
    return (
      <div className="rounded-xl p-4 mb-4" style={{ backgroundColor: '#F0FEF5', border: '1px solid #D3F5E0' }}>
        <p className="text-xs font-bold text-stone-500 uppercase tracking-widest mb-2">
          Bank Transfer Details
        </p>
        <div className="space-y-1">
          {details.bank_name && (
            <p className="text-sm text-stone-600">
              Bank: <span className="font-bold text-stone-900">{details.bank_name}</span>
            </p>
          )}
          <p className="text-sm text-stone-600">
            Account: <span className="font-bold text-stone-900 font-mono">{details.bank_account}</span>
          </p>
          {details.bank_holder && (
            <p className="text-sm text-stone-600">
              Name: <span className="font-bold text-stone-900">{details.bank_holder}</span>
            </p>
          )}
        </div>
        <p className="text-xs text-stone-500 mt-2">
          Transfer <strong>RM {amount.toFixed(2)}</strong> then confirm below
        </p>
      </div>
    );
  }

  if (method === 'cash') {
    return (
      <div className="rounded-xl p-4 mb-4" style={{ backgroundColor: '#FEFEF0', border: '1px solid #F5F3D3' }}>
        <p className="text-xs font-bold text-stone-500 uppercase tracking-widest mb-2">
          Cash Payment
        </p>
        <p className="text-sm text-stone-600 text-center">
          Hand <strong>RM {amount.toFixed(2)}</strong> to the organiser in person, then confirm below.
        </p>
      </div>
    );
  }

  return null;
}

// ── Main Component ────────────────────────────────────────────────────────────

interface Props {
  bill: Bill;
}

type Step = 'select' | 'method' | 'done';

export default function PayClientPage({ bill }: Props) {
  const payments = useRealtimePayments(bill.id, bill.payments ?? []);
  const paidIds = new Set(payments.map((p) => p.participant_id));
  const collected = payments.reduce((s, p) => s + Number(p.amount), 0);

  const unpaidParticipants = (bill.participants ?? []).filter((p: Participant) => !paidIds.has(p.id));

  const [step, setStep] = useState<Step>('select');
  const [selected, setSelected] = useState<Participant | null>(null);
  const [method, setMethod] = useState<string>('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string>('');

  const paymentAmount = selected ? (selected.amount_owed ?? bill.per_person) : bill.per_person;

  const handleConfirm = async () => {
    if (!selected || !method) return;
    setSubmitting(true);
    setError('');
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
      const res = await fetch(`${apiUrl}/api/payments/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          participant_id: selected.id,
          bill_id: bill.id,
          amount: selected.amount_owed ?? bill.per_person,
          method,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail ?? 'Failed to confirm payment');
      }
      setStep('done');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen" style={{ backgroundColor: '#FAFAF8' }}>
      <div className="max-w-md mx-auto px-4 py-8">

        {/* Header */}
        <div className="text-center mb-6">
          <div className="text-5xl mb-2">{bill.emoji_tag}</div>
          <h1 className="text-2xl font-bold text-stone-900">{bill.title}</h1>
          {bill.description && (
            <p className="text-stone-500 text-sm mt-1">{bill.description}</p>
          )}
          {bill.due_date && (
            <p className="text-sm mt-2 font-semibold" style={{ color: '#BA7517' }}>
              Due {bill.due_date}
            </p>
          )}
        </div>

        {/* Progress */}
        <ProgressBar collected={collected} total={bill.total_amount} />

        {/* Per person */}
        <div className="rounded-xl p-4 mb-6 text-center" style={{ backgroundColor: '#fff' }}>
          <p className="text-stone-500 text-sm">Per person</p>
          <p className="text-3xl font-extrabold" style={{ color: '#C8410A' }}>
            RM {bill.per_person?.toFixed(2)}
          </p>
        </div>

        {/* Step: select participant */}
        {step === 'select' && (
          <div>
            <h2 className="text-sm font-bold text-stone-500 uppercase tracking-widest mb-3">
              Who are you?
            </h2>
            {unpaidParticipants.length === 0 ? (
              <div className="rounded-xl p-6 text-center" style={{ backgroundColor: '#fff' }}>
                <div className="text-4xl mb-2">🎉</div>
                <p className="font-bold text-stone-900">All paid up!</p>
                <p className="text-stone-500 text-sm mt-1">Everyone has confirmed their payment.</p>
              </div>
            ) : (
              <div className="flex flex-col gap-2">
                {unpaidParticipants.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => { setSelected(p); setStep('method'); }}
                    className="flex items-center justify-between rounded-xl px-4 py-3 font-semibold text-stone-900 transition-all"
                    style={{ backgroundColor: '#fff', border: '1.5px solid #E7E5E4' }}
                  >
                    <span>{p.name}</span>
                    <span className="text-sm font-bold" style={{ color: '#C8410A' }}>
                      RM {(p.amount_owed ?? bill.per_person).toFixed(2)}
                    </span>
                  </button>
                ))}
              </div>
            )}

            {/* Already paid list */}
            {paidIds.size > 0 && (
              <div className="mt-4">
                <p className="text-xs text-stone-400 uppercase tracking-widest mb-2">Already paid</p>
                {(bill.participants ?? [])
                  .filter((p) => paidIds.has(p.id))
                  .map((p) => (
                    <div key={p.id} className="flex items-center gap-2 py-2 text-sm text-stone-400">
                      <span style={{ color: '#1D9E75' }}>✓</span>
                      <span>{p.name}</span>
                    </div>
                  ))}
              </div>
            )}
          </div>
        )}

        {/* Step: choose payment method + show payment details */}
        {step === 'method' && selected && (
          <div>
            <button
              onClick={() => { setStep('select'); setSelected(null); setMethod(''); }}
              className="text-sm text-stone-500 mb-4 flex items-center gap-1"
            >
              ← Back
            </button>
            <h2 className="text-sm font-bold text-stone-500 uppercase tracking-widest mb-3">
              How did {selected.name} pay?
            </h2>
            <div className="flex flex-col gap-2 mb-4">
              {PAYMENT_METHODS.map((m) => (
                <button
                  key={m.key}
                  onClick={() => setMethod(m.key)}
                  className="flex items-center gap-3 rounded-xl px-4 py-3 font-semibold transition-all"
                  style={{
                    backgroundColor: method === m.key ? '#C8410A' : '#fff',
                    color: method === m.key ? '#fff' : '#1C1917',
                    border: `1.5px solid ${method === m.key ? '#C8410A' : '#E7E5E4'}`,
                  }}
                >
                  <span className="text-xl">{m.emoji}</span>
                  <span>{m.label}</span>
                </button>
              ))}
            </div>

            {/* Level 1: Show organiser payment details for the selected method */}
            {method && (
              <PaymentInstructions
                method={method}
                details={bill.payment_details}
                amount={paymentAmount}
              />
            )}

            {error && (
              <p className="text-red-600 text-sm mb-3">{error}</p>
            )}

            <button
              onClick={handleConfirm}
              disabled={!method || submitting}
              className="w-full rounded-xl py-4 font-bold text-white text-lg transition-all disabled:opacity-50"
              style={{ backgroundColor: '#C8410A' }}
            >
              {submitting ? 'Confirming...' : `Confirm RM ${paymentAmount.toFixed(2)} 💸`}
            </button>
          </div>
        )}

        {/* Step: done */}
        {step === 'done' && selected && (
          <div className="rounded-xl p-8 text-center" style={{ backgroundColor: '#fff' }}>
            <div className="text-5xl mb-3">🎉</div>
            <h2 className="text-xl font-extrabold text-stone-900">Dah bayar!</h2>
            <p className="text-stone-500 mt-2">
              {selected.name}, your payment of{' '}
              <strong>RM {paymentAmount.toFixed(2)}</strong> is confirmed.
            </p>
            <p className="text-xs text-stone-400 mt-4">
              The organiser will be notified. Terima kasih! 🙏
            </p>
          </div>
        )}

        {/* Footer */}
        <p className="text-center text-xs text-stone-400 mt-8">
          Bayar.lah · Split duit, no awkward lah.
        </p>
      </div>
    </div>
  );
}
