import { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  Alert,
  useColorScheme,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { createBill } from '../lib/api';
import { Colors, Spacing, Radius, EMOJI_TAGS } from '../constants/theme';
import type { PaymentDetails } from '../types';

interface ParticipantField {
  name: string;
  phone: string;
}

const DUITNOW_ID_TYPES = [
  { key: 'phone', label: 'Phone' },
  { key: 'nric', label: 'NRIC' },
  { key: 'business', label: 'Business' },
] as const;

const BANKS = [
  'Maybank', 'CIMB', 'Public Bank', 'RHB', 'Hong Leong',
  'AmBank', 'Bank Islam', 'Bank Rakyat', 'OCBC', 'UOB',
  'Standard Chartered', 'HSBC', 'Other',
] as const;

export default function CreateBillScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ amount?: string; emoji?: string; ref?: string }>();
  const scheme = useColorScheme();
  const isDark = scheme === 'dark';

  // Cross-link pre-fill from Bajet Buddy deep-link
  const prefillAmount = params.amount && !isNaN(parseFloat(params.amount)) ? params.amount : '';
  const prefillEmoji = params.emoji || '🍽️';

  const [title, setTitle] = useState('');
  const [amount, setAmount] = useState(prefillAmount);
  const [description, setDescription] = useState('');
  const [emoji, setEmoji] = useState(prefillEmoji);
  const [gameMode, setGameMode] = useState<'equal' | 'tangga' | 'roulette'>('equal');
  const [participants, setParticipants] = useState<ParticipantField[]>([{ name: '', phone: '' }]);
  const [loading, setLoading] = useState(false);

  // Payment details (Level 1)
  const [showPaymentDetails, setShowPaymentDetails] = useState(false);
  const [duitnowId, setDuitnowId] = useState('');
  const [duitnowIdType, setDuitnowIdType] = useState<'phone' | 'nric' | 'business'>('phone');
  const [tngPhone, setTngPhone] = useState('');
  const [bankName, setBankName] = useState('');
  const [bankAccount, setBankAccount] = useState('');
  const [bankHolder, setBankHolder] = useState('');

  const textColor = isDark ? Colors.lightBg : Colors.darkBg;
  const cardBg = isDark ? Colors.gray700 : Colors.white;
  const inputBg = isDark ? Colors.gray700 : Colors.gray100;
  const borderColor = isDark ? Colors.gray500 : Colors.gray300;
  const subText = isDark ? Colors.gray300 : Colors.gray500;
  const bg = isDark ? Colors.darkBg : Colors.lightBg;

  const addParticipant = () =>
    setParticipants((p) => [...p, { name: '', phone: '' }]);

  const updateParticipant = (i: number, field: keyof ParticipantField, val: string) =>
    setParticipants((p) => p.map((x, idx) => (idx === i ? { ...x, [field]: val } : x)));

  const removeParticipant = (i: number) =>
    setParticipants((p) => p.filter((_, idx) => idx !== i));

  const perPerson = () => {
    const n = parseFloat(amount);
    const count = participants.filter((p) => p.name.trim()).length;
    if (!n || !count) return '—';
    return `RM ${(n / count).toFixed(2)}`;
  };

  const buildPaymentDetails = (): PaymentDetails | undefined => {
    const details: PaymentDetails = {};
    if (duitnowId.trim()) {
      details.duitnow_id = duitnowId.trim();
      details.duitnow_id_type = duitnowIdType;
    }
    if (tngPhone.trim()) details.tng_phone = tngPhone.trim();
    if (bankAccount.trim()) {
      details.bank_account = bankAccount.trim();
      if (bankName.trim()) details.bank_name = bankName.trim();
      if (bankHolder.trim()) details.bank_holder = bankHolder.trim();
    }
    // Return undefined if empty (don't send null object)
    return Object.keys(details).length > 0 ? details : undefined;
  };

  const handleSubmit = async () => {
    if (!title.trim()) return Alert.alert('Missing', 'Enter a bill title.');
    if (!amount || isNaN(parseFloat(amount))) return Alert.alert('Missing', 'Enter a valid amount.');
    const validParticipants = participants.filter((p) => p.name.trim());
    if (!validParticipants.length) return Alert.alert('Missing', 'Add at least one participant.');

    setLoading(true);
    try {
      const bill = await createBill({
        title: title.trim(),
        total_amount: parseFloat(amount),
        description: description.trim() || undefined,
        emoji_tag: emoji,
        game_mode: gameMode,
        participants: validParticipants.map((p) => ({ name: p.name.trim(), phone: p.phone.trim() || undefined })),
        payment_details: buildPaymentDetails(),
      });
      router.replace(`/bill/${bill.id}`);
    } catch (e: any) {
      Alert.alert('Error', e.message ?? 'Failed to create bill.');
    } finally {
      setLoading(false);
    }
  };

  const inputStyle = [styles.input, { backgroundColor: inputBg, color: textColor, borderColor }];

  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView style={[styles.container, { backgroundColor: bg }]} contentContainerStyle={styles.content}>

        {/* Cross-link badge */}
        {params.ref === 'bajet-buddy' && (
          <View style={[styles.crossLinkBadge, { backgroundColor: Colors.forestGreen + '15' }]}>
            <Text style={[styles.crossLinkText, { color: Colors.forestGreen }]}>
              📱 Linked from Bajet Buddy
            </Text>
          </View>
        )}

        {/* Emoji picker */}
        <Text style={[styles.label, { color: subText }]}>Tag</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.emojiRow}>
          {EMOJI_TAGS.map((e) => (
            <TouchableOpacity
              key={e}
              style={[styles.emojiChip, { borderColor, backgroundColor: emoji === e ? Colors.brandRed : inputBg }]}
              onPress={() => setEmoji(e)}
            >
              <Text style={styles.emojiChipText}>{e}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>

        <Text style={[styles.label, { color: subText }]}>Bill Title</Text>
        <TextInput
          style={inputStyle}
          value={title}
          onChangeText={setTitle}
          placeholder="e.g. Dinner at PappaRich"
          placeholderTextColor={Colors.gray500}
        />

        <Text style={[styles.label, { color: subText }]}>Total Amount (RM)</Text>
        <TextInput
          style={inputStyle}
          value={amount}
          onChangeText={setAmount}
          placeholder="0.00"
          placeholderTextColor={Colors.gray500}
          keyboardType="decimal-pad"
        />

        <Text style={[styles.label, { color: subText }]}>Description (optional)</Text>
        <TextInput
          style={[inputStyle, styles.multiline]}
          value={description}
          onChangeText={setDescription}
          placeholder="What's this for?"
          placeholderTextColor={Colors.gray500}
          multiline
          numberOfLines={3}
        />

        {/* Game mode */}
        <Text style={[styles.label, { color: subText }]}>Split Mode</Text>
        <View style={styles.modeRow}>
          {(['equal', 'tangga', 'roulette'] as const).map((m) => (
            <TouchableOpacity
              key={m}
              style={[styles.modeChip, { borderColor, backgroundColor: gameMode === m ? Colors.brandRed : inputBg }]}
              onPress={() => setGameMode(m)}
            >
              <Text style={[styles.modeLabel, { color: gameMode === m ? '#fff' : textColor }]}>
                {m === 'equal' ? '⚖️ Equal' : m === 'tangga' ? '🪜 Tangga' : '🎡 Pusing'}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Participants */}
        <View style={styles.participantHeader}>
          <Text style={[styles.label, { color: subText }]}>Participants</Text>
          <Text style={[styles.perPerson, { color: Colors.forestGreen }]}>{perPerson()} each</Text>
        </View>

        {participants.map((p, i) => (
          <View key={i} style={styles.participantRow}>
            <TextInput
              style={[inputStyle, styles.participantName]}
              value={p.name}
              onChangeText={(v) => updateParticipant(i, 'name', v)}
              placeholder={`Name ${i + 1}`}
              placeholderTextColor={Colors.gray500}
            />
            <TextInput
              style={[inputStyle, styles.participantPhone]}
              value={p.phone}
              onChangeText={(v) => updateParticipant(i, 'phone', v)}
              placeholder="60123456789"
              placeholderTextColor={Colors.gray500}
              keyboardType="phone-pad"
            />
            {participants.length > 1 && (
              <TouchableOpacity onPress={() => removeParticipant(i)} style={styles.removeBtn}>
                <Text style={styles.removeBtnText}>✕</Text>
              </TouchableOpacity>
            )}
          </View>
        ))}

        <TouchableOpacity style={[styles.addBtn, { borderColor }]} onPress={addParticipant}>
          <Text style={[styles.addBtnText, { color: Colors.brandRed }]}>+ Add participant</Text>
        </TouchableOpacity>

        {/* ── Payment Details (Level 1) ──────────────────────────────────── */}
        <TouchableOpacity
          style={[styles.sectionToggle, { borderColor }]}
          onPress={() => setShowPaymentDetails((v) => !v)}
        >
          <Text style={[styles.sectionToggleText, { color: textColor }]}>
            {showPaymentDetails ? '▾' : '▸'} Payment Details (optional)
          </Text>
          <Text style={[styles.sectionToggleHint, { color: subText }]}>
            Help members know where to send money
          </Text>
        </TouchableOpacity>

        {showPaymentDetails && (
          <View style={[styles.paymentDetailsSection, { backgroundColor: cardBg, borderColor }]}>

            {/* DuitNow */}
            <Text style={[styles.subLabel, { color: Colors.turmericGold }]}>🇲🇾 DuitNow</Text>
            <View style={styles.idTypeRow}>
              {DUITNOW_ID_TYPES.map((t) => (
                <TouchableOpacity
                  key={t.key}
                  style={[
                    styles.idTypeChip,
                    { borderColor, backgroundColor: duitnowIdType === t.key ? Colors.brandRed : inputBg },
                  ]}
                  onPress={() => setDuitnowIdType(t.key)}
                >
                  <Text style={{ color: duitnowIdType === t.key ? '#fff' : textColor, fontSize: 12, fontWeight: '600' }}>
                    {t.label}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
            <TextInput
              style={inputStyle}
              value={duitnowId}
              onChangeText={setDuitnowId}
              placeholder={duitnowIdType === 'phone' ? '60123456789' : duitnowIdType === 'nric' ? '990101-14-1234' : 'Registration no.'}
              placeholderTextColor={Colors.gray500}
              keyboardType={duitnowIdType === 'phone' ? 'phone-pad' : 'default'}
            />

            {/* Touch 'n Go */}
            <Text style={[styles.subLabel, { color: Colors.turmericGold, marginTop: Spacing.md }]}>💳 Touch &apos;n Go</Text>
            <TextInput
              style={inputStyle}
              value={tngPhone}
              onChangeText={setTngPhone}
              placeholder="TnG linked phone (60123456789)"
              placeholderTextColor={Colors.gray500}
              keyboardType="phone-pad"
            />

            {/* Bank Transfer */}
            <Text style={[styles.subLabel, { color: Colors.turmericGold, marginTop: Spacing.md }]}>🏦 Bank Transfer</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.bankRow}>
              {BANKS.map((b) => (
                <TouchableOpacity
                  key={b}
                  style={[
                    styles.bankChip,
                    { borderColor, backgroundColor: bankName === b ? Colors.brandRed : inputBg },
                  ]}
                  onPress={() => setBankName(b)}
                >
                  <Text style={{ color: bankName === b ? '#fff' : textColor, fontSize: 11, fontWeight: '600' }}>
                    {b}
                  </Text>
                </TouchableOpacity>
              ))}
            </ScrollView>
            <TextInput
              style={inputStyle}
              value={bankAccount}
              onChangeText={setBankAccount}
              placeholder="Account number"
              placeholderTextColor={Colors.gray500}
              keyboardType="number-pad"
            />
            <TextInput
              style={[inputStyle, { marginTop: Spacing.xs }]}
              value={bankHolder}
              onChangeText={setBankHolder}
              placeholder="Account holder name"
              placeholderTextColor={Colors.gray500}
            />
          </View>
        )}

        <TouchableOpacity
          style={[styles.submitBtn, loading && styles.submitDisabled]}
          onPress={handleSubmit}
          disabled={loading}
        >
          <Text style={styles.submitText}>{loading ? 'Creating...' : 'Create Bill 💸'}</Text>
        </TouchableOpacity>

      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  content: { padding: Spacing.md, gap: Spacing.sm, paddingBottom: 60 },
  label: { fontSize: 12, fontWeight: '600', textTransform: 'uppercase', letterSpacing: 0.8, marginTop: Spacing.sm },
  input: { borderRadius: Radius.card, padding: Spacing.md, fontSize: 15, borderWidth: 1 },
  multiline: { height: 80, textAlignVertical: 'top' },
  emojiRow: { flexDirection: 'row', marginBottom: Spacing.xs },
  emojiChip: { borderWidth: 1.5, borderRadius: Radius.chip, padding: Spacing.sm, marginRight: Spacing.xs },
  emojiChipText: { fontSize: 22 },
  modeRow: { flexDirection: 'row', gap: Spacing.sm },
  modeChip: { flex: 1, borderWidth: 1.5, borderRadius: Radius.card, padding: Spacing.sm, alignItems: 'center' },
  modeLabel: { fontSize: 13, fontWeight: '600' },
  participantHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: Spacing.sm },
  perPerson: { fontSize: 14, fontWeight: '700' },
  participantRow: { flexDirection: 'row', gap: Spacing.xs, alignItems: 'center' },
  participantName: { flex: 1 },
  participantPhone: { flex: 1 },
  removeBtn: { padding: Spacing.xs },
  removeBtnText: { color: Colors.error, fontSize: 16 },
  addBtn: { borderWidth: 1.5, borderStyle: 'dashed', borderRadius: Radius.card, padding: Spacing.md, alignItems: 'center' },
  addBtnText: { fontSize: 14, fontWeight: '600' },
  // Payment details section
  sectionToggle: { marginTop: Spacing.lg, padding: Spacing.md, borderWidth: 1, borderRadius: Radius.card },
  sectionToggleText: { fontSize: 14, fontWeight: '700' },
  sectionToggleHint: { fontSize: 12, marginTop: 2 },
  paymentDetailsSection: { padding: Spacing.md, borderWidth: 1, borderTopWidth: 0, borderBottomLeftRadius: Radius.card, borderBottomRightRadius: Radius.card },
  subLabel: { fontSize: 13, fontWeight: '700', marginBottom: Spacing.xs },
  idTypeRow: { flexDirection: 'row', gap: Spacing.xs, marginBottom: Spacing.xs },
  idTypeChip: { paddingHorizontal: Spacing.sm + 4, paddingVertical: Spacing.xs + 2, borderRadius: Radius.chip, borderWidth: 1 },
  bankRow: { flexDirection: 'row', marginBottom: Spacing.xs },
  bankChip: { paddingHorizontal: Spacing.sm + 2, paddingVertical: Spacing.xs + 2, borderRadius: Radius.chip, borderWidth: 1, marginRight: Spacing.xs },
  crossLinkBadge: { borderRadius: Radius.card, padding: Spacing.sm + 2, marginBottom: Spacing.sm, alignItems: 'center' },
  crossLinkText: { fontSize: 13, fontWeight: '600' },
  // Submit
  submitBtn: { backgroundColor: Colors.brandRed, borderRadius: Radius.button, padding: Spacing.md + 4, alignItems: 'center', marginTop: Spacing.md },
  submitDisabled: { opacity: 0.6 },
  submitText: { color: '#fff', fontSize: 17, fontWeight: '700' },
});
