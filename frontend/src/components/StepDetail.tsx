import type { ReactNode } from "react";
import type { RunState } from "../state/runReducer";

type Props = {
  state: RunState;
  stepId: string;
  links: Record<string, string>;
  onApprove: () => void;
};

type Detail = Record<string, any>;

export function StepDetail({ state, stepId, links, onApprove }: Props) {
  const step = state.steps.find((s) => s.id === stepId);
  if (!step) return null;
  const detail: Detail = state.details[stepId] ?? {};
  const tools = state.toolCalls.filter((t) => t.step === stepId);
  const simulated = state.simulated.includes(step.primitive);

  return (
    <section className="detail">
      <header className="detail-header">
        <span className="primitive-tag">{step.primitive}</span>
        <h2>{step.label}</h2>
        {simulated && <span className="simulated-tag">Simulated</span>}
        <span className={`status-tag status-${step.status}`}>{step.status}</span>
      </header>
      <p className="step-description">{step.description}</p>
      {links[step.primitive] && (
        <a className="console-link" href={links[step.primitive]} target="_blank" rel="noreferrer">
          Open {step.primitive} in AWS console
        </a>
      )}
      {step.status === "pending" && <p className="muted small">Not started</p>}
      {step.status === "active" && !state.details[stepId] && (
        <div className="working"><span className="muted small">Working</span><div className="indeterminate"><div /></div></div>
      )}
      {step.status !== "pending" && renderBody(stepId, detail, state, onApprove)}
      {tools.length > 0 && stepId !== "approval" && <ToolCalls calls={tools} />}
    </section>
  );
}

function renderBody(stepId: string, detail: Detail, state: RunState, onApprove: () => void) {
  if (!Object.keys(detail).length && stepId !== "human_review" && stepId !== "memory") return null;
  switch (stepId) {
    case "intake":
      return (
        <>
          <Field label="Short-term memory">
            <ul className="list">{(detail.remembered_turns ?? []).map((t: string, i: number) => <li key={i}>{t}</li>)}</ul>
          </Field>
          <Field label="Missing documents">
            <div className="chips">{(detail.missing ?? []).map((d: string) => <span key={d} className="chip">{d}</span>)}</div>
          </Field>
          {detail.message && <Field label="Agent message"><p className="quote">{detail.message}</p></Field>}
        </>
      );
    case "lookup":
      return detail.company ? <KeyValues data={detail.company} /> : null;
    case "registry_page":
      return (
        <>
          <Field label="URL"><code className="inline">{detail.url}</code></Field>
          {detail.screenshot
            ? <img className="screenshot" alt="Registry page" src={`data:image/png;base64,${detail.screenshot}`} />
            : <p className="quote">{detail.text}</p>}
        </>
      );
    case "ownership":
      return <Ownership detail={detail} />;
    case "screening":
      return (
        <>
          <table className="table">
            <thead><tr><th>Person</th><th>PEP</th><th>Sanctions</th></tr></thead>
            <tbody>
              {(detail.results ?? []).map((r: Detail) => (
                <tr key={r.person}><td>{r.person}</td><td>{r.pep ? "Yes" : "No"}</td><td>{r.sanctioned ? "Yes" : "No"}</td></tr>
              ))}
            </tbody>
          </table>
          {detail.risk && <Field label="Risk"><span className={`risk risk-${detail.risk}`}>{detail.risk}</span></Field>}
        </>
      );
    case "approval":
      return <Approval state={state} detail={detail} decisionStep="approval" />;
    case "human_review":
      if (detail.skipped) return <p className="muted">Not needed. {detail.reason}, within policy.</p>;
      return state.status === "awaiting_approval" ? (
        <>
          <p className="muted">Medium risk. A compliance officer decides.</p>
          <button className="primary" onClick={onApprove}>Approve as compliance officer</button>
        </>
      ) : (
        <>
          <Field label="Approved by">{detail.approved_by} · {detail.role}</Field>
          <Approval state={state} detail={{}} decisionStep="human_review" />
        </>
      );
    case "memory":
      return (
        <ul className="records">
          {state.memoryRecords.map((r, i) => (
            <li key={i}><span className="chip chip-strategy">{r.strategy}</span>{r.text}</li>
          ))}
        </ul>
      );
    case "evaluation":
      return (
        <ul className="scores">
          {(detail.scores ?? []).map((s: Detail) => (
            <li key={s.evaluator}>
              <div className="score-row"><span>{s.evaluator}</span><strong>{Math.round(s.value * 100)}%</strong></div>
              <div className="bar"><div style={{ width: `${s.value * 100}%` }} /></div>
              <p className="muted small">{s.explanation}</p>
            </li>
          ))}
        </ul>
      );
    case "registry":
      if (detail.available === false) {
        return <><p>Not permitted in this account.</p><p className="muted small mono">{detail.reason}</p></>;
      }
      return detail.entry ? <KeyValues data={detail.entry} /> : null;
    default:
      return <pre className="code">{JSON.stringify(detail, null, 2)}</pre>;
  }
}

function Ownership({ detail }: { detail: Detail }) {
  const ownership: Record<string, number> = detail.ownership ?? {};
  const owners: string[] = detail.beneficial_owners ?? [];
  return (
    <>
      {detail.code && <Field label="Code written by the model"><pre className="code code-short">{detail.code}</pre></Field>}
      <Field label="Effective ownership">
        <div className="ownership">
          {Object.entries(ownership).sort((a, b) => b[1] - a[1]).map(([person, percent]) => (
            <div key={person} className="ownership-row">
              <span>{person}</span>
              <div className="bar bar-threshold">
                <div className={owners.includes(person) ? "bar-owner" : ""} style={{ width: `${percent}%` }} />
              </div>
              <strong>{percent}%</strong>
            </div>
          ))}
          <p className="muted small">Beneficial owner: more than 25%</p>
        </div>
      </Field>
      {"matches_reference" in detail && (
        <Field label="Check">{detail.matches_reference ? "Matches tested reference" : "Differs from reference"}</Field>
      )}
    </>
  );
}

function Approval({ state, detail, decisionStep }: { state: RunState; detail: Detail; decisionStep: string }) {
  const decision = state.policyDecisions.find((p) => p.step === decisionStep);
  return (
    <>
      {decision && (
        <div className={`decision decision-${decision.decision}`}>
          <div className="decision-head"><strong>{decision.decision}</strong><code>{decision.tool}</code>
            <span className="muted small">as {decision.caller}</span></div>
          <pre className="code">{JSON.stringify(decision.arguments, null, 2)}</pre>
          {decision.reason && <p className="small">{decision.reason}</p>}
        </div>
      )}
      {detail.routed_to && <Field label="Routed to"><KeyValues data={detail.routed_to} /></Field>}
    </>
  );
}

function ToolCalls({ calls }: { calls: RunState["toolCalls"] }) {
  return (
    <Field label="Gateway calls">
      {calls.map((c, i) => (
        <div key={i} className="tool-call">
          <div className="tool-head"><code>{c.tool}</code><span className="muted small">as {c.caller}</span></div>
          <div className="io">
            <pre className="code">{JSON.stringify(c.arguments, null, 2)}</pre>
            <pre className="code">{JSON.stringify(c.output, null, 2)}</pre>
          </div>
        </div>
      ))}
    </Field>
  );
}

function KeyValues({ data }: { data: Record<string, unknown> }) {
  return (
    <dl className="kv">
      {Object.entries(data).map(([k, v]) => (
        <div key={k}><dt>{k.replaceAll("_", " ")}</dt><dd>{String(v)}</dd></div>
      ))}
    </dl>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="field">
      <div className="field-label">{label}</div>
      {children}
    </div>
  );
}
