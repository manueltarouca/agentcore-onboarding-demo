// Diagram geometry. One lane per Runtime invocation, read left to right:
// lane 1 runs as the relationship manager, lane 2 as the compliance officer.

export const NODE = { width: 184, height: 84 };
export const LANE = { height: 210, labelOffset: 40 };
const GAP_X = 36;
const ORIGIN = { x: 56, y: 108 };
const PER_LANE = 6;

export type Point = { x: number; y: number };

export function nodePosition(index: number, invocations: number[]): Point {
  const lane = (invocations[index] ?? 1) - 1;
  const firstOfLane = invocations.findIndex((i) => i === lane + 1);
  const column = index - firstOfLane;
  return { x: ORIGIN.x + column * (NODE.width + GAP_X), y: ORIGIN.y + lane * LANE.height };
}

export function edgePath(from: Point, to: Point): string {
  const midY = (p: Point) => p.y + NODE.height / 2;
  if (from.y === to.y) return `M ${from.x + NODE.width} ${midY(from)} L ${to.x} ${midY(to)}`;
  // Between lanes: down from the last node of lane 1, along the left margin, into lane 2 from the side,
  // so the line never crosses the lane label.
  const startX = from.x + NODE.width / 2;
  const turnY = from.y + NODE.height + (to.y - from.y - NODE.height) / 2;
  const marginX = to.x - 22;
  return `M ${startX} ${from.y + NODE.height} L ${startX} ${turnY} L ${marginX} ${turnY} ` +
    `L ${marginX} ${midY(to)} L ${to.x} ${midY(to)}`;
}

export function laneLabelY(lane: number): number {
  return ORIGIN.y - 18 + lane * LANE.height;
}

export function handoffPoint(from: Point, to: Point): Point {
  return { x: (from.x + to.x + NODE.width) / 2, y: from.y + NODE.height + (to.y - from.y - NODE.height) / 2 };
}

export const DIAGRAM = {
  width: ORIGIN.x * 2 + PER_LANE * NODE.width + (PER_LANE - 1) * GAP_X,
  height: ORIGIN.y + LANE.height + NODE.height + 48,
};
