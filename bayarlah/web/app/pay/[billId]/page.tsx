import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { createClient } from '@supabase/supabase-js';
import PayClientPage from './PayClientPage';
import type { Bill } from '../../../types';

interface Props {
  params: Promise<{ billId: string }>;
}

async function fetchBill(billId: string): Promise<Bill | null> {
  const supabase = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );
  const { data } = await supabase
    .from('bills')
    .select('*, participants(*, payments(*))')
    .eq('id', billId)
    .single();
  return data ?? null;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { billId } = await params;
  const bill = await fetchBill(billId);
  if (!bill) return { title: 'Bill not found — Bayar.lah' };

  const collected = (bill.payments ?? []).reduce((s: number, p: any) => s + Number(p.amount), 0);
  const pct = Math.round((collected / bill.total_amount) * 100);

  return {
    title: `${bill.emoji_tag} ${bill.title} — Bayar.lah`,
    description: `RM ${bill.per_person?.toFixed(2)} per person · ${pct}% collected. Split duit, no awkward lah.`,
    openGraph: {
      title: `${bill.emoji_tag} ${bill.title}`,
      description: `RM ${bill.per_person?.toFixed(2)} each · Tap to confirm your payment.`,
      siteName: 'Bayar.lah',
      type: 'website',
    },
    twitter: {
      card: 'summary',
      title: `${bill.emoji_tag} ${bill.title} — Bayar.lah`,
      description: `RM ${bill.per_person?.toFixed(2)} per person`,
    },
  };
}

export default async function PayPage({ params }: Props) {
  const { billId } = await params;
  const bill = await fetchBill(billId);
  if (!bill) notFound();
  return <PayClientPage bill={bill} />;
}
