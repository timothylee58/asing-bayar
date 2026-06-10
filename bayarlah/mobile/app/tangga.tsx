import { useState, useCallback, useEffect } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  ScrollView,
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
  type SharedValue,
} from 'react-native-reanimated';
import * as Haptics from 'expo-haptics';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { generateTangga, lockTangga } from '../lib/api';
import {
  generateLadder,
  computeAllPaths,
  type Rung,
  type ParticipantPath,
  type PathSegment,
} from '../lib/TanggaEngine';
import { Colors, Spacing, Radius } from '../constants/theme';

const { width: SCREEN_W } = Dimensions.get('window');
const LADDER_H = 420;
const DOT_SIZE = 16;
const LANE_TOP_PAD = 32;
const LANE_BOT_PAD = 48;
const EFFECTIVE_H = LADDER_H - LANE_TOP_PAD - LANE_BOT_PAD;

const SEGMENT_MS_PER_UNIT = 600; // ms per normalised vertical unit
const HORIZ_MS = 220;
const BETWEEN_PLAYER_MS = 400;

const DEFAULT_LABELS = ['Bayar Semua! 💸', 'Free! 🎉', 'Bayar Separuh 😅', 'Lucky Draw 🍀'];
const LOSER_LABEL = 'Bayar Semua! 💸';

// ── Helpers ───────────────────────────────────────────────────────────────────

function laneX(lane: number, nLanes: number, canvasW: number): number {
  return ((lane + 1) * canvasW) / (nLanes + 1);
}

function normY(y: number): number {
  return LANE_TOP_PAD + y * EFFECTIVE_H;
}

// ── Static ladder drawing (Views) ─────────────────────────────────────────────

function LadderCanvas({
  nLanes,
  rungs,
  labels,
  isDark,
  participantNames,
  selectedLane,
  onSelectLane,
  canSelectLane,
  revealedEndLanes,
}: {
  nLanes: number;
  rungs: Rung[];
  labels: string[];
  isDark: boolean;
  participantNames: string[];
  selectedLane: number | null;
  onSelectLane: (lane: number) => void;
  canSelectLane: boolean;
  revealedEndLanes: number[];
}) {
  const canvasW = SCREEN_W - Spacing.md * 2;
  const lineColor = isDark ? Colors.gray500 : Colors.gray300;
  const textColor = isDark ? Colors.lightBg : Colors.darkBg;

  return (
    <View style={[canvas.wrap, { width: canvasW, height: LADDER_H }]}>
      {/* Vertical lanes */}
      {Array.from({ length: nLanes }, (_, i) => (
        <View
          key={`lane-${i}`}
          style={[
            canvas.lane,
            {
              left: laneX(i, nLanes, canvasW) - 1,
              height: EFFECTIVE_H + LANE_TOP_PAD,
              top: 0,
              backgroundColor: lineColor,
            },
          ]}
        />
      ))}

      {/* Rungs */}
      {rungs.map((r, i) => {
        const x1 = laneX(r.lane, nLanes, canvasW);
        const x2 = laneX(r.lane + 1, nLanes, canvasW);
        return (
          <View
            key={`rung-${i}`}
            style={[
              canvas.rung,
              {
                left: x1,
                top: normY(r.y),
                width: x2 - x1,
                backgroundColor: lineColor,
              },
            ]}
          />
        );
      })}

      {/* Top lane selectors */}
      {canSelectLane &&
        Array.from({ length: nLanes }, (_, i) => (
          <TouchableOpacity
            key={`sel-${i}`}
            onPress={() => onSelectLane(i)}
            style={[
              canvas.lanePicker,
              {
                left: laneX(i, nLanes, canvasW) - 18,
                top: 2,
                backgroundColor:
                  selectedLane === i ? Colors.brandRed : isDark ? Colors.gray700 : Colors.white,
                borderColor:
                  selectedLane === i ? Colors.brandRed : lineColor,
              },
            ]}
          >
            <Text style={{ fontSize: 10, color: selectedLane === i ? '#fff' : textColor, fontWeight: '700' }}>
              {i + 1}
            </Text>
          </TouchableOpacity>
        ))}

      {/* Bottom outcome labels */}
      {labels.slice(0, nLanes).map((label, i) => {
        const isLoser = label === LOSER_LABEL;
        const isRevealed = revealedEndLanes.includes(i);
        return (
          <View
            key={`label-${i}`}
            style={[
              canvas.labelWrap,
              {
                left: laneX(i, nLanes, canvasW) - 30,
                bottom: 2,
                backgroundColor: isRevealed
                  ? isLoser ? Colors.brandRed : Colors.forestGreen
                  : isDark ? Colors.gray700 : Colors.gray100,
              },
            ]}
          >
            <Text style={{ fontSize: 9, color: isRevealed ? '#fff' : textColor, textAlign: 'center', fontWeight: '700' }} numberOfLines={2}>
              {isRevealed ? label : '?'}
            </Text>
          </View>
        );
      })}
    </View>
  );
}

const canvas = StyleSheet.create({
  wrap: { position: 'relative', overflow: 'hidden' },
  lane: { position: 'absolute', width: 2 },
  rung: { position: 'absolute', height: 2 },
  lanePicker: {
    position: 'absolute',
    width: 36,
    height: 36,
    borderRadius: 18,
    borderWidth: 2,
    alignItems: 'center',
    justifyContent: 'center',
  },
  labelWrap: {
    position: 'absolute',
    width: 60,
    borderRadius: 6,
    paddingHorizontal: 2,
    paddingVertical: 4,
  },
});

// ── Animated dot ──────────────────────────────────────────────────────────────

function PlayerDot({
  color,
  x,
  y,
}: {
  color: string;
  x: SharedValue<number>;
  y: SharedValue<number>;
}) {
  const style = useAnimatedStyle(() => ({
    transform: [
      { translateX: x.value - DOT_SIZE / 2 },
      { translateY: y.value - DOT_SIZE / 2 },
    ],
  }));
  return (
    <Animated.View
      style={[
        StyleSheet.absoluteFill,
        style,
        {
          width: DOT_SIZE,
          height: DOT_SIZE,
          borderRadius: DOT_SIZE / 2,
          backgroundColor: color,
          borderWidth: 2,
          borderColor: '#fff',
          shadowColor: color,
          shadowOpacity: 0.6,
          shadowRadius: 6,
          shadowOffset: { width: 0, height: 0 },
          elevation: 4,
        },
      ]}
    />
  );
}

// ── Dot colors per participant ────────────────────────────────────────────────

const DOT_COLORS = [
  Colors.brandRed,
  Colors.turmericGold,
  '#3B82F6',
  '#8B5CF6',
  '#EC4899',
  '#14B8A6',
];

// ── Main Screen ───────────────────────────────────────────────────────────────

type GamePhase = 'setup' | 'select' | 'playing' | 'done';

export default function TanggaScreen() {
  const { billId, participantIds: rawIds, participantNames: rawNames } = useLocalSearchParams<{
    billId: string;
    participantIds: string;
    participantNames: string;
  }>();
  const router = useRouter();
  const scheme = useColorScheme();
  const isDark = scheme === 'dark';

  const participantIds: string[] = rawIds ? JSON.parse(rawIds) : [];
  const participantNames: string[] = rawNames ? JSON.parse(rawNames) : [];
  const nLanes = participantIds.length;

  const labelCount = Math.min(nLanes, DEFAULT_LABELS.length);
  const outcomeLabels = [...DEFAULT_LABELS.slice(0, labelCount)];
  // Ensure exactly nLanes labels
  while (outcomeLabels.length < nLanes) outcomeLabels.push(`Bayar ${outcomeLabels.length + 1}`);

  const [phase, setPhase] = useState<GamePhase>('setup');
  const [rungs, setRungs] = useState<Rung[]>([]);
  const [seed, setSeed] = useState('');
  const [allPaths, setAllPaths] = useState<ParticipantPath[]>([]);
  // participantIndex → lane they picked (selection order)
  const [laneAssignment, setLaneAssignment] = useState<Record<number, number>>({});
  const [revealedEndLanes, setRevealedEndLanes] = useState<number[]>([]);
  const [results, setResults] = useState<{ name: string; label: string }[]>([]);
  const [loading, setLoading] = useState(false);

  const textColor = isDark ? Colors.lightBg : Colors.darkBg;
  const cardBg = isDark ? Colors.gray700 : Colors.white;
  const subText = isDark ? Colors.gray300 : Colors.gray500;
  const bg = isDark ? Colors.darkBg : Colors.lightBg;

  // One shared value pair per participant
  const dotXValues = Array.from({ length: nLanes }, () => useSharedValue(0));
  const dotYValues = Array.from({ length: nLanes }, () => useSharedValue(0));

  const canvasW = SCREEN_W - Spacing.md * 2;

  // ── Generate ladder ─────────────────────────────────────────────────────────

  const handleGenerate = useCallback(async () => {
    if (nLanes < 2) {
      Alert.alert('Need at least 2 participants for Tangga.');
      return;
    }
    setLoading(true);
    try {
      const res = await generateTangga({
        bill_id: billId,
        participant_ids: participantIds,
        outcome_labels: outcomeLabels,
      });
      const ladder = generateLadder(res.n_lanes, res.seed);
      const paths = computeAllPaths(res.n_lanes, ladder.rungs);
      setRungs(ladder.rungs);
      setSeed(res.seed);
      setAllPaths(paths);

      // Initialise dot positions at top of each lane
      paths.forEach((_, i) => {
        const x = laneX(i, nLanes, canvasW);
        dotXValues[i].value = x;
        dotYValues[i].value = LANE_TOP_PAD;
      });

      setPhase('select');
    } catch (e: any) {
      Alert.alert('Error', e.message ?? 'Failed to generate ladder.');
    } finally {
      setLoading(false);
    }
  }, [billId, nLanes, participantIds, outcomeLabels, canvasW]);

  // ── Lane selection ──────────────────────────────────────────────────────────

  const assignedLanes = Object.values(laneAssignment);
  const nextToAssign = Object.keys(laneAssignment).length; // index of next participant

  const handleSelectLane = useCallback((lane: number) => {
    if (assignedLanes.includes(lane)) return;
    if (nextToAssign >= nLanes) return;
    setLaneAssignment((prev) => ({ ...prev, [nextToAssign]: lane }));
  }, [assignedLanes, nextToAssign, nLanes]);

  const allSelected = Object.keys(laneAssignment).length === nLanes;

  // ── Animation ───────────────────────────────────────────────────────────────

  const animateParticipant = useCallback((
    participantIdx: number,
    startLane: number,
    onDone: () => void,
  ) => {
    const path = allPaths[startLane];
    if (!path) { onDone(); return; }

    const xSV = dotXValues[participantIdx];
    const ySV = dotYValues[participantIdx];

    // Start position
    xSV.value = laneX(startLane, nLanes, canvasW);
    ySV.value = LANE_TOP_PAD;

    const timings: { x: number; y: number; duration: number }[] = [];

    for (const seg of path.segments) {
      if (seg.type === 'vertical') {
        const dist = seg.toY - seg.fromY;
        timings.push({
          x: laneX(seg.toLane, nLanes, canvasW),
          y: normY(seg.toY),
          duration: Math.max(150, SEGMENT_MS_PER_UNIT * dist),
        });
      } else {
        timings.push({
          x: laneX(seg.toLane, nLanes, canvasW),
          y: normY(seg.fromY),
          duration: HORIZ_MS,
        });
      }
    }

    function runStep(idx: number) {
      if (idx >= timings.length) {
        runOnJS(onDone)();
        return;
      }
      const { x, y, duration } = timings[idx];
      const easing = Easing.inOut(Easing.ease);
      xSV.value = withTiming(x, { duration, easing });
      ySV.value = withTiming(y, { duration, easing }, (finished) => {
        if (finished) runStep(idx + 1);
      });
    }

    runStep(0);
  }, [allPaths, dotXValues, dotYValues, nLanes, canvasW]);

  const handlePlay = useCallback(async () => {
    setPhase('playing');
    const revealed: number[] = [];
    const resultList: { name: string; label: string }[] = [];

    function playNext(participantIdx: number) {
      if (participantIdx >= nLanes) {
        // All done — lock results
        const resultMap: Record<string, string> = {};
        resultList.forEach(({ name, label }, i) => {
          resultMap[participantIds[i]] = label;
        });
        lockTangga({ bill_id: billId, result: resultMap }).catch(() => {});
        setResults(resultList);
        setRevealedEndLanes([...revealed]);
        setPhase('done');

        const loser = resultList.find((r) => r.label === LOSER_LABEL);
        if (loser) {
          setTimeout(() => {
            Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
          }, 300);
        }
        return;
      }

      const startLane = laneAssignment[participantIdx];
      animateParticipant(participantIdx, startLane, () => {
        const endLane = allPaths[startLane]?.endLane ?? startLane;
        const label = outcomeLabels[endLane] ?? '?';
        revealed.push(endLane);
        resultList.push({ name: participantNames[participantIdx], label });
        setRevealedEndLanes([...revealed]);
        Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
        setTimeout(() => playNext(participantIdx + 1), BETWEEN_PLAYER_MS);
      });
    }

    playNext(0);
  }, [nLanes, laneAssignment, animateParticipant, allPaths, outcomeLabels, participantIds, participantNames, billId]);

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <ScrollView
      style={[styles.container, { backgroundColor: bg }]}
      contentContainerStyle={styles.content}
      scrollEnabled={phase !== 'playing'}
    >
      {/* Header */}
      <View style={[styles.card, { backgroundColor: cardBg }]}>
        <Text style={[styles.title, { color: textColor }]}>🪜 Tangga</Text>
        <Text style={[styles.subtitle, { color: subText }]}>
          {phase === 'setup' && 'Generate the ladder to begin'}
          {phase === 'select' && `${participantNames[nextToAssign] ?? 'Everyone'} — pick a lane`}
          {phase === 'playing' && 'Watch the paths reveal...'}
          {phase === 'done' && 'Fates decided! 🎲'}
        </Text>
      </View>

      {/* Ladder canvas + dots */}
      {phase !== 'setup' && (
        <View style={[styles.ladderWrap, { backgroundColor: cardBg }]}>
          {/* Participant name chips at top */}
          <View style={[styles.nameRow, { width: canvasW }]}>
            {participantNames.map((name, i) => {
              const lane = laneAssignment[i];
              return (
                <View
                  key={i}
                  style={[
                    styles.nameChip,
                    {
                      backgroundColor:
                        lane !== undefined
                          ? DOT_COLORS[i % DOT_COLORS.length] + '33'
                          : isDark ? Colors.gray700 : Colors.gray100,
                      borderColor:
                        lane !== undefined ? DOT_COLORS[i % DOT_COLORS.length] : 'transparent',
                    },
                  ]}
                >
                  <Text style={{ fontSize: 10, color: textColor, fontWeight: '600' }} numberOfLines={1}>
                    {name}
                  </Text>
                </View>
              );
            })}
          </View>

          {/* Ladder */}
          <View style={{ width: canvasW }}>
            <LadderCanvas
              nLanes={nLanes}
              rungs={rungs}
              labels={outcomeLabels}
              isDark={isDark}
              participantNames={participantNames}
              selectedLane={
                nextToAssign < nLanes ? laneAssignment[nextToAssign] ?? null : null
              }
              onSelectLane={handleSelectLane}
              canSelectLane={phase === 'select'}
              revealedEndLanes={revealedEndLanes}
            />

            {/* Animated dots — rendered over canvas */}
            {phase !== 'select' && (
              <View style={StyleSheet.absoluteFill} pointerEvents="none">
                {participantNames.map((_, i) => (
                  <PlayerDot
                    key={i}
                    color={DOT_COLORS[i % DOT_COLORS.length]}
                    x={dotXValues[i]}
                    y={dotYValues[i]}
                  />
                ))}
              </View>
            )}
          </View>
        </View>
      )}

      {/* Results */}
      {phase === 'done' && results.length > 0 && (
        <View style={[styles.card, { backgroundColor: cardBg }]}>
          <Text style={[styles.sectionTitle, { color: subText }]}>RESULTS</Text>
          {results.map(({ name, label }, i) => {
            const isLoser = label === LOSER_LABEL;
            return (
              <View
                key={i}
                style={[
                  styles.resultRow,
                  { borderBottomColor: isDark ? Colors.gray500 : Colors.gray300 },
                  i < results.length - 1 && styles.resultBorder,
                ]}
              >
                <View
                  style={[
                    styles.resultDot,
                    { backgroundColor: DOT_COLORS[i % DOT_COLORS.length] },
                  ]}
                />
                <Text style={[styles.resultName, { color: textColor }]}>{name}</Text>
                <Text
                  style={[
                    styles.resultLabel,
                    { color: isLoser ? Colors.brandRed : Colors.forestGreen },
                  ]}
                >
                  {label}
                </Text>
              </View>
            );
          })}

          {results.some((r) => r.label === LOSER_LABEL) && (
            <View style={styles.kenaWrap}>
              <Text style={styles.kenaText}>
                Kena kau lah! 🔥{' '}
                {results.find((r) => r.label === LOSER_LABEL)?.name}
              </Text>
            </View>
          )}
        </View>
      )}

      {/* CTA buttons */}
      <View style={styles.btnRow}>
        {phase === 'setup' && (
          <TouchableOpacity
            style={[styles.btn, { backgroundColor: Colors.brandRed }, loading && styles.btnDisabled]}
            onPress={handleGenerate}
            disabled={loading}
            activeOpacity={0.8}
          >
            <Text style={styles.btnText}>{loading ? 'Generating...' : 'Generate Ladder 🪜'}</Text>
          </TouchableOpacity>
        )}

        {phase === 'select' && (
          <TouchableOpacity
            style={[styles.btn, { backgroundColor: Colors.brandRed }, !allSelected && styles.btnDisabled]}
            onPress={handlePlay}
            disabled={!allSelected}
            activeOpacity={0.8}
          >
            <Text style={styles.btnText}>
              {allSelected ? 'Play! 🎲' : `${nLanes - Object.keys(laneAssignment).length} more to pick`}
            </Text>
          </TouchableOpacity>
        )}

        {phase === 'done' && (
          <TouchableOpacity
            style={[styles.btn, { backgroundColor: Colors.gray500 }]}
            onPress={() => router.back()}
            activeOpacity={0.8}
          >
            <Text style={styles.btnText}>Back to Bill</Text>
          </TouchableOpacity>
        )}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  content: { padding: Spacing.md, gap: Spacing.md, paddingBottom: 60 },
  card: {
    borderRadius: Radius.card,
    padding: Spacing.md,
    shadowColor: '#000',
    shadowOpacity: 0.06,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
  title: { fontSize: 24, fontWeight: '800', textAlign: 'center' },
  subtitle: { fontSize: 14, textAlign: 'center', marginTop: 4 },
  ladderWrap: {
    borderRadius: Radius.card,
    padding: Spacing.md,
    alignItems: 'center',
    gap: Spacing.sm,
    shadowColor: '#000',
    shadowOpacity: 0.06,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
  nameRow: { flexDirection: 'row', justifyContent: 'space-around', gap: 4 },
  nameChip: {
    flex: 1,
    borderWidth: 1.5,
    borderRadius: Radius.chip,
    paddingHorizontal: 6,
    paddingVertical: 4,
    alignItems: 'center',
  },
  sectionTitle: {
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 1,
    textTransform: 'uppercase',
    marginBottom: Spacing.sm,
  },
  resultRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: Spacing.sm, gap: Spacing.sm },
  resultBorder: { borderBottomWidth: StyleSheet.hairlineWidth },
  resultDot: { width: 10, height: 10, borderRadius: 5 },
  resultName: { flex: 1, fontSize: 15, fontWeight: '600' },
  resultLabel: { fontSize: 13, fontWeight: '700' },
  kenaWrap: {
    backgroundColor: Colors.brandRed,
    borderRadius: Radius.card,
    padding: Spacing.md,
    alignItems: 'center',
    marginTop: Spacing.md,
  },
  kenaText: { color: '#fff', fontWeight: '800', fontSize: 18 },
  btnRow: { gap: Spacing.sm },
  btn: {
    borderRadius: Radius.button,
    padding: Spacing.md + 2,
    alignItems: 'center',
  },
  btnDisabled: { opacity: 0.45 },
  btnText: { color: '#fff', fontSize: 17, fontWeight: '700' },
});
