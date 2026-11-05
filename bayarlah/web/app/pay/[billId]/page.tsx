import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { fetchPublicBill } from '../../../lib/api';
import PayClientPage from './PayClientPage';

interface Props {
  params: Promise<{ billId: string }>;
}

// Never serve a cached bill: payment state changes by the minute.
export const dynamic = 'force-dynamic';

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { billId } = await params;
  const bill = await fetchPublicBill(billId).catch(() => null);
  if (!bill) return { title: 'Bill not found — Bayar.lah' };

  const pct = bill.total_amount > 0 ? Math.round((bill.collected / bill.total_amount) * 100) : 0;
  const share = bill.per_person != null ? `RM ${bill.per_person.toFixed(2)} per person` : 'See your share';

  return {
    title: `${bill.emoji_tag} ${bill.title} — Bayar.lah`,
    description: `${share} · ${pct}% collected. Split duit, no awkward lah.`,
    openGraph: {
      title: `${bill.emoji_tag} ${bill.title}`,
      description: `${share} · Tap to confirm your payment.`,
      siteName: 'Bayar.lah',
      type: 'website',
    },
    twitter: {
      card: 'summary',
      title: `${bill.emoji_tag} ${bill.title} — Bayar.lah`,
      description: share,
    },
  };
}

export default async function PayPage({ params }: Props) {
  const { billId } = await params;
  const bill = await fetchPublicBill(billId);
  if (!bill) notFound();
  return <PayClientPage bill={bill} />;
}
