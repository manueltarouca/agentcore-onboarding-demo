// What the relationship manager sees: her case, where it stands, and what the agent found.
import { useState, type ReactNode } from "react";
import type { RunState } from "../state/runReducer";

type Detail = Record<string, any>;

const STAGES = [
  { label: "Documents", steps: ["intake"] },
  { label: "Verification", steps: ["lookup", "registry_page"] },
  { label: "Ownership", steps: ["ownership"] },
  { label: "Screening", steps: ["screening"] },
  { label: "Decision", steps: ["approval", "human_review"] },
];

export function RelationshipManagerView({ state }: { state: RunState }) {
  const [zoom, setZoom] = useState(false);
  const d = (id: string): Detail => state.details[id] ?? {};
  const status = caseStatus(state);
  const decided = Boolean(state.details.human_review);
  const sentToCompliance = state.details.approval?.decision === "DENY";

  return (
    <div className="persona">
      <aside className="case-card">
        <div className="field-label">Case</div>
        <h2>{state.company || "Lusitania Holdings SGPS"}</h2>
        <p className="muted mono">{state.caseId || "CASE-2026-0142"}</p>
        <div className="field-label">Owner</div>
        <p>Rita Almeida · Relationship manager</p>
        <div className="field-label">Status</div>
        <span className={`pill pill-${status.tone}`}>{status.label}</span>
        <ol className="tracker">
          {STAGES.map((stage) => (
            <li key={stage.label} className={`tracker-${stageStatus(state, stage.steps)}`}>{stage.label}</li>
          ))}
        </ol>
      </aside>

      <section className="feed feed-grid">
        {state.status !== "idle" && (
          <div className={`banner banner-${status.tone}`}>
            <span className="banner-label">{status.label}</span>
            <span className="muted">{status.detail}</span>
          </div>
        )}
        {state.status === "idle" && <div className="empty">Run the case to see the agent work</div>}
        {d("intake").message && (
          <Card title="Missing documents" tag="Agent">
            <p className="quote">{d("intake").message}</p>
            <div className="chips">{(d("intake").missing ?? []).map((m: string) => <span key={m} className="chip">{m}</span>)}</div>
          </Card>
        )}
        {d("lookup").company && (
          <Card title="Company verified" tag="Registry">
            <div className="split">
              <dl className="kv">
                {["name", "legal_form", "registered_office", "status"].map((k) => (
                  <div key={k}><dt>{k.replaceAll("_", " ")}</dt><dd>{String(d("lookup").company[k])}</dd></div>
                ))}
              </dl>
              {d("registry_page").screenshot && (
                <figure className="thumb-figure" onClick={() => setZoom(true)}>
                  <img className="thumb" alt="Registry page read by the agent"
                       src={`data:image/png;base64,${d("registry_page").screenshot}`} />
                  <figcaption className="muted small">Read by the agent's browser</figcaption>
                </figure>
              )}
            </div>
          </Card>
        )}
        {d("ownership").ownership && (
          <Card title="Beneficial owners" tag="Ownership" wide>
            <OwnershipBars detail={d("ownership")} />
          </Card>
        )}
        {d("screening").risk && (
          <Card title="Screening" tag="Compliance checks">
            {(d("screening").results ?? []).map((r: Detail) => (
              <div key={r.person} className="row-between">
                <span>{r.person}</span>
                <span className={r.pep ? "flag-text" : "muted"}>{r.pep ? "Politically exposed person" : "Clear"}</span>
              </div>
            ))}
            <div className="row-between top-gap"><span className="muted">Risk</span>
              <span className={`risk risk-${d("screening").risk}`}>{d("screening").risk}</span></div>
          </Card>
        )}
        {sentToCompliance && !decided && (
          <Card title="Sent to compliance review" tag="Decision" tone="waiting">
            <p className="muted">Medium risk needs a compliance officer. The agent prepared the case.</p>
          </Card>
        )}
        {decided && (
          <Card title="Approved" tag="Decision" tone="done">
            <p>Approved by {d("human_review").approved_by}.</p>
          </Card>
        )}
        {state.memoryRecords.length > 0 && (
          <Card title="Remembered for next time" tag="Memory" wide>
            <ul className="records">
              {state.memoryRecords.map((r, i) => <li key={i}><span className="chip chip-strategy">{r.strategy}</span>{r.text}</li>)}
            </ul>
          </Card>
        )}
        {state.status === "failed" && <Card title="Something went wrong" tag="Error" tone="blocked"><p>{state.error}</p></Card>}
      </section>
      {zoom && (
        <div className="lightbox" onClick={() => setZoom(false)}>
          <img alt="Registry page read by the agent" src={`data:image/png;base64,${d("registry_page").screenshot}`} />
        </div>
      )}
    </div>
  );
}

export function OwnershipBars({ detail }: { detail: Detail }) {
  const ownership: Record<string, number> = detail.ownership ?? {};
  const owners: string[] = detail.beneficial_owners ?? [];
  return (
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
      <p className="muted small">Beneficial owner: more than 25%, directly or through other companies</p>
    </div>
  );
}

function Card({ title, tag, tone, wide, children }: {
  title: string; tag: string; tone?: string; wide?: boolean; children: ReactNode;
}) {
  return (
    <article className={`card ${tone ? `card-${tone}` : ""} ${wide ? "card-wide" : ""}`}>
      <header><span className="card-tag">{tag}</span><h3>{title}</h3></header>
      {children}
    </article>
  );
}

function caseStatus(state: RunState) {
  if (state.status === "failed") return { label: "Error", tone: "blocked", detail: state.error };
  if (state.details.human_review) return { label: "Approved", tone: "done", detail: "Account can be opened" };
  if (state.details.approval?.decision === "DENY")
    return { label: "With compliance", tone: "waiting", detail: "Medium risk: a compliance officer decides" };
  if (state.status === "idle") return { label: "Not started", tone: "pending", detail: "" };
  return { label: "In progress", tone: "active", detail: "The agent is preparing the case" };
}

function stageStatus(state: RunState, steps: string[]) {
  const statuses = steps.map((id) => state.steps.find((s) => s.id === id)?.status ?? "pending");
  if (statuses[statuses.length - 1] === "done") return "done";
  if (statuses.some((s) => s === "waiting" || s === "blocked")) return "waiting";
  if (statuses.some((s) => s !== "pending")) return "active";
  return "pending";
}
