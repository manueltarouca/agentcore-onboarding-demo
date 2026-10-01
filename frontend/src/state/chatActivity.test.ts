import { describe, expect, it } from "vitest";
import { activityRows } from "./chatActivity";

const turn = [
  { type: "memory_read", turns: 2 },
  { type: "policy_decision", tool: "approve_customer", decision: "DENY", caller: "Lusitania Holdings SGPS" },
  { type: "policy_decision", tool: "case_status", decision: "ALLOW", caller: "Lusitania Holdings SGPS" },
  { type: "tool_call", tool: "case_status", output: { stage: "Under review" }, caller: "Lusitania Holdings SGPS" },
  { type: "usage", input_tokens: 900, output_tokens: 60, latency_ms: 2100, cost_usd: 0.0036 },
  { type: "memory_saved", turns: 2 },
  { type: "chat_reply", text: "Hi" },
];

describe("activityRows", () => {
  it("turns one chat turn into what the agent did, in order, one primitive per row", () => {
    const rows = activityRows(turn);
    expect(rows.map((r) => r.primitive)).toEqual(["Memory", "Policy", "Policy", "Gateway", "Model", "Memory"]);
    expect(rows[0].text).toBe("Read 2 earlier messages");
    expect(rows[1]).toMatchObject({ text: "approve_customer", tone: "deny", note: "DENY as Lusitania Holdings SGPS" });
    expect(rows[3].text).toBe("case_status");
    expect(rows[4].text).toBe("960 tokens · 2.1 s");
  });

  it("says when the conversation is new", () => {
    expect(activityRows([{ type: "memory_read", turns: 0 }])[0].text).toBe("New conversation");
  });
});
