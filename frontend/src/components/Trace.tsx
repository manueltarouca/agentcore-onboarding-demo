import type { RunState } from "../state/runReducer";

// Observability view: every model call and tool call in order, with tokens and latency.
export function Trace({ state, observabilityLink }: { state: RunState; observabilityLink?: string }) {
  const rows = [
    ...state.usageEvents.map((u) => ({
      at: u.at, step: u.step, kind: "Model", name: u.model_id,
      value: `${u.input_tokens + u.output_tokens} tokens · ${u.latency_ms} ms`, ms: u.latency_ms,
    })),
    ...state.toolCalls.map((t) => ({ at: t.at, step: t.step, kind: "Tool", name: t.tool, value: "", ms: 0 })),
    ...state.policyDecisions.map((p) => ({ at: p.at, step: p.step, kind: "Policy", name: `${p.tool} · ${p.decision}`, value: "", ms: 0 })),
  ].sort((a, b) => a.at - b.at);
  const longest = Math.max(1, ...rows.map((r) => r.ms));
  const repeated = repeatedTools(state);

  return (
    <section className="trace">
      {observabilityLink && (
        <a className="console-link" href={observabilityLink} target="_blank" rel="noreferrer">
          Open full traces in CloudWatch GenAI Observability
        </a>
      )}
      {rows.length === 0 && <p className="muted">No spans yet</p>}
      {rows.map((r, i) => (
        <div key={i} className={`span span-${r.kind.toLowerCase()} ${repeated.has(r.name) && r.kind === "Tool" ? "span-repeated" : ""}`}>
          <span className="span-kind">{r.kind}</span>
          <span className="span-name">{r.name}<span className="muted small"> · {r.step}</span></span>
          <span className="span-bar"><span style={{ width: `${(r.ms / longest) * 100}%` }} /></span>
          <span className="span-value">{r.value}</span>
        </div>
      ))}
    </section>
  );
}

function repeatedTools(state: RunState): Set<string> {
  const seen = new Map<string, number>();
  for (const t of state.toolCalls) {
    const key = `${t.tool}:${JSON.stringify(t.arguments)}`;
    seen.set(key, (seen.get(key) ?? 0) + 1);
  }
  return new Set([...seen].filter(([, n]) => n > 1).map(([k]) => k.split(":")[0]));
}
