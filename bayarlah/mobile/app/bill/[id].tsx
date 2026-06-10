import { useEffect, useState, useCallback, useRef } from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
  Share,
  Linking,
  Alert,
  useColorScheme,
  RefreshControl,
  Animated,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { getBill, nudgeParticipant } from '../../lib/api';
import { useDashboardWS } from '../../hooks/useDashboardWS';
import { AnimatedProgressRing } from '../../components/AnimatedProgressRing';
import { Confetti } from '../../components/Confetti';
import { Colors, Spacing, Radius } from '../../constants/theme';
import type { Bill, Participant, Payment } from '../../types';

const WEB_BASE = process.env.EXPO_PUBLIC_WEB_URL ?? 'http://localhost:3000';

function Toast({ message, visible }: { message: string; visible: boolean }) {
  const opacity = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (visible) {
      Animated.sequence([
        Animated.timing(opacity, { toValue: 1, duration: 200, useNativeDriver: true }),
        Animated.delay(2200),
        Animated.timing(opacity, { toValue: 0, duration: 300, useNativeDriver: true }),
      ]).start();
    }
  }, [visible, message, opacity]);

  return (
    <Animated.View style={[toast.wrap, { opacity }]} pointerEvents="none">
      <Text style={toast.text}>{message}</Text>
    </Animated.View>
  );
}

const toast = StyleSheet.create({
  wrap: {
    position: 'absolute',
    bottom: 100,
    alignSelf: 'center',
    backgroundColor: Colors.forestGreen,
    borderRadius: Radius.chip,
    paddingHorizontal: 20,
    paddingVertical: 10,
    zIndex: 99,
    shadowColor: '#000',
    shadowOpacity: 0.2,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 4 },
    elevation: 8,
  },
  text: { color: '#fff', fontWeight: '700', fontSize: 14 },
});

export default function BillSummaryScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const scheme = useColorScheme();
  const isDark = scheme === 'dark';

  const [bill, setBill] = useState<Bill | null>(null);
  const [payments, setPayments] = useState<Payment[]>([]);
  const [loading, setLoading] = useState(true);
  const [toastMsg, setToastMsg] = useState('');
  const [toastVisible, setToastVisible] = useState(false);
  const [showConfetti, setShowConfetti] = useState(false);
  const allPaidRef = useRef(false);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const showToast = useCallback((msg: string) => {
    setToastMsg(msg);
    setToastVisible(false);
    // Force re-trigger
    setTimeout(() => setToastVisible(true), 10);
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToastVisible(false), 3000);
  }, []);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    try {
      const data = await getBill(id);
      setBill(data);
      setPayments(data.payments ?? []);
    } catch {
      Alert.alert('Error', 'Could not load bill.');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  // WebSocket real-time
  const handleInit = useCallback((data: Bill) => {
    setBill(data);
    setPayments(data.payments ?? []);
  }, []);

  const handlePaymentConfirmed = useCallback((payment: Payment, name: string) => {
    setPayments((prev) => {
      if (prev.some((p) => p.id === payment.id)) return prev;
      return [...prev, payment];
    });
    showToast(`✓ ${name} just paid! 🎉`);
  }, [showToast]);

  const { connected } = useDashboardWS({
    billId: id ?? '',
    onInit: handleInit,
    onPaymentConfirmed: handlePaymentConfirmed,
  });

  const textColor = isDark ? Colors.lightBg : Colors.darkBg;
  const cardBg = isDark ? Colors.gray700 : Colors.white;
  const subText = isDark ? Colors.gray300 : Colors.gray500;
  const bg = isDark ? Colors.darkBg : Colors.lightBg;
  const borderColor = isDark ? Colors.gray500 : Colors.gray300;

  const shareLink = () => {
    if (!bill) return;
    const url = `${WEB_BASE}/pay/${bill.id}`;
    Share.share({ message: `${bill.emoji_tag} ${bill.title} — bayar lah! ${url}`, url });
  };

  const handleNudge = async (participant: Participant) => {
    try {
      const res = await nudgeParticipant(participant.id);
      if (res.whatsapp_link) {
        await Linking.openURL(res.whatsapp_link);
      } else {
        showToast(`Nudged ${participant.name}!`);
      }
    } catch (e: any) {
      Alert.alert('Cooldown', e.message ?? 'Try again in 24h.');
    }
  };

  if (!bill) {
    return (
      <View style={[styles.container, { backgroundColor: bg }]}>
        <Text style={{ color: textColor, padding: Spacing.md }}>Loading...</Text>
      </View>
    );
  }

  const paidIds = new Set(payments.map((p) => p.participant_id));
  const collected = payments.reduce((s, p) => s + Number(p.amount), 0);
  const paidCount = paidIds.size;
  const totalCount = (bill.participants ?? []).length;
  const allPaid = totalCount > 0 && paidCount >= totalCount;
  const shareUrl = `${WEB_BASE}/pay/${bill.id}`;

  // Fire confetti exactly once when bill transitions to 100%
  useEffect(() => {
    if (allPaid && !allPaidRef.current) {
      allPaidRef.current = true;
      setShowConfetti(true);
      setTimeout(() => setShowConfetti(false), 3500);
    } else if (!allPaid) {
      allPaidRef.current = false;
    }
  }, [allPaid]);

  return (
    <View style={{ flex: 1, backgroundColor: bg }}>
      <ScrollView
        style={styles.container}
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={load} tintColor={Colors.brandRed} />}
      >
        {/* Connection indicator */}
        <View style={[styles.connRow, { backgroundColor: cardBg }]}>
          <View style={[styles.connDot, { backgroundColor: connected ? Colors.forestGreen : Colors.gray300 }]} />
          <Text style={[styles.connText, { color: subText }]}>
            {connected ? 'Live updates on' : 'Reconnecting...'}
          </Text>
        </View>

        {/* Bill header */}
        <View style={[styles.card, { backgroundColor: cardBg }]}>
          <Text style={styles.titleEmoji}>{bill.emoji_tag}</Text>
          <Text style={[styles.billTitle, { color: textColor }]}>{bill.title}</Text>
          {bill.description ? (
            <Text style={[styles.billDesc, { color: subText }]}>{bill.description}</Text>
          ) : null}
          <View style={styles.metaRow}>
            {bill.due_date ? (
              <Text style={[styles.metaChip, { color: Colors.turmericGold, borderColor: Colors.turmericGold }]}>
                Due {bill.due_date}
              </Text>
            ) : null}
            <Text style={[styles.metaChip, { color: subText, borderColor }]}>
              {bill.game_mode === 'equal' ? '⚖️ Equal split' : bill.game_mode === 'tangga' ? '🪜 Tangga' : '🎡 Pusing'}
            </Text>
          </View>
        </View>

        {/* Animated progress ring */}
        <AnimatedProgressRing collected={collected} total={bill.total_amount} />

        {/* All paid celebration */}
        {allPaid && (
          <View style={[styles.card, styles.celebCard]}>
            <Text style={styles.celebEmoji}>🎉</Text>
            <Text style={styles.celebText}>Everyone paid! Bayar dah!</Text>
          </View>
        )}

        {/* Share link */}
        <View style={[styles.card, { backgroundColor: cardBg }]}>
          <Text style={[styles.sectionTitle, { color: subText }]}>SHARE LINK</Text>
          <Text style={[styles.shareUrl, { color: Colors.brandRed }]} numberOfLines={1} ellipsizeMode="middle">
            {shareUrl}
          </Text>
          <TouchableOpacity style={styles.shareBtn} onPress={shareLink} activeOpacity={0.8}>
            <Text style={styles.shareBtnText}>Share to WhatsApp 📤</Text>
          </TouchableOpacity>
        </View>

        {/* Participants */}
        <View style={[styles.card, { backgroundColor: cardBg }]}>
          <View style={styles.sectionHeader}>
            <Text style={[styles.sectionTitle, { color: subText }]}>PARTICIPANTS</Text>
            <Text style={[styles.sectionCount, { color: subText }]}>{paidCount}/{totalCount} paid</Text>
          </View>

          {(bill.participants ?? []).map((p, idx) => {
            const paid = paidIds.has(p.id);
            const isLast = idx === (bill.participants ?? []).length - 1;
            return (
              <View
                key={p.id}
                style={[
                  styles.participantRow,
                  !isLast && { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: borderColor },
                ]}
              >
                <View style={[styles.statusDot, { backgroundColor: paid ? Colors.forestGreen : Colors.gray300 }]} />
                <View style={styles.participantInfo}>
                  <Text style={[styles.participantName, { color: textColor }]}>{p.name}</Text>
                  <Text style={[styles.participantAmt, { color: subText }]}>
                    RM {(p.amount_owed ?? bill.per_person).toFixed(2)}
                  </Text>
                </View>
                {paid ? (
                  <View style={styles.paidBadge}>
                    <Text style={styles.paidBadgeText}>✓ Paid</Text>
                  </View>
                ) : (
                  <TouchableOpacity
                    style={styles.nudgeBtn}
                    onPress={() => handleNudge(p)}
                    activeOpacity={0.75}
                  >
                    <Text style={styles.nudgeBtnText}>Nudge 📲</Text>
                  </TouchableOpacity>
                )}
              </View>
            );
          })}
        </View>

        {/* Game mode — play buttons */}
        {bill.game_mode === 'tangga' && (
          <View style={[styles.card, { backgroundColor: cardBg }]}>
            <Text style={[styles.sectionTitle, { color: subText }]}>GAME MODE</Text>
            <Text style={[styles.gameModeLabel, { color: Colors.brandRed }]}>🪜 Tangga (Ladder)</Text>
            <TouchableOpacity
              style={[styles.playBtn, { backgroundColor: Colors.brandRed }]}
              activeOpacity={0.8}
              onPress={() =>
                router.push({
                  pathname: '/tangga',
                  params: {
                    billId: bill.id,
                    participantIds: JSON.stringify((bill.participants ?? []).map((p) => p.id)),
                    participantNames: JSON.stringify((bill.participants ?? []).map((p) => p.name)),
                  },
                })
              }
            >
              <Text style={styles.playBtnText}>Play Tangga 🪜</Text>
            </TouchableOpacity>
          </View>
        )}

        {bill.game_mode === 'roulette' && (
          <View style={[styles.card, { backgroundColor: cardBg }]}>
            <Text style={[styles.sectionTitle, { color: subText }]}>GAME MODE</Text>
            <Text style={[styles.gameModeLabel, { color: Colors.brandRed }]}>🎡 Pusing (Roulette)</Text>
            <TouchableOpacity
              style={[styles.playBtn, { backgroundColor: Colors.brandRed }]}
              activeOpacity={0.8}
              onPress={() =>
                router.push({
                  pathname: '/roulette',
                  params: {
                    billId: bill.id,
                    participantIds: JSON.stringify((bill.participants ?? []).map((p) => p.id)),
                    participantNames: JSON.stringify((bill.participants ?? []).map((p) => p.name)),
                  },
                })
              }
            >
              <Text style={styles.playBtnText}>Play Pusing 🎡</Text>
            </TouchableOpacity>
          </View>
        )}

      </ScrollView>

      <Toast message={toastMsg} visible={toastVisible} />
      <Confetti visible={showConfetti} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  content: { padding: Spacing.md, gap: Spacing.md, paddingBottom: 80 },
  connRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    borderRadius: Radius.chip,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.xs + 2,
    alignSelf: 'flex-start',
  },
  connDot: { width: 7, height: 7, borderRadius: 4 },
  connText: { fontSize: 12 },
  card: {
    borderRadius: Radius.card,
    padding: Spacing.md,
    shadowColor: '#000',
    shadowOpacity: 0.06,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
  celebCard: {
    backgroundColor: Colors.forestGreen,
    alignItems: 'center',
    gap: Spacing.xs,
  },
  celebEmoji: { fontSize: 36 },
  celebText: { color: '#fff', fontWeight: '800', fontSize: 17 },
  titleEmoji: { fontSize: 42, textAlign: 'center', marginBottom: Spacing.xs },
  billTitle: { fontSize: 22, fontWeight: '800', textAlign: 'center' },
  billDesc: { fontSize: 14, textAlign: 'center', marginTop: Spacing.xs },
  metaRow: { flexDirection: 'row', justifyContent: 'center', gap: Spacing.sm, marginTop: Spacing.sm, flexWrap: 'wrap' },
  metaChip: { fontSize: 12, fontWeight: '600', borderWidth: 1, borderRadius: Radius.chip, paddingHorizontal: 10, paddingVertical: 3 },
  sectionHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: Spacing.sm },
  sectionTitle: { fontSize: 11, fontWeight: '700', letterSpacing: 1, textTransform: 'uppercase' },
  sectionCount: { fontSize: 12, fontWeight: '600' },
  shareUrl: { fontSize: 13, marginBottom: Spacing.sm },
  shareBtn: { backgroundColor: '#25D366', borderRadius: Radius.card, padding: Spacing.sm + 4, alignItems: 'center' },
  shareBtnText: { color: '#fff', fontWeight: '700', fontSize: 15 },
  participantRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: Spacing.sm, gap: Spacing.sm },
  statusDot: { width: 10, height: 10, borderRadius: 5, flexShrink: 0 },
  participantInfo: { flex: 1 },
  participantName: { fontSize: 15, fontWeight: '600' },
  participantAmt: { fontSize: 13, marginTop: 1 },
  paidBadge: { backgroundColor: Colors.forestGreen + '22', borderRadius: Radius.chip, paddingHorizontal: 10, paddingVertical: 4 },
  paidBadgeText: { color: Colors.forestGreen, fontWeight: '700', fontSize: 13 },
  nudgeBtn: { backgroundColor: Colors.turmericGold, borderRadius: Radius.chip, paddingHorizontal: 12, paddingVertical: 6 },
  nudgeBtnText: { color: '#fff', fontSize: 12, fontWeight: '700' },
  gameModeLabel: { fontSize: 16, fontWeight: '700', marginBottom: Spacing.sm },
  gameHint: { fontSize: 13 },
  playBtn: { borderRadius: Radius.card, padding: Spacing.md, alignItems: 'center', marginTop: Spacing.xs },
  playBtnText: { color: '#fff', fontSize: 15, fontWeight: '700' },
});
