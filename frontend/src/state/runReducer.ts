// Turns the stream of backend events into what the screen shows.
// Pure function: same events in, same state out. Easy to test.

import type { RunEvent, StepInfo, StepStatus } from "../types";

type ToolCall = Extract<RunEvent, { type: "tool_call" }>;
type PolicyDecision = Extract<RunEvent, { type: "policy_decision" }>;
type MemoryRecord = Extract<RunEvent, { type: "memory_record" }>;
type Usage = Extract<RunEvent, { type: "usage" }>;

export type RunState = {
  status: "idle" | "running" | "awaiting_approval" | "completed" | "failed";
  error: string;
  caseId: string;
  company: string;
  sessionId: string;
  actingFor: string;
  simulated: string[];
  steps: (StepInfo & { status: StepStatus })[];
  activeStep: string | null;
  details: Record<string, Record<string, unknown>>;
  toolCalls: ToolCall[];
  policyDecisions: PolicyDecision[];
  memoryRecords: MemoryRecord[];
  usageEvents: Usage[];
  usage: { tokens: number; costUsd: number; byStep: Record<string, number> };
  startedAt: number | null;
  finishedAt: number | null;
};

export const initialState: RunState = {
  status: "idle",
  error: "",
  caseId: "",
  company: "",
  sessionId: "",
  actingFor: "",
  simulated: [],
  steps: [],
  activeStep: null,
  details: {},
  toolCalls: [],
  policyDecisions: [],
  memoryRecords: [],
  usageEvents: [],
  usage: { tokens: 0, costUsd: 0, byStep: {} },
  startedAt: null,
  finishedAt: null,
};

const setStatus = (state: RunState, stepId: string, status: StepStatus) =>
  state.steps.map((s) => (s.id === stepId ? { ...s, status } : s));

export function runReducer(state: RunState, event: RunEvent): RunState {
  switch (event.type) {
    case "run_started":
      return {
        ...initialState,
        status: "running",
        caseId: event.case_id,
        company: event.company,
        sessionId: event.session_id,
        actingFor: event.acting_for,
        simulated: event.simulated,
        steps: event.steps.map((s) => ({ ...s, status: "pending" })),
        startedAt: event.at,
      };

    case "step_started":
      return { ...state, activeStep: event.step, steps: setStatus(state, event.step, "active") };

    case "step_completed": {
      const blocked = state.steps.find((s) => s.id === event.step)?.status === "blocked";
      return {
        ...state,
        status: state.status === "awaiting_approval" ? "running" : state.status,
        steps: blocked ? state.steps : setStatus(state, event.step, "done"),
        details: { ...state.details, [event.step]: event.detail },
      };
    }

    case "policy_decision":
      return {
        ...state,
        policyDecisions: [...state.policyDecisions, event],
        steps: event.decision === "DENY" ? setStatus(state, event.step, "blocked") : state.steps,
      };

    case "step_skipped":
      return { ...state, steps: setStatus(state, event.step, "skipped"),
               details: { ...state.details, [event.step]: { skipped: true, reason: event.reason } } };

    case "reset":
      return initialState;

    case "awaiting_approval":
      return { ...state, status: "awaiting_approval", steps: setStatus(state, event.step, "waiting") };

    case "tool_call":
      return { ...state, toolCalls: [...state.toolCalls, event] };

    case "memory_record":
      return { ...state, memoryRecords: [...state.memoryRecords, event] };

    case "usage": {
      const tokens = event.input_tokens + event.output_tokens;
      return {
        ...state,
        usageEvents: [...state.usageEvents, event],
        usage: {
          tokens: state.usage.tokens + tokens,
          costUsd: state.usage.costUsd + event.cost_usd,
          byStep: { ...state.usage.byStep, [event.step]: (state.usage.byStep[event.step] ?? 0) + tokens },
        },
      };
    }

    case "error":
      return { ...state, status: "failed", error: event.message, activeStep: null };

    case "run_completed":
      return { ...state, status: "completed", activeStep: null, finishedAt: event.at };
  }
}
