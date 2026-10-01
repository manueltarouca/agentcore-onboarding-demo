import { useEffect, useReducer, useRef, useState } from "react";
import { approve, getConfig, startRun, streamRun, type Config, type Mode } from "./api";
import { ClientView, useChat } from "./components/ClientView";
import { ComplianceView } from "./components/ComplianceView";
import { ObservabilityStrip } from "./components/ObservabilityStrip";
import { RelationshipManagerView } from "./components/RelationshipManagerView";
import { StepDetail } from "./components/StepDetail";
import { Trace } from "./components/Trace";
import { WorkflowDiagram } from "./components/WorkflowDiagram";
import { initialState, runReducer, type RunState } from "./state/runReducer";

type Persona = "client" | "relationship_manager" | "compliance" | "engineering";

export function App() {
  const [state, dispatch] = useReducer(runReducer, initialState);
  const chat = useChat();
  const [config, setConfig] = useState<Config | null>(null);
  const [persona, setPersona] = useState<Persona>("engineering");
  const [mode, setMode] = useState<Mode>("live");
  const [speed, setSpeed] = useState(1);
  const [pinned, setPinned] = useState<string | null>(null);
  const [tab, setTab] = useState<"step" | "trace">("step");
  const [error, setError] = useState("");
  const runId = useRef<string | null>(null);
  const stop = useRef<() => void>(() => {});
  const running = state.status === "running" || state.status === "awaiting_approval";
  const elapsed = useElapsed(running);

  useEffect(() => {
    getConfig().then(setConfig).catch(() => setError("Backend not reachable"));
  }, []);

  async function run() {
    stop.current();
    setError("");
    setPinned(null);
    try {
      runId.current = await startRun(mode, speed);
      elapsed.reset();
      stop.current = streamRun(runId.current, dispatch);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const onApprove = () => runId.current && approve(runId.current);
  const links = config?.links ?? {};
  const diagramSteps = state.steps.length
    ? state.steps
    : (config?.steps ?? []).map((s) => ({ ...s, status: "pending" as const }));
  const shownStep = pinned ?? state.activeStep ?? lastStarted(state) ?? diagramSteps[0]?.id ?? null;

  return (
    <div className="app">
      <header className="topbar">
        <div className="title">
          <strong>Business onboarding</strong>
          <span className="muted">Amazon Bedrock AgentCore</span>
        </div>
        <nav className="personas">
          {(config?.personas ?? []).map((p) => (
            <button key={p.id} className={persona === p.id ? "active" : ""} onClick={() => setPersona(p.id as Persona)}>
              {p.label}
              {p.id === "compliance" && state.status === "awaiting_approval" && <span className="badge">1</span>}
            </button>
          ))}
        </nav>
        <div className="controls">
          <Segmented value={mode} options={["live", "replay"]} onChange={(v) => setMode(v as Mode)} />
          {mode === "replay" && (
            <Segmented value={String(speed)} options={["1", "2"]} labels={["1x", "2x"]} onChange={(v) => setSpeed(Number(v))} />
          )}
          <button className={`primary ${state.status === "awaiting_approval" ? "primary-waiting" : ""}`}
                  onClick={run} disabled={running}>{runLabel(state.status)}</button>
        </div>
      </header>

      {(error || state.status === "failed") && <div className="error">{error || state.error}</div>}

      {persona === "client" && <main className="main-single"><ClientView state={state} chat={chat} /></main>}
      {persona === "relationship_manager" && <main className="main-single"><RelationshipManagerView state={state} /></main>}
      {persona === "compliance" && <main className="main-single"><ComplianceView state={state} onApprove={onApprove} /></main>}
      {persona === "engineering" && (
        <main className="main">
          <div className="canvas">
            <WorkflowDiagram steps={diagramSteps} activeStep={state.activeStep} sessionId={state.sessionId}
                             waiting={state.status === "awaiting_approval"} selected={shownStep} onSelect={setPinned} />
          </div>
          <aside className="panel">
            <nav className="tabs">
              <button className={tab === "step" ? "active" : ""} onClick={() => setTab("step")}>Step</button>
              <button className={tab === "trace" ? "active" : ""} onClick={() => setTab("trace")}>Trace</button>
            </nav>
            {tab === "trace"
              ? <Trace state={state} observabilityLink={links["Observability"]} />
              : shownStep && <StepDetail state={{ ...state, steps: diagramSteps }} stepId={shownStep} links={links}
                                         onApprove={onApprove} />}
          </aside>
        </main>
      )}

      <ObservabilityStrip state={state} elapsedMs={elapsed.ms} />
    </div>
  );
}

function runLabel(status: RunState["status"]): string {
  return { idle: "Run case", running: "Running", awaiting_approval: "Waiting for approval",
           completed: "Run again", failed: "Run again" }[status];
}

function lastStarted(state: RunState): string | null {
  const started = state.steps.filter((s) => s.status !== "pending");
  return started.length ? started[started.length - 1].id : null;
}

function useElapsed(active: boolean) {
  const [ms, setMs] = useState(0);
  const start = useRef(Date.now());
  useEffect(() => {
    if (!active) return;
    const timer = setInterval(() => setMs(Date.now() - start.current), 100);
    return () => clearInterval(timer);
  }, [active]);
  return { ms, reset: () => { start.current = Date.now(); setMs(0); } };
}

function Segmented({ value, options, labels, onChange }: {
  value: string; options: string[]; labels?: string[]; onChange: (v: string) => void;
}) {
  return (
    <div className="segmented">
      {options.map((o, i) => (
        <button key={o} className={o === value ? "active" : ""} onClick={() => onChange(o)}>
          {labels?.[i] ?? o[0].toUpperCase() + o.slice(1)}
        </button>
      ))}
    </div>
  );
}
