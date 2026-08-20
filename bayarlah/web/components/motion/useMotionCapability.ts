'use client';

import { useState } from 'react';

/**
 * Gates WebGL-based motion (three.js scenes) behind two checks:
 *  - the browser actually supports WebGL (old Android WebViews, some
 *    in-app browsers used to open WhatsApp share links do not)
 *  - the visitor hasn't asked for reduced motion
 *
 * Resolved once per mount via a lazy `useState` initializer — cheap,
 * runs client-side only (guarded for SSR), and avoids the cascading
 * render that a `useEffect(() => setState(...))` on mount would cause.
 */
export function useMotionCapability(): boolean {
  const [capable] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false;

    const prefersReducedMotion = window.matchMedia(
      '(prefers-reduced-motion: reduce)'
    ).matches;
    if (prefersReducedMotion) return false;

    return supportsWebGL();
  });

  return capable;
}

function supportsWebGL(): boolean {
  try {
    const canvas = document.createElement('canvas');
    return !!(
      window.WebGLRenderingContext &&
      (canvas.getContext('webgl') || canvas.getContext('experimental-webgl'))
    );
  } catch {
    return false;
  }
}
