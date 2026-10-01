// What the agent did for one chat message, as rows: one AgentCore primitive per row.

export type ChatEvent = { type: string; [key: string]: unknown };
export type ActivityRow = { primitive: string; text: string; note?: string; tone?: "allow" | "deny"; detail?: unknown };

export function activityRows(events: ChatEvent[]): ActivityRow[] {
  return events.flatMap((e): ActivityRow[] => {
    switch (e.type) {
      case "memory_read":
        return [{ primitive: "Memory", text: e.turns ? `Read ${e.turns} earlier messages` : "New conversation" }];
      case "policy_decision": {
        const allowed = e.decision === "ALLOW";
        return [{ primitive: "Policy", text: `${e.tool}${argumentsShown(e.arguments)}`, tone: allowed ? "allow" : "deny",
                  note: `${e.decision} as ${e.caller}` }];
      }
      case "tool_call":
        return [{ primitive: "Gateway", text: String(e.tool), note: "Lambda via MCP", detail: e.output }];
      case "usage": {
        const tokens = Number(e.input_tokens) + Number(e.output_tokens);
        return [{ primitive: "Model", text: `${tokens.toLocaleString("en-US")} tokens · ${(Number(e.latency_ms) / 1000).toFixed(1)} s`,
                  note: `$${Number(e.cost_usd).toFixed(4)}` }];
      }
      case "memory_saved":
        return [{ primitive: "Memory", text: "Saved this exchange" }];
      default:
        return [];
    }
  });
}

// The arguments that matter to the decision. The case id is always the client's own, so it is left out.
function argumentsShown(args: unknown): string {
  const shown = Object.entries((args ?? {}) as Record<string, unknown>).filter(([k]) => k !== "case_id");
  return shown.length ? `(${shown.map(([k, v]) => `${k}=${v}`).join(", ")})` : "";
}
