// What the compliance officer sees: cases the agent was not allowed to approve.
import type { RunState } from "../state/runReducer";
import { OwnershipBars } from "./RelationshipManagerView";

// Detail payloads are free-form JSON from the backend.
type Detail = Record<string, any>;

export function ComplianceView({ state, onApprove }: { state: RunState; onApprove: () => void }) {
  const inQueue = state.details.approval?.decision === "DENY";
  const approved = Boolean(state.details.human_review);
  const waiting = state.status === "awaiting_approval";
  const denial = state.policyDecisions.find((p) => p.decision === "DENY");
  const allowed = state.policyDecisions.find((p) => p.decision === "ALLOW");
  const screening: Detail = state.details.screening ?? {};
  const summary = String((state.details.approval as Detail | undefined)?.summary ?? "");

  return (
    <div className="persona">
      <aside className="case-card">
        <div className="field-label">Review queue</div>
        {inQueue ? (
          <button className={`queue-item ${approved ? "queue-done" : ""}`}>
            <strong>{state.company}</strong>
            <span className="muted mono small">{state.caseId}</span>
            <span className={`risk risk-${screening.risk}`}>{screening.risk}</span>
          </button>
        ) : <p className="muted">No cases waiting</p>}
        <div className="field-label top-gap">Signed in as</div>
        <p>Compliance officer</p>
      </aside>

      <section className="feed">
        {!inQueue && <div className="empty">Cases appear here when the agent is not allowed to decide</div>}
        {inQueue && (
          <>
            {approved ? (
              <div className="banner banner-done">
                <span className="banner-label">Approved</span>
                {allowed && <span className="mono small">{allowed.caller} · {allowed.tool} · ALLOW</span>}
              </div>
            ) : (
              <div className="banner banner-waiting">
                <span className="banner-label">Decision needed</span>
                <span className="muted">Runs as compliance.officer. Policy checks the call again.</span>
                <button className="primary" onClick={onApprove} disabled={!waiting}>Approve</button>
              </div>
            )}
            <article className="card card-blocked">
              <header><span className="card-tag">Why it is here</span><h3>The agent may not approve this case</h3></header>
              {summary && <p className="quote">{summary}</p>}
              <p className="muted top-gap">Policy allows the agent to approve low-risk customers only.</p>
              {denial && <p className="mono small muted">{denial.caller} · {denial.tool} · DENY</p>}
            </article>
            <article className="card">
              <header><span className="card-tag">Screening</span><h3>Findings</h3></header>
              {(screening.results ?? []).map((r: Detail) => (
                <div key={r.person} className="row-between">
                  <span>{r.person}</span>
                  <span className={r.pep ? "flag-text" : "muted"}>{r.pep ? "Politically exposed person" : "Clear"}</span>
                </div>
              ))}
            </article>
            <article className="card">
              <header><span className="card-tag">Ownership</span><h3>Beneficial owners</h3></header>
              <OwnershipBars detail={state.details.ownership ?? {}} />
            </article>
          </>
        )}
      </section>
    </div>
  );
}
