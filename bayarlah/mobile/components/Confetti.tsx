import { useEffect, useRef } from 'react';
import { StyleSheet, Dimensions } from 'react-native';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withTiming,
  withDelay,
  withSequence,
  withSpring,
  Easing,
} from 'react-native-reanimated';

const { width: W, height: H } = Dimensions.get('window');

const COLORS = ['#C8410A', '#BA7517', '#1D9E75', '#3B82F6', '#8B5CF6', '#EC4899', '#F97316', '#14B8A6'];
const PARTICLE_COUNT = 28;

interface Particle {
  x: number;
  y: number;
  tx: number;
  ty: number;
  color: string;
  size: number;
  delay: number;
  duration: number;
  rotate: number;
}

function seeded(seed: number) {
  let s = seed;
  return () => {
    s = (s * 1664525 + 1013904223) & 0xffffffff;
    return (s >>> 0) / 0xffffffff;
  };
}

function buildParticles(): Particle[] {
  const rng = seeded(42);
  return Array.from({ length: PARTICLE_COUNT }, (_, i) => ({
    x: W * 0.5 + (rng() - 0.5) * W * 0.3,
    y: H * 0.4,
    tx: (rng() - 0.5) * W * 1.2,
    ty: H * 0.4 + rng() * H * 0.5,
    color: COLORS[i % COLORS.length],
    size: 8 + rng() * 8,
    delay: rng() * 300,
    duration: 1200 + rng() * 800,
    rotate: rng() * 720,
  }));
}

const PARTICLES = buildParticles();

function Particle({ p }: { p: Particle }) {
  const x = useSharedValue(p.x);
  const y = useSharedValue(p.y);
  const opacity = useSharedValue(0);
  const scale = useSharedValue(0);
  const rotate = useSharedValue(0);

  useEffect(() => {
    const easing = Easing.out(Easing.cubic);
    opacity.value = withDelay(p.delay, withSequence(
      withTiming(1, { duration: 200 }),
      withTiming(0, { duration: p.duration - 200, easing }),
    ));
    scale.value = withDelay(p.delay, withSequence(
      withSpring(1.2, { damping: 8 }),
      withTiming(0.6, { duration: p.duration }),
    ));
    x.value = withDelay(p.delay, withTiming(p.x + p.tx, { duration: p.duration, easing }));
    y.value = withDelay(p.delay, withTiming(p.ty, { duration: p.duration, easing }));
    rotate.value = withDelay(p.delay, withTiming(p.rotate, { duration: p.duration }));
  }, []);

  const style = useAnimatedStyle(() => ({
    position: 'absolute',
    left: x.value - p.size / 2,
    top: y.value - p.size / 2,
    width: p.size,
    height: p.size * 0.6,
    borderRadius: 2,
    backgroundColor: p.color,
    opacity: opacity.value,
    transform: [{ scale: scale.value }, { rotate: `${rotate.value}deg` }],
  }));

  return <Animated.View style={style} />;
}

interface Props {
  visible: boolean;
}

export function Confetti({ visible }: Props) {
  if (!visible) return null;
  return (
    <>
      {PARTICLES.map((p, i) => (
        <Particle key={i} p={p} />
      ))}
    </>
  );
}
