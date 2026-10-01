import type { RunState } from "../state/runReducer";

export function ObservabilityStrip({ state, elapsedMs }: { state: RunState; elapsedMs: number }) {
  const maxStepTokens = Math.max(1, ...Object.values(state.usage.byStep));
  return (
    <footer className="strip">
      <Metric label="Tokens" value={state.usage.tokens.toLocaleString("en-US")} />
      <Metric label="Est. cost" value={`$${state.usage.costUsd.toFixed(4)}`} />
      <Metric label="Tool calls" value={String(state.toolCalls.length)} />
      <Metric label="Elapsed" value={`${(elapsedMs / 1000).toFixed(1)} s`} />
      <div className="sparkline" aria-label="Tokens per step">
        {state.steps.map((s) => (
          <div key={s.id} title={`${s.label}: ${state.usage.byStep[s.id] ?? 0} tokens`}
               style={{ height: `${((state.usage.byStep[s.id] ?? 0) / maxStepTokens) * 100}%` }} />
        ))}
      </div>
    </footer>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric">
      <span className="metric-label">{label}</span>
      <span className="metric-value">{value}</span>
    </div>
  );
}
