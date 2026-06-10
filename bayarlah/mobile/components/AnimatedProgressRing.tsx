import { useEffect, useRef } from 'react';
import { Animated, View, Text, StyleSheet } from 'react-native';
import { Colors } from '../constants/theme';

interface Props {
  collected: number;
  total: number;
  size?: number;
  strokeWidth?: number;
}

export function AnimatedProgressRing({
  collected,
  total,
  size = 140,
  strokeWidth = 10,
}: Props) {
  const pct = total > 0 ? Math.min(collected / total, 1) : 0;
  const displayPct = Math.round(pct * 100);

  // Animate a scale pop when pct changes
  const scaleAnim = useRef(new Animated.Value(1)).current;
  const prevPct = useRef(pct);

  useEffect(() => {
    if (pct !== prevPct.current) {
      prevPct.current = pct;
      Animated.sequence([
        Animated.spring(scaleAnim, { toValue: 1.08, useNativeDriver: true, speed: 20 }),
        Animated.spring(scaleAnim, { toValue: 1, useNativeDriver: true, speed: 20 }),
      ]).start();
    }
  }, [pct, scaleAnim]);

  const ringColor = pct >= 1 ? Colors.forestGreen : pct > 0.5 ? Colors.turmericGold : Colors.brandRed;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  // We fake the arc using border — SVG not available without extra lib
  // Use a bordered View approach: two half-circle approach
  const borderColors = buildRingColors(pct, ringColor);

  return (
    <Animated.View style={[styles.wrap, { transform: [{ scale: scaleAnim }] }]}>
      <View
        style={[
          styles.ring,
          {
            width: size,
            height: size,
            borderRadius: size / 2,
            borderWidth: strokeWidth,
            borderTopColor: borderColors[0],
            borderRightColor: borderColors[1],
            borderBottomColor: borderColors[2],
            borderLeftColor: borderColors[3],
            transform: [{ rotate: '-45deg' }],
          },
        ]}
      >
        <View style={[styles.inner, { transform: [{ rotate: '45deg' }] }]}>
          <Text style={[styles.pct, { color: ringColor }]}>{displayPct}%</Text>
          <Text style={styles.label}>collected</Text>
        </View>
      </View>
      <Text style={styles.amounts}>
        RM {collected.toFixed(2)} / RM {total.toFixed(2)}
      </Text>
    </Animated.View>
  );
}

/**
 * Approximates a CSS conic-gradient using 4 border sides.
 * Each quarter (0–25%, 25–50%, 50–75%, 75–100%) lights up one border side.
 */
function buildRingColors(pct: number, active: string): [string, string, string, string] {
  const track = Colors.gray300;
  if (pct <= 0) return [track, track, track, track];
  if (pct <= 0.25) return [active, track, track, track];
  if (pct <= 0.5) return [active, active, track, track];
  if (pct <= 0.75) return [active, active, active, track];
  return [active, active, active, active];
}

const styles = StyleSheet.create({
  wrap: { alignItems: 'center', marginVertical: 24, gap: 12 },
  ring: { alignItems: 'center', justifyContent: 'center' },
  inner: { alignItems: 'center' },
  pct: { fontSize: 30, fontWeight: '800' },
  label: { fontSize: 11, color: Colors.gray500, marginTop: -2 },
  amounts: { fontSize: 13, color: Colors.gray500 },
});
