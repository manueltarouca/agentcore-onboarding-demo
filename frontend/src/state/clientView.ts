// What the client (the company applying) sees. Built from the same events as the other views,
// but it only exposes status and requests: never screening results, risk or the internal review.
// Telling a customer they are under suspicion is "tipping off", which anti-money-laundering rules forbid.

import type { RunState } from "./runReducer";

export type ClientStage = "not_started" | "submitted" | "in_review" | "approved" | "delayed";
type TimelineState = "pending" | "active" | "done";

export type ClientView = {
  stage: ClientStage;
  headline: string;
  detail: string;
  documentsNeeded: string[];
  timeline: { label: string; state: TimelineState }[];
};

const COPY: Record<ClientStage, [string, string]> = {
  not_started: ["", ""],
  submitted: ["Application received", "We are checking your documents."],
  in_review: ["Under review", "We will contact you if we need anything else."],
  approved: ["Approved", "Your account opens once we receive the documents below."],
  delayed: ["Taking longer than usual", "We will contact you shortly."],
};

export function clientView(state: RunState): ClientView {
  const documentsChecked = Boolean(state.details.intake);
  const approved = Boolean(state.details.human_review) || state.details.approval?.decision === "ALLOW";
  const stage: ClientStage =
    state.status === "idle" ? "not_started"
    : state.status === "failed" ? "delayed"
    : approved ? "approved"
    : documentsChecked ? "in_review"
    : "submitted";
  const documentsNeeded = ((state.details.intake?.missing as string[] | undefined) ?? []).map(String);
  const [headline, detail] = COPY[stage];
  return {
    stage,
    headline,
    detail: approved && documentsNeeded.length === 0 ? "Your account is ready." : detail,
    documentsNeeded,
    timeline: [
      { label: "Application received", state: stage === "not_started" ? "pending" : "done" },
      { label: "Documents checked", state: documentsChecked ? "done" : stage === "submitted" ? "active" : "pending" },
      { label: "Review", state: approved ? "done" : documentsChecked ? "active" : "pending" },
      { label: "Decision", state: approved ? "done" : "pending" },
    ],
  };
}
