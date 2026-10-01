import { describe, expect, it } from "vitest";
import type { RunEvent } from "../types";
import { initialState, runReducer } from "./runReducer";

const steps = [
  { id: "intake", label: "Intake", primitive: "Memory", description: "d", invocation: 1 },
  { id: "approval", label: "Approval attempt", primitive: "Policy", description: "d", invocation: 1 },
  { id: "human_review", label: "Human review", primitive: "Identity", description: "d", invocation: 2 },
];

const started: RunEvent = {
  type: "run_started", at: 0, case_id: "C1", company: "Co", session_id: "s1",
  acting_for: "Rita Almeida", simulated: [], steps,
};

const play = (events: RunEvent[]) => events.reduce(runReducer, initialState);

describe("runReducer", () => {
  it("lists every step as pending when the run starts", () => {
    const state = play([started]);
    expect(state.status).toBe("running");
    expect(state.steps.map((s) => s.status)).toEqual(["pending", "pending", "pending"]);
  });

  it("marks the current step active and finished steps done", () => {
    const state = play([
      started,
      { type: "step_started", at: 1, step: "intake" },
      { type: "step_completed", at: 2, step: "intake", detail: { missing: ["x"] } },
      { type: "step_started", at: 3, step: "approval" },
    ]);
    expect(state.steps.map((s) => s.status)).toEqual(["done", "active", "pending"]);
    expect(state.activeStep).toBe("approval");
    expect(state.details.intake).toEqual({ missing: ["x"] });
  });

  it("shows a policy denial on its step", () => {
    const state = play([
      started,
      { type: "step_started", at: 1, step: "approval" },
      { type: "policy_decision", at: 2, step: "approval", tool: "approve_customer", decision: "DENY",
        reason: "only low risk", arguments: {}, caller: "Rita" },
      { type: "step_completed", at: 3, step: "approval", detail: {} },
    ]);
    expect(state.steps[1].status).toBe("blocked");
    expect(state.policyDecisions).toHaveLength(1);
  });

  it("waits for the human and records the elapsed approval", () => {
    const state = play([
      started,
      { type: "step_started", at: 1, step: "human_review" },
      { type: "awaiting_approval", at: 2, step: "human_review", reason: "medium risk" },
    ]);
    expect(state.status).toBe("awaiting_approval");
    expect(state.steps[2].status).toBe("waiting");
  });

  it("adds up tokens and cost per step and in total", () => {
    const usage = (step: string, tokens: number, cost: number): RunEvent => ({
      type: "usage", at: 1, step, model_id: "m", input_tokens: tokens, output_tokens: 0, latency_ms: 10, cost_usd: cost,
    });
    const state = play([started, usage("intake", 100, 0.001), usage("intake", 50, 0.0005), usage("approval", 10, 0.0001)]);
    expect(state.usage.tokens).toBe(160);
    expect(state.usage.costUsd).toBeCloseTo(0.0016);
    expect(state.usage.byStep.intake).toBe(150);
  });

  it("collects tool calls and memory records in order", () => {
    const state = play([
      started,
      { type: "tool_call", at: 1, step: "intake", tool: "registry_lookup", arguments: {}, output: {}, caller: "Rita" },
      { type: "memory_record", at: 2, step: "intake", strategy: "Semantic", text: "fact" },
    ]);
    expect(state.toolCalls.map((t) => t.tool)).toEqual(["registry_lookup"]);
    expect(state.memoryRecords[0].strategy).toBe("Semantic");
  });

  it("finishes when the run completes", () => {
    const state = play([started, { type: "run_completed", at: 9, totals: { tokens: 0, cost_usd: 0, tool_calls: 0 } }]);
    expect(state.status).toBe("completed");
    expect(state.activeStep).toBeNull();
  });

  it("shows an error and stops the run", () => {
    const state = play([started, { type: "step_started", at: 1, step: "intake" },
                        { type: "error", at: 2, message: "Runtime returned 403" }]);
    expect(state.status).toBe("failed");
    expect(state.error).toBe("Runtime returned 403");
  });

  it("keeps the allowed decision for the compliance officer", () => {
    const state = play([
      started,
      { type: "step_started", at: 1, step: "human_review" },
      { type: "policy_decision", at: 2, step: "human_review", tool: "approve_customer", decision: "ALLOW",
        reason: "", arguments: {}, caller: "Compliance officer" },
    ]);
    expect(state.policyDecisions[0].caller).toBe("Compliance officer");
    expect(state.steps[2].status).toBe("active");
  });
});
