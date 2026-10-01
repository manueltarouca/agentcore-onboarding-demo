// Calls to the backend. URLs are relative so the app also works behind a proxy path.

import type { RunEvent } from "./types";

export type Mode = "live" | "replay";

export async function startRun(mode: Mode, speed: number): Promise<string> {
  const response = await fetch("api/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode, speed }),
  });
  if (!response.ok) throw new Error(`Could not start run (${response.status})`);
  return (await response.json()).run_id;
}

export function streamRun(runId: string, onEvent: (event: RunEvent) => void): () => void {
  const source = new EventSource(`api/runs/${runId}/events`);
  source.onmessage = (message) => {
    const event = JSON.parse(message.data) as RunEvent;
    onEvent(event);
    if (event.type === "run_completed" || event.type === "error") source.close();
  };
  // On a dropped connection the browser reconnects by itself and sends Last-Event-ID,
  // so the server resumes after the last event we saw. Nothing to do here.
  return () => source.close();
}

export async function approve(runId: string): Promise<void> {
  await fetch(`api/runs/${runId}/approve`, { method: "POST" });
}

export type Config = {
  personas: { id: string; label: string; user: string }[];
  steps: import("./types").StepInfo[];
  links: Record<string, string>;
  replay_available: boolean;
};

export async function getConfig(): Promise<Config> {
  return (await fetch("api/config")).json();
}
