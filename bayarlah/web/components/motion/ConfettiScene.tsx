'use client';

import { useEffect, useMemo, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import * as THREE from 'three';

// Bayarlah brand palette (README → Design System → Colours), reused here so
// the WebGL burst reads as the same product as the flat-CSS UI around it.
const COLORS = ['#C8410A', '#BA7517', '#1D9E75', '#FAFAF8'] as const;

const PARTICLE_COUNT = 90;
const LIFETIME_MS = 3500; // matches mobile Confetti.tsx particle lifetime
const GRAVITY = -9.8;

interface Particle {
  origin: THREE.Vector3;
  velocity: THREE.Vector3;
  rotationAxis: THREE.Vector3;
  spinSpeed: number;
  color: THREE.Color;
}

function makeParticles(seed: number): Particle[] {
  // Cheap deterministic-enough PRNG so each burst still looks random
  // without depending on `Math.random` inside render.
  let s = seed || 1;
  const rand = () => {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };

  return Array.from({ length: PARTICLE_COUNT }, () => {
    const angle = rand() * Math.PI * 2;
    const speed = 2.5 + rand() * 3.5;
    return {
      origin: new THREE.Vector3((rand() - 0.5) * 0.6, 0, (rand() - 0.5) * 0.6),
      velocity: new THREE.Vector3(
        Math.cos(angle) * speed,
        5 + rand() * 4,
        Math.sin(angle) * speed
      ),
      rotationAxis: new THREE.Vector3(rand(), rand(), rand()).normalize(),
      spinSpeed: 4 + rand() * 8,
      color: new THREE.Color(COLORS[Math.floor(rand() * COLORS.length)]),
    };
  });
}

function ConfettiParticles({ seed, onDone }: { seed: number; onDone: () => void }) {
  const meshRef = useRef<THREE.InstancedMesh>(null);
  const particles = useMemo(() => makeParticles(seed), [seed]);
  const startedAt = useRef(0);
  const dummy = useMemo(() => new THREE.Object3D(), []);
  const doneRef = useRef(false);

  // Reset the clock as a post-commit effect (not during render) whenever a
  // fresh burst is requested via a new seed.
  useEffect(() => {
    startedAt.current = performance.now();
    doneRef.current = false;
  }, [seed]);

  useFrame(() => {
    const mesh = meshRef.current;
    if (!mesh || doneRef.current) return;

    const elapsedMs = performance.now() - startedAt.current;
    const t = elapsedMs / 1000;

    if (elapsedMs >= LIFETIME_MS) {
      doneRef.current = true;
      onDone();
      return;
    }

    const fade = 1 - elapsedMs / LIFETIME_MS;

    particles.forEach((p, i) => {
      dummy.position.set(
        p.origin.x + p.velocity.x * t,
        p.origin.y + p.velocity.y * t + 0.5 * GRAVITY * t * t,
        p.origin.z + p.velocity.z * t
      );
      dummy.rotation.setFromVector3(
        p.rotationAxis.clone().multiplyScalar(p.spinSpeed * t)
      );
      dummy.scale.setScalar(Math.max(fade, 0));
      dummy.updateMatrix();
      mesh.setMatrixAt(i, dummy.matrix);
      mesh.setColorAt(i, p.color);
    });

    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
  });

  return (
    <instancedMesh ref={meshRef} args={[undefined, undefined, PARTICLE_COUNT]}>
      <planeGeometry args={[0.14, 0.22]} />
      <meshBasicMaterial side={THREE.DoubleSide} toneMapped={false} />
    </instancedMesh>
  );
}

interface ConfettiSceneProps {
  /** Bump this (e.g. `Date.now()`) to fire a fresh burst. */
  triggerSeed: number;
  onComplete?: () => void;
}

/**
 * Fullscreen, click-through WebGL confetti burst. Mount only while a burst
 * should be visible — the parent lazy-loads this via next/dynamic so three.js
 * never ships to visitors who never trigger it.
 */
export default function ConfettiScene({ triggerSeed, onComplete }: ConfettiSceneProps) {
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none fixed inset-0 z-50"
      style={{ mixBlendMode: 'normal' }}
    >
      <Canvas
        orthographic
        camera={{ zoom: 80, position: [0, 0, 10] }}
        gl={{ alpha: true, antialias: true }}
        dpr={[1, 2]}
      >
        <ConfettiParticles seed={triggerSeed} onDone={() => onComplete?.()} />
      </Canvas>
    </div>
  );
}
