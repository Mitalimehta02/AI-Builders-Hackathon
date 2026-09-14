// Human-readable labels and colours shared by the dashboard, case view and analytics pages.

import type { ClaimStatus, Gate, PointStatus, Tier } from "@/lib/api";

export const STATUS_LABEL: Record<ClaimStatus, string> = {
  pending: "Queued",
  gathering_evidence: "Gathering evidence",
  debating: "Debating",
  calibrating: "Calibrating",
  resolved: "Resolved",
  failed: "Failed",
};

export const TIER_STYLE: Record<Tier, string> = {
  HIGH: "bg-emerald-100 text-emerald-800",
  MEDIUM: "bg-amber-100 text-amber-900",
  LOW: "bg-rose-100 text-rose-800",
};

export const GATE_LABEL: Record<Gate, string> = {
  auto_resolved: "Auto-resolved",
  human_review: "Human review",
};

export const POINT_STATUS_LABEL: Record<PointStatus, string> = {
  answered_with_case_file_fact: "Answered with a case-file fact",
  answered_by_assertion_only: "Answered by assertion only",
  conceded: "Conceded",
  unanswered: "Unanswered",
  not_assessed: "Not assessed by the judge",
};

export const POINT_STATUS_STYLE: Record<PointStatus, string> = {
  answered_with_case_file_fact: "bg-emerald-100 text-emerald-800",
  answered_by_assertion_only: "bg-amber-100 text-amber-900",
  conceded: "bg-rose-100 text-rose-800",
  unanswered: "bg-rose-100 text-rose-800",
  not_assessed: "bg-zinc-200 text-zinc-700",
};

export const ORDERING_LABEL = {
  prosecutor_first: "Prosecutor's argument shown first",
  defender_first: "Defender's argument shown first",
} as const;

export function money(value: number): string {
  return `$${value.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}

export function days(value: number): string {
  return `${value} day${value === 1 ? "" : "s"}`;
}
