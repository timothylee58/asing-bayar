export interface Rung {
  lane: number; // connects lane[i] → lane[i+1]
  y: number;    // normalised 0..1 (top=0, bottom=1)
}

export interface PathSegment {
  type: 'vertical' | 'horizontal';
  fromLane: number;
  toLane: number;
  fromY: number; // normalised
  toY: number;
}

export interface LadderData {
  nLanes: number;
  rungs: Rung[];
  seed: string;
}

export interface ParticipantPath {
  startLane: number;
  endLane: number;
  segments: PathSegment[];
}

/**
 * Re-create the same ladder on client given the seed + n from the server.
 * Mirrors _generate_tangga_rungs logic in backend/app/api/game.py.
 * Uses a seeded LCG so both sides produce identical rungs deterministically.
 */
export function generateLadder(nLanes: number, seed: string): LadderData {
  const rungs = generateRungs(nLanes, seed);
  return { nLanes, rungs, seed };
}

function seededRandom(seed: string): () => number {
  // Simple mulberry32 seeded from string hash
  let h = 0;
  for (let i = 0; i < seed.length; i++) {
    h = (Math.imul(31, h) + seed.charCodeAt(i)) | 0;
  }
  let s = (h >>> 0) + 0x6d2b79f5;
  return function () {
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    s = (s + 0x9e3779b9) | 0;
    return ((t ^ (t >>> 14)) >>> 0) / 0xffffffff;
  };
}

function generateRungs(nLanes: number, seed: string): Rung[] {
  const rng = seededRandom(seed);
  const nRungs = nLanes * 3;
  const rungs: Rung[] = [];
  const used = new Set<string>();

  for (let attempt = 0; attempt < nRungs * 5 && rungs.length < nRungs; attempt++) {
    const lane = Math.floor(rng() * (nLanes - 1)); // 0 .. nLanes-2
    const y = parseFloat((0.05 + rng() * 0.9).toFixed(2));
    const key = `${lane}:${(Math.round(y * 10) / 10).toFixed(1)}`;
    if (!used.has(key)) {
      used.add(key);
      rungs.push({ lane, y });
    }
  }

  return rungs.sort((a, b) => a.y - b.y);
}

/**
 * Compute the ordered list of path segments for one participant
 * starting at `startLane`, traversing the sorted rungs top→bottom.
 */
export function computePathSegments(startLane: number, rungs: Rung[]): PathSegment[] {
  const segments: PathSegment[] = [];
  let currentLane = startLane;
  let currentY = 0;

  for (const rung of rungs) {
    if (rung.lane === currentLane || rung.lane === currentLane - 1) {
      // Vertical segment down to this rung
      if (rung.y > currentY) {
        segments.push({
          type: 'vertical',
          fromLane: currentLane,
          toLane: currentLane,
          fromY: currentY,
          toY: rung.y,
        });
        currentY = rung.y;
      }
      // Horizontal cross
      const nextLane = rung.lane === currentLane ? currentLane + 1 : currentLane - 1;
      segments.push({
        type: 'horizontal',
        fromLane: currentLane,
        toLane: nextLane,
        fromY: rung.y,
        toY: rung.y,
      });
      currentLane = nextLane;
    }
  }

  // Final vertical to bottom
  if (currentY < 1) {
    segments.push({
      type: 'vertical',
      fromLane: currentLane,
      toLane: currentLane,
      fromY: currentY,
      toY: 1,
    });
  }

  return segments;
}

export function computeAllPaths(nLanes: number, rungs: Rung[]): ParticipantPath[] {
  return Array.from({ length: nLanes }, (_, startLane) => {
    const segments = computePathSegments(startLane, rungs);
    const endLane = segments.at(-1)?.toLane ?? startLane;
    return { startLane, endLane, segments };
  });
}

export function getFinalLane(startLane: number, rungs: Rung[]): number {
  const segments = computePathSegments(startLane, rungs);
  return segments.at(-1)?.toLane ?? startLane;
}
