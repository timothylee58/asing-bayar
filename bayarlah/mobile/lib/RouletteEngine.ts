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
 * Work out how far to turn the wheel so the fixed top pointer comes to rest inside the
 * slice of the winner the SERVER already chose.
 *
 * (The client used to derive the winner from the server's angular velocity and then
 * report it back, so the "server-computed, not manipulable" result was really decided,
 * and could be edited, on the phone. The wheel is now purely an animation of the
 * server's decision.)
 *
 * Pointer is fixed at the top (0 deg). The wheel rotates clockwise, so for the pointer to
 * rest at angle P on the wheel the wheel's final rotation is (360 - P) mod 360.
 *
 * @param landingFraction where inside the winning slice (0..1) to stop; chosen by the
 *        server so the stopping point looks natural but can't straddle a boundary.
 */
export function resolveSpinResult(
  segments: WheelSegment[],
  angularVelocity: number,
  currentRotationDeg: number,
  winnerParticipantId: string,
  landingFraction: number,
): SpinResult {
  const winnerIndex = segments.findIndex((s) => s.participantId === winnerParticipantId);
  if (winnerIndex < 0) throw new Error('The winner is not on the wheel');

  const anglePer = 360 / segments.length;
  const pointerAngle = (winnerIndex + landingFraction) * anglePer;
  const finalAngle = (360 - pointerAngle) % 360;

  // Always at least two full turns for show; the server's velocity adds up to two more,
  // so spins still vary in length.
  const extraTurns = Math.min(2, Math.max(0, Math.floor((angularVelocity - 800) / 200)));
  const base = currentRotationDeg + 720 + extraTurns * 360;
  const delta = (((finalAngle - (base % 360)) % 360) + 360) % 360;

  // Duration 4-6 seconds based on velocity
  const durationMs = 4000 + Math.min(Math.max((angularVelocity - 800) / 400, 0), 1) * 2000;

  return {
    winnerIndex,
    winnerParticipantId,
    totalRotationDeg: base + delta,
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
