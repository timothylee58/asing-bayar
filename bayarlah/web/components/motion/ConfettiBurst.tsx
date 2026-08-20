'use client';

import dynamic from 'next/dynamic';
import { useMotionCapability } from './useMotionCapability';

// three.js + @react-three/fiber are only pulled into the client bundle the
// moment a burst is actually requested — SSR is off since WebGL requires
// a browser canvas.
const ConfettiScene = dynamic(() => import('./ConfettiScene'), { ssr: false });

interface ConfettiBurstProps {
  /** Bump this (e.g. `Date.now()`) each time a burst should fire. `0`/`null` renders nothing. */
  triggerSeed: number | null;
  onComplete?: () => void;
}

/**
 * Drop-in confetti burst for payment-success / game-reveal moments.
 * Falls back to rendering nothing (never a broken/blank canvas) when the
 * browser lacks WebGL or the visitor has `prefers-reduced-motion` set —
 * the surrounding UI (e.g. the 🎉 emoji on the "done" screen) already
 * carries the celebratory beat on its own.
 */
export default function ConfettiBurst({ triggerSeed, onComplete }: ConfettiBurstProps) {
  const capable = useMotionCapability();

  if (!triggerSeed || !capable) return null;

  return <ConfettiScene triggerSeed={triggerSeed} onComplete={onComplete} />;
}
