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
import { useRouter } from 'expo-router';
import { createBill } from '../lib/api';
import { Colors, Spacing, Radius, EMOJI_TAGS } from '../constants/theme';

interface ParticipantField {
  name: string;
  phone: string;
}

export default function CreateBillScreen() {
  const router = useRouter();
  const scheme = useColorScheme();
  const isDark = scheme === 'dark';

  const [title, setTitle] = useState('');
  const [amount, setAmount] = useState('');
  const [description, setDescription] = useState('');
  const [emoji, setEmoji] = useState('🍽️');
  const [gameMode, setGameMode] = useState<'equal' | 'tangga' | 'roulette'>('equal');
  const [participants, setParticipants] = useState<ParticipantField[]>([{ name: '', phone: '' }]);
  const [loading, setLoading] = useState(false);

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
  submitBtn: { backgroundColor: Colors.brandRed, borderRadius: Radius.button, padding: Spacing.md + 4, alignItems: 'center', marginTop: Spacing.md },
  submitDisabled: { opacity: 0.6 },
  submitText: { color: '#fff', fontSize: 17, fontWeight: '700' },
});
