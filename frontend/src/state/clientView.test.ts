import { describe, expect, it } from "vitest";
import type { RunEvent } from "../types";
import { initialState, runReducer } from "./runReducer";
import { clientView } from "./clientView";

const steps = ["intake", "lookup", "screening", "approval", "human_review"].map((id) => (
  { id, label: id, primitive: "p", description: "d", invocation: id === "human_review" ? 2 : 1 }));

const play = (events: RunEvent[]) => events.reduce(runReducer, initialState);
const started: RunEvent = { type: "run_started", at: 0, case_id: "C1", company: "Lusitania Holdings SGPS",
  session_id: "s1", acting_for: "Rita Almeida", simulated: [], steps };
const intake: RunEvent = { type: "step_completed", at: 1, step: "intake",
  detail: { missing: ["Beneficial owner declaration"], message: "Please ask the customer..." } };
const screened: RunEvent[] = [
  { type: "step_completed", at: 2, step: "screening",
    detail: { risk: "medium", results: [{ person: "Miguel Santos", pep: true }] } },
  { type: "policy_decision", at: 3, step: "approval", tool: "approve_customer", decision: "DENY",
    reason: "risk medium", arguments: { risk: "medium" }, caller: "Rita Almeida" },
  { type: "step_completed", at: 4, step: "approval", detail: { decision: "DENY", queue: "Compliance review" } },
  { type: "awaiting_approval", at: 5, step: "human_review", reason: "medium risk" },
];
const approved: RunEvent = { type: "step_completed", at: 6, step: "human_review",
  detail: { approved_by: "compliance.officer" } };

describe("clientView", () => {
  it("shows nothing before the application is submitted", () => {
    expect(clientView(initialState).stage).toBe("not_started");
  });

  it("asks the client only for the documents still missing", () => {
    const view = clientView(play([started, intake]));
    expect(view.documentsNeeded).toEqual(["Beneficial owner declaration"]);
    expect(view.timeline.map((t) => t.state)).toEqual(["done", "done", "active", "pending"]);
  });

  it("never tells the client about screening, risk or the compliance review", () => {
    const view = clientView(play([started, intake, ...screened]));
    expect(view.stage).toBe("in_review");
    expect(JSON.stringify(view)).not.toMatch(/miguel|politically|pep|risk|medium|compliance|deny|policy/i);
  });

  it("confirms the approval and what is still needed to open the account", () => {
    const view = clientView(play([started, intake, ...screened, approved]));
    expect(view.stage).toBe("approved");
    expect(view.documentsNeeded).toEqual(["Beneficial owner declaration"]);
    expect(view.timeline.every((t) => t.state === "done")).toBe(true);
    expect(JSON.stringify(view)).not.toMatch(/compliance/i);
  });
});

describe("clientView, low risk", () => {
  it("shows the application approved when the agent approved it within policy", () => {
    const view = clientView(play([started, intake,
      { type: "step_completed", at: 4, step: "approval", detail: { decision: "ALLOW" } }]));
    expect(view.stage).toBe("approved");
  });
});
