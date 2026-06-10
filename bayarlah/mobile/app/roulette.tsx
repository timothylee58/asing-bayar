import { useState, useCallback, useRef } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Dimensions,
  Alert,
  useColorScheme,
} from 'react-native';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withTiming,
  runOnJS,
  Easing,
} from 'react-native-reanimated';
import { Svg, Path, Text as SvgText, Circle, Polygon } from 'react-native-svg';
import * as Haptics from 'expo-haptics';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { spinRoulette, lockRoulette } from '../lib/api';
import {
  buildSegments,
  resolveSpinResult,
  slicePath,
  sliceLabelPos,
  type WheelSegment,
} from '../lib/RouletteEngine';
import { Confetti } from '../components/Confetti';
import { Colors, Spacing, Radius } from '../constants/theme';

const { width: SCREEN_W } = Dimensions.get('window');
const WHEEL_SIZE = Math.min(SCREEN_W - Spacing.md * 4, 320);
const WHEEL_R = WHEEL_SIZE / 2;
const CX = WHEEL_R;
const CY = WHEEL_R;
const LOSER_LABEL = 'Bayar Semua! 💸';

type Phase = 'ready' | 'spinning' | 'done';

// ── Wheel SVG ─────────────────────────────────────────────────────────────────

function WheelSvg({ segments }: { segments: WheelSegment[] }) {
  return (
    <Svg width={WHEEL_SIZE} height={WHEEL_SIZE}>
      {/* Outer border */}
      <Circle cx={CX} cy={CY} r={WHEEL_R - 1} stroke={Colors.gray300} strokeWidth={2} fill="none" />

      {segments.map((seg, i) => {
        const d = slicePath(CX, CY, WHEEL_R - 2, seg.startAngleDeg, seg.endAngleDeg);
        const label = sliceLabelPos(CX, CY, WHEEL_R, seg.startAngleDeg, seg.endAngleDeg);
        const truncated = seg.name.length > 8 ? seg.name.slice(0, 7) + '…' : seg.name;
        return (
          <Path key={`seg-${i}`} d={d} fill={seg.color} stroke="#fff" strokeWidth={1.5} />
        );
      })}

      {/* Labels rendered after slices so they're on top */}
      {segments.map((seg, i) => {
        const label = sliceLabelPos(CX, CY, WHEEL_R, seg.startAngleDeg, seg.endAngleDeg);
        const truncated = seg.name.length > 9 ? seg.name.slice(0, 8) + '…' : seg.name;
        return (
          <SvgText
            key={`lbl-${i}`}
            x={label.x}
            y={label.y}
            fontSize={Math.max(9, Math.min(13, 130 / segments.length))}
            fontWeight="700"
            fill="#fff"
            textAnchor="middle"
            alignmentBaseline="middle"
            rotation={label.rotation}
            origin={`${label.x}, ${label.y}`}
          >
            {truncated}
          </SvgText>
        );
      })}

      {/* Center hub */}
      <Circle cx={CX} cy={CY} r={18} fill={Colors.darkBg} stroke="#fff" strokeWidth={2} />
    </Svg>
  );
}

// ── Pointer (triangle at top) ─────────────────────────────────────────────────

function Pointer() {
  return (
    <View style={pointer.wrap} pointerEvents="none">
      <Svg width={28} height={32}>
        <Polygon
          points="14,28 2,2 26,2"
          fill={Colors.brandRed}
          stroke="#fff"
          strokeWidth={2}
          strokeLinejoin="round"
        />
      </Svg>
    </View>
  );
}

const pointer = StyleSheet.create({
  wrap: {
    position: 'absolute',
    top: -12,
    alignSelf: 'center',
    zIndex: 10,
  },
});

// ── Main Screen ───────────────────────────────────────────────────────────────

export default function RouletteScreen() {
  const {
    billId,
    participantIds: rawIds,
    participantNames: rawNames,
  } = useLocalSearchParams<{
    billId: string;
    participantIds: string;
    participantNames: string;
  }>();
  const router = useRouter();
  const scheme = useColorScheme();
  const isDark = scheme === 'dark';

  const participantIds: string[] = rawIds ? JSON.parse(rawIds) : [];
  const participantNames: string[] = rawNames ? JSON.parse(rawNames) : [];

  const participants = participantIds.map((id, i) => ({
    id,
    name: participantNames[i] ?? `P${i + 1}`,
  }));

  const segments = buildSegments(participants);

  const [phase, setPhase] = useState<Phase>('ready');
  const [winner, setWinner] = useState<{ name: string; id: string } | null>(null);
  const [showConfetti, setShowConfetti] = useState(false);
  const [loading, setLoading] = useState(false);

  const rotation = useSharedValue(0);

  const textColor = isDark ? Colors.lightBg : Colors.darkBg;
  const cardBg = isDark ? Colors.gray700 : Colors.white;
  const subText = isDark ? Colors.gray300 : Colors.gray500;
  const bg = isDark ? Colors.darkBg : Colors.lightBg;

  const wheelStyle = useAnimatedStyle(() => ({
    transform: [{ rotate: `${rotation.value}deg` }],
  }));

  const handleReveal = useCallback((winnerIdx: number) => {
    const seg = segments[winnerIdx];
    if (!seg) return;
    const isLoser = seg.name === LOSER_LABEL || true; // all spins are valid reveals
    setWinner({ name: seg.name, id: seg.participantId });
    setPhase('done');

    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    setShowConfetti(true);
    setTimeout(() => setShowConfetti(false), 3500);

    lockRoulette({
      bill_id: billId,
      winner_participant_id: seg.participantId,
      outcome: LOSER_LABEL,
    }).catch(() => {});
  }, [segments, billId]);

  const handleSpin = useCallback(async () => {
    if (phase !== 'ready') return;
    setLoading(true);
    try {
      const res = await spinRoulette({
        bill_id: billId,
        participant_ids: participantIds,
        include_belanja_segment: true,
      });

      const result = resolveSpinResult(segments, res.angular_velocity, rotation.value);
      setPhase('spinning');

      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);

      rotation.value = withTiming(
        result.totalRotationDeg,
        {
          duration: result.durationMs,
          easing: Easing.bezier(0.17, 0.67, 0.12, 0.99),
        },
        (finished) => {
          if (finished) runOnJS(handleReveal)(result.winnerIndex);
        },
      );
    } catch (e: any) {
      Alert.alert('Error', e.message ?? 'Failed to spin.');
      setPhase('ready');
    } finally {
      setLoading(false);
    }
  }, [phase, billId, participantIds, segments, rotation, handleReveal]);

  const isLoser = winner
    ? participantNames.includes(winner.name) &&
      segments.find((s) => s.participantId === winner.id) !== undefined
    : false;

  return (
    <View style={[styles.container, { backgroundColor: bg }]}>

      {/* Header */}
      <View style={[styles.header, { backgroundColor: cardBg }]}>
        <Text style={[styles.title, { color: textColor }]}>🎡 Pusing</Text>
        <Text style={[styles.subtitle, { color: subText }]}>
          {phase === 'ready' && 'Tap Spin to decide fate'}
          {phase === 'spinning' && 'Spinning... 🙏'}
          {phase === 'done' && 'Fate decided! 🎲'}
        </Text>
      </View>

      {/* Wheel */}
      <View style={styles.wheelContainer}>
        <Pointer />
        <Animated.View style={[styles.wheelWrap, wheelStyle]}>
          <WheelSvg segments={segments} />
        </Animated.View>
      </View>

      {/* Result card */}
      {phase === 'done' && winner && (
        <View style={[styles.resultCard, { backgroundColor: Colors.brandRed }]}>
          <Text style={styles.kenakau}>Kena kau lah! 🔥</Text>
          <Text style={styles.winnerName}>{winner.name}</Text>
          <Text style={styles.winnerOutcome}>{LOSER_LABEL}</Text>
        </View>
      )}

      {/* Participant legend */}
      <View style={[styles.legend, { backgroundColor: cardBg }]}>
        {segments.map((seg, i) => (
          <View key={i} style={styles.legendRow}>
            <View style={[styles.legendDot, { backgroundColor: seg.color }]} />
            <Text style={[styles.legendName, { color: textColor }]} numberOfLines={1}>
              {seg.name}
            </Text>
            {winner?.id === seg.participantId && (
              <Text style={{ color: Colors.brandRed, fontWeight: '800', fontSize: 13 }}>← Kena!</Text>
            )}
          </View>
        ))}
      </View>

      {/* CTA */}
      <View style={styles.btnRow}>
        {phase === 'ready' && (
          <TouchableOpacity
            style={[styles.btn, { backgroundColor: Colors.brandRed }, loading && styles.btnDisabled]}
            onPress={handleSpin}
            disabled={loading || phase !== 'ready'}
            activeOpacity={0.8}
          >
            <Text style={styles.btnText}>{loading ? 'Getting seed...' : 'SPIN! 🎡'}</Text>
          </TouchableOpacity>
        )}

        {phase === 'spinning' && (
          <View style={[styles.btn, { backgroundColor: Colors.gray500 }]}>
            <Text style={styles.btnText}>Spinning...</Text>
          </View>
        )}

        {phase === 'done' && (
          <TouchableOpacity
            style={[styles.btn, { backgroundColor: Colors.gray700 }]}
            onPress={() => router.back()}
            activeOpacity={0.8}
          >
            <Text style={styles.btnText}>Back to Bill</Text>
          </TouchableOpacity>
        )}
      </View>

      {/* Confetti overlay */}
      {showConfetti && <Confetti visible={showConfetti} />}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: Spacing.md, gap: Spacing.md },
  header: {
    borderRadius: Radius.card,
    padding: Spacing.md,
    alignItems: 'center',
    shadowColor: '#000',
    shadowOpacity: 0.06,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
  title: { fontSize: 24, fontWeight: '800' },
  subtitle: { fontSize: 14, marginTop: 4 },
  wheelContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingTop: 16,
    position: 'relative',
  },
  wheelWrap: {
    shadowColor: '#000',
    shadowOpacity: 0.15,
    shadowRadius: 16,
    shadowOffset: { width: 0, height: 6 },
    elevation: 8,
  },
  resultCard: {
    borderRadius: Radius.card,
    padding: Spacing.md,
    alignItems: 'center',
    gap: 4,
  },
  kenakau: { color: '#fff', fontSize: 20, fontWeight: '800' },
  winnerName: { color: '#fff', fontSize: 28, fontWeight: '900' },
  winnerOutcome: { color: 'rgba(255,255,255,0.8)', fontSize: 14, marginTop: 2 },
  legend: {
    borderRadius: Radius.card,
    padding: Spacing.md,
    gap: Spacing.xs,
    shadowColor: '#000',
    shadowOpacity: 0.06,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
  legendRow: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm },
  legendDot: { width: 12, height: 12, borderRadius: 6, flexShrink: 0 },
  legendName: { flex: 1, fontSize: 14, fontWeight: '600' },
  btnRow: {},
  btn: { borderRadius: Radius.button, padding: Spacing.md + 2, alignItems: 'center' },
  btnDisabled: { opacity: 0.45 },
  btnText: { color: '#fff', fontSize: 17, fontWeight: '700' },
});
