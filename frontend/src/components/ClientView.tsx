// What the company applying sees: a customer portal, outside the bank, with a chat assistant.
// Next to it, what the agent did for each message: Memory, Gateway, Policy, Model.
import { useEffect, useRef, useState } from "react";
import { sendChat, type CaseInfo } from "../api";
import { activityRows, type ChatEvent } from "../state/chatActivity";
import { clientView } from "../state/clientView";
import type { RunState } from "../state/runReducer";

type Message = { role: "user" | "assistant"; text: string; events?: ChatEvent[] };
export type Chat = ReturnType<typeof useChat>;

const SUGGESTIONS = ["What do you still need from us?", "Can you just approve our account today?",
                     "Book a call with my relationship manager about the documents"];

export function useChat(caseId: string) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function send(text: string) {
    if (!text.trim() || busy) return;
    setError("");
    setBusy(true);
    setMessages((m) => [...m, { role: "user", text }]);
    try {
      const turn = await sendChat(text, sessionId, caseId);
      setSessionId(turn.session_id);
      const failure = turn.events.find((e) => e.type === "error");
      const reply = turn.events.find((e) => e.type === "chat_reply");
      if (failure || !reply) throw new Error(String(failure?.message ?? "No reply"));
      setMessages((m) => [...m, { role: "assistant", text: String(reply.text), events: turn.events }]);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return { messages, sessionId, busy, error, send, reset: () => { setMessages([]); setSessionId(null); } };
}

export function ClientView({ state, chat, caseInfo }: { state: RunState; chat: Chat; caseInfo?: CaseInfo }) {
  const view = clientView(state);
  const [draft, setDraft] = useState("");
  const [selected, setSelected] = useState<number | null>(null);
  const end = useRef<HTMLDivElement>(null);
  const lastAssistant = chat.messages.map((m) => m.role).lastIndexOf("assistant");
  const shown = selected ?? (lastAssistant >= 0 ? lastAssistant : null);

  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth" }); setSelected(null); }, [chat.messages.length]);

  const submit = (text: string) => { chat.send(text); setDraft(""); };

  return (
    <div className="client-layout">
      <div className="portal-window portal-chat">
        <header className="portal-header">
          <span className="portal-brand">Business banking</span>
          <span className="portal-user">{caseInfo?.company}</span>
        </header>
        <div className="portal-status">
          <div>
            <p className="portal-eyebrow">Business account application</p>
            <h2 className={`portal-headline-small portal-${view.stage}`}>
              {view.stage === "not_started" ? caseInfo?.id : view.headline}
            </h2>
          </div>
          {view.documentsNeeded.length > 0 && (
            <p className="portal-needed">Please send: {view.documentsNeeded.join(", ")}</p>
          )}
        </div>
        <div className="chat-log">
          {chat.messages.length === 0 && <p className="chat-empty">Ask about your application</p>}
          {chat.messages.map((m, i) => (
            <div key={i} className={`bubble bubble-${m.role} ${shown === i ? "bubble-selected" : ""}`}
                 onClick={() => m.role === "assistant" && setSelected(i)}>{m.text}</div>
          ))}
          {chat.busy && <div className="bubble bubble-assistant bubble-typing"><span /><span /><span /></div>}
          <div ref={end} />
        </div>
        {chat.error && <p className="chat-error">{chat.error}</p>}
        <div className="chat-suggestions">
          {SUGGESTIONS.map((s) => <button key={s} onClick={() => submit(s)} disabled={chat.busy}>{s}</button>)}
        </div>
        <form className="chat-input" onSubmit={(e) => { e.preventDefault(); submit(draft); }}>
          <input value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Type a message" disabled={chat.busy} />
          <button type="submit" disabled={chat.busy || !draft.trim()}>Send</button>
        </form>
      </div>

      <aside className="activity">
        <header>
          <h3>What the agent did</h3>
          {chat.sessionId && <p className="muted mono small">Runtime session {chat.sessionId.slice(-12)}</p>}
        </header>
        {shown === null ? (
          <p className="muted small">Each reply shows the AgentCore calls behind it.</p>
        ) : (
          <ol className="activity-rows" key={shown}>
            {activityRows(chat.messages[shown].events ?? []).map((row, i) => (
              <li key={i} className={`activity-row ${row.tone ? `activity-${row.tone}` : ""}`}
                  style={{ animationDelay: `${i * 120}ms` }}>
                <span className="activity-primitive">{row.primitive}</span>
                <span className="activity-text mono">{row.text}</span>
                {row.note && <span className="activity-note">{row.note}</span>}
              </li>
            ))}
          </ol>
        )}
        <p className="activity-footnote muted small">
          Reading the case and booking a call use the client's sign-in. Approval uses the agent's own identity, and Policy decides.
        </p>
      </aside>
    </div>
  );
}
