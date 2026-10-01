import { useEffect, useRef, useState } from "react";
import type { StepInfo, StepStatus } from "../types";
import { DIAGRAM, NODE, edgePath, handoffPoint, laneLabelY, nodePosition } from "./layout";

type Step = StepInfo & { status: StepStatus };

type Props = {
  steps: Step[];
  activeStep: string | null;
  sessionId: string;
  waiting: boolean;
  autonomous: boolean;
  selected: string | null;
  onSelect: (stepId: string) => void;
};

const FLAG: Partial<Record<StepStatus, string>> = { blocked: "DENIED", waiting: "WAITING", skipped: "SKIPPED" };
const LANES = ["Invocation 1  ·  as Rita Almeida, relationship manager", "Invocation 2  ·  as compliance officer"];
const AUTONOMOUS_LANES = [LANES[0], "Still invocation 1  ·  low risk, no human step"];

export function WorkflowDiagram({ steps, activeStep, sessionId, waiting, autonomous, selected, onSelect }: Props) {
  const invocations = steps.map((s) => s.invocation);
  const position = (i: number) => nodePosition(i, invocations);
  const packet = usePacket(steps, activeStep, position);
  const handoffIndex = invocations.indexOf(2);
  const handoff = handoffIndex > 0 ? handoffPoint(position(handoffIndex - 1), position(handoffIndex)) : null;
  const approved = steps[handoffIndex]?.status === "done";

  return (
    <svg className="diagram" viewBox={`0 0 ${DIAGRAM.width} ${DIAGRAM.height}`} role="img" aria-label="Onboarding workflow">
      <defs>
        <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
          <path d="M 0 0 L 10 5 L 0 10 z" className="arrow-head" />
        </marker>
      </defs>

      <rect className="runtime-frame" x="12" y="12" width={DIAGRAM.width - 24} height={DIAGRAM.height - 24} rx="16" />
      <text className="runtime-label" x="36" y="44">
        AgentCore Runtime{sessionId ? `  ·  session ${sessionId}` : ""}
      </text>
      {(autonomous ? AUTONOMOUS_LANES : LANES).map((label, lane) => (
        <text key={label} className="lane-label" x="56" y={laneLabelY(lane)}>{label}</text>
      ))}

      {steps.slice(1).map((step, i) => (
        <path key={`edge-${step.id}`} d={edgePath(position(i), position(i + 1))} markerEnd="url(#arrow)"
              className={`edge ${steps[i].status !== "pending" && step.status !== "pending" ? "edge-done" : ""}`} />
      ))}

      {handoff && (
        <g className={`handoff ${waiting ? "handoff-waiting" : approved || autonomous ? "handoff-done" : ""}`}
           transform={`translate(${handoff.x} ${handoff.y})`}>
          <rect x="-104" y="-15" width="208" height="30" rx="15" />
          <text textAnchor="middle" y="5">{waiting ? "Waiting for compliance" : autonomous ? "Approved by the agent" : approved ? "Approved by a human" : "Human decision"}</text>
        </g>
      )}

      {packet && (
        <circle key={packet.key} r="6" className="packet">
          <animateMotion dur="0.9s" fill="freeze" path={packet.path} />
        </circle>
      )}

      {steps.map((step, i) => {
        const { x, y } = position(i);
        return (
          <g key={step.id} className={`node node-${step.status} ${selected === step.id ? "node-selected" : ""}`}
             transform={`translate(${x} ${y})`} onClick={() => onSelect(step.id)}>
            <rect width={NODE.width} height={NODE.height} rx="12" />
            <text className="node-primitive" x="16" y="30">
              <tspan className="node-index">{String(i + 1).padStart(2, "0")}</tspan>  {step.primitive.toUpperCase()}
            </text>
            <text className="node-label" x="16" y="60">{step.label}</text>
            {FLAG[step.status] && (
              <text className={`node-flag flag-${step.status}`} x={NODE.width - 14} y="30" textAnchor="end">{FLAG[step.status]}</text>
            )}
            {step.status === "done" && <circle className="node-check" cx={NODE.width - 18} cy={NODE.height - 18} r="5" />}
          </g>
        );
      })}
    </svg>
  );
}

// When the active step changes, send a packet along the edge that leads to it.
function usePacket(steps: Step[], activeStep: string | null, position: (i: number) => { x: number; y: number }) {
  const previous = useRef<string | null>(null);
  const [packet, setPacket] = useState<{ key: string; path: string } | null>(null);

  useEffect(() => {
    if (!activeStep || activeStep === previous.current) return;
    const to = steps.findIndex((s) => s.id === activeStep);
    const from = steps.findIndex((s) => s.id === previous.current);
    previous.current = activeStep;
    if (to > 0 && from === to - 1) {
      setPacket({ key: `${activeStep}-${Date.now()}`, path: edgePath(position(from), position(to)) });
    }
  }, [activeStep, steps, position]);

  return packet;
}
