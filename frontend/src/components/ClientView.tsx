// What the company applying sees: a customer portal, outside the bank. Status and requests only.
import type { RunState } from "../state/runReducer";
import { clientView } from "../state/clientView";

export function ClientView({ state }: { state: RunState }) {
  const view = clientView(state);
  return (
    <div className="portal">
      <div className="portal-window">
        <header className="portal-header">
          <span className="portal-brand">Business banking</span>
          <span className="portal-user">{state.company || "Lusitania Holdings SGPS"}</span>
        </header>
        <div className="portal-body">
          <p className="portal-eyebrow">Business account application</p>
          {view.stage === "not_started" ? (
            <h2 className="portal-headline portal-muted">No application in progress</h2>
          ) : (
            <>
              <h2 className={`portal-headline portal-${view.stage}`}>{view.headline}</h2>
              <p className="portal-detail">{view.detail}</p>
            </>
          )}
          <ol className="portal-timeline">
            {view.timeline.map((t) => <li key={t.label} className={`portal-step-${t.state}`}>{t.label}</li>)}
          </ol>
          {view.documentsNeeded.length > 0 && (
            <section className="portal-request">
              <h3>Please send</h3>
              <ul>{view.documentsNeeded.map((d) => <li key={d}>{d}</li>)}</ul>
            </section>
          )}
        </div>
      </div>
      <p className="portal-note muted small">The client sees status and requests only. Screening results stay inside the bank.</p>
    </div>
  );
}
