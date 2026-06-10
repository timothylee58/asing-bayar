export interface WheelSegment {
  participantId: string;
  name: string;
  startAngleDeg: number; // 0=top, clockwise
  endAngleDeg: number;
  color: string;
}

export interface SpinResult {
  winnerIndex: number;      // index into segments[]
  winnerParticipantId: string;
  totalRotationDeg: number; // how far the wheel spins
  durationMs: number;       // animation duration
}

const SEGMENT_COLORS = [
  '#C8410A', // brandRed
  '#BA7517', // turmericGold
  '#1D9E75', // forestGreen
  '#3B82F6', // blue
  '#8B5CF6', // violet
  '#EC4899', // pink
  '#14B8A6', // teal
  '#F97316', // orange
];

export function buildSegments(
  participants: { id: string; name: string }[],
): WheelSegment[] {
  const n = participants.length;
  const anglePer = 360 / n;
  return participants.map((p, i) => ({
    participantId: p.id,
    name: p.name,
    startAngleDeg: i * anglePer,
    endAngleDeg: (i + 1) * anglePer,
    color: SEGMENT_COLORS[i % SEGMENT_COLORS.length],
  }));
}

/**
 * Given an angularVelocity (degrees) from the server and current wheel rotation,
 * compute final resting angle and which segment is under the top pointer.
 *
 * Pointer is fixed at the top (0°). Wheel rotates clockwise.
 * Segment under pointer = the one whose range contains (360 - finalAngle % 360).
 */
export function resolveSpinResult(
  segments: WheelSegment[],
  angularVelocity: number,
  currentRotationDeg: number = 0,
): SpinResult {
  // Add at least 2 full rotations for visual effect
  const totalRotation = currentRotationDeg + angularVelocity + 720;
  const finalAngle = totalRotation % 360;
  // Pointer is at top = 0°. Wheel has rotated finalAngle clockwise.
  // The segment at pointer = the segment covering (360 - finalAngle) % 360
  const pointerAngle = (360 - finalAngle + 360) % 360;
  const n = segments.length;
  const anglePer = 360 / n;
  const winnerIndex = Math.floor(pointerAngle / anglePer) % n;

  // Duration 4–6 seconds based on velocity
  const durationMs = 4000 + Math.min((angularVelocity - 800) / 400, 1) * 2000;

  return {
    winnerIndex,
    winnerParticipantId: segments[winnerIndex].participantId,
    totalRotationDeg: totalRotation,
    durationMs,
  };
}

/** Arc path data for a pie slice (SVG). cx/cy = center, r = radius */
export function slicePath(
  cx: number,
  cy: number,
  r: number,
  startDeg: number,
  endDeg: number,
): string {
  const toRad = (d: number) => ((d - 90) * Math.PI) / 180;
  const sx = cx + r * Math.cos(toRad(startDeg));
  const sy = cy + r * Math.sin(toRad(startDeg));
  const ex = cx + r * Math.cos(toRad(endDeg));
  const ey = cy + r * Math.sin(toRad(endDeg));
  const large = endDeg - startDeg > 180 ? 1 : 0;
  return `M ${cx} ${cy} L ${sx} ${sy} A ${r} ${r} 0 ${large} 1 ${ex} ${ey} Z`;
}

/** Label position along the bisector of a slice */
export function sliceLabelPos(
  cx: number,
  cy: number,
  r: number,
  startDeg: number,
  endDeg: number,
  radiusFraction = 0.62,
): { x: number; y: number; rotation: number } {
  const bisector = (startDeg + endDeg) / 2;
  const toRad = (d: number) => ((d - 90) * Math.PI) / 180;
  return {
    x: cx + r * radiusFraction * Math.cos(toRad(bisector)),
    y: cy + r * radiusFraction * Math.sin(toRad(bisector)),
    rotation: bisector,
  };
}
