// Events sent by the backend (see backend/src/onboarding_demo/workflow/runner.py).

export type StepInfo = { id: string; label: string; primitive: string; description: string; invocation: number };

export type RunEvent =
  | { type: "run_started"; at: number; case_id: string; company: string; session_id: string;
      acting_for: string; simulated: string[]; steps: StepInfo[] }
  | { type: "step_started"; at: number; step: string }
  | { type: "step_completed"; at: number; step: string; detail: Record<string, unknown> }
  | { type: "tool_call"; at: number; step: string; tool: string; arguments: Record<string, unknown>;
      output: Record<string, unknown>; caller: string }
  | { type: "policy_decision"; at: number; step: string; tool: string; decision: "ALLOW" | "DENY";
      reason: string; arguments: Record<string, unknown>; caller: string }
  | { type: "usage"; at: number; step: string; model_id: string; input_tokens: number;
      output_tokens: number; latency_ms: number; cost_usd: number }
  | { type: "awaiting_approval"; at: number; step: string; reason: string }
  | { type: "memory_record"; at: number; step: string; strategy: string; text: string }
  | { type: "error"; at: number; message: string }
  | { type: "run_completed"; at: number; totals: { tokens: number; cost_usd: number; tool_calls: number } };

export type StepStatus = "pending" | "active" | "done" | "blocked" | "waiting";
