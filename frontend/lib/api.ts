// Typed helpers for the ClaimLens backend. The browser only calls this Next.js app;
// next.config.ts forwards everything under /api to the FastAPI server.

export type ClaimStatus = "pending" | "gathering_evidence" | "debating" | "calibrating" | "resolved" | "failed";
export type Decision = "APPROVE" | "DENY";
export type Tier = "HIGH" | "MEDIUM" | "LOW";
export type Gate = "auto_resolved" | "human_review";
export type PointStatus = "answered_with_case_file_fact" | "answered_by_assertion_only" | "conceded" | "unanswered" | "not_assessed";

export type Address = { street: string; city: string; state: string };

export type Claim = {
  claim_id?: string;
  claim_type: "auto" | "property";
  filed_date: string;
  claim_amount: number;
  policyholder: { address: Address; [key: string]: unknown };
  policy: {
    policy_number: string;
    policy_type: string;
    start_date: string;
    deductible: number;
    coverages?: string[];
    insured_vehicle?: { year: number; make: string; model: string; estimated_value: number; license_plate?: string };
    insured_property?: Address & { property_type: string; year_built: number };
    dwelling_coverage?: number;
    contents_coverage?: number;
    [key: string]: unknown;
  };
  incident: {
    date: string;
    location: Address & { latitude?: number; longitude?: number };
    description: string;
    damage: string;
  };
  supporting_documents: string[];
  [key: string]: unknown;
};

// The Stage 3 evidence object (all fields optional so older stored results still render).
export type Evidence = {
  timeline?: {
    incident_date?: string;
    filed_date?: string;
    policy_start_date?: string;
    days_incident_to_filing?: number;
    days_policy_start_to_incident?: number;
    days_last_policy_change_to_incident?: number | null;
  };
  policy?: {
    type?: string;
    coverages?: string[];
    vehicle?: string;
    vehicle_estimated_value?: number;
    claim_amount_pct_of_vehicle_value?: number;
    property?: string;
    dwelling_coverage?: number;
    contents_coverage?: number;
    changes?: { days_before_incident: number; change: string }[];
  };
  claim_history?: {
    prior_claims_count?: number;
    prior_claims_last_24_months?: number;
    prior_claims?: {
      days_before_incident: number;
      claim_type: string;
      summary: string;
      amount: number;
      insurer: string;
      words_shared_with_this_claim: string[];
    }[];
  };
  location?: {
    incident_location?: string;
    policyholder_home?: string;
    same_city_as_home?: boolean;
    same_state_as_home?: boolean;
    incident_address_matches_insured_property?: boolean;
  };
  documents?: {
    documents_provided?: number;
    documents_mentioned_but_absent?: string[];
    expected_but_not_found?: string[];
    listed_as_not_yet_provided?: string[];
    dated_documents?: { document: string; days_relative_to_incident: number }[];
  };
  weather?: {
    status?: string;
    reason?: string;
    source?: string;
    dates_checked?: string;
    lowest_temp_c?: number;
    highest_temp_c?: number;
    days_with_low_below_freezing?: number;
    total_precipitation_mm?: number;
    total_snowfall_cm?: number;
    weather_terms_in_description?: string[];
  };
};

export type Point = { id: string; point: string; evidence: string };
export type ProsecutorArgument = { points: Point[]; summary: string };
export type DefenderArgument = {
  responses: { responds_to: string; position: string; response: string; evidence: string }[];
  points: Point[];
  summary: string;
};
export type RebuttalArgument = { rebuttals: { responds_to: string; rebuttal: string; evidence: string }[]; summary: string };
export type PointAssessment = { point_id: string; significant: boolean; status: PointStatus };
export type UnresolvedPoint = { point_id: string; status: PointStatus };

export type JudgeRuling = {
  decision: Decision;
  reasoning: string;
  verbalized_confidence: Tier;
  confidence_justification: string;
  point_assessments?: PointAssessment[];
};

export type Transcript = {
  prosecutor?: ProsecutorArgument;
  defender?: DefenderArgument;
  prosecutor_rebuttal?: RebuttalArgument;
  judge_prosecutor_first?: JudgeRuling;
  judge_defender_first?: JudgeRuling;
};

export type CaseDetail = {
  id: number | null;
  claim_id: string;
  status: ClaimStatus;
  error: string | null;
  claim: Claim;
  evidence: Evidence | null;
  decision: Decision | null;
  confidence_tier: Tier | null;
  gate: Gate | null;
  auto_resolved: boolean | null;
  tier_before_cap?: Tier | null;
  cap_applied?: boolean | null;
  orderings_agree?: boolean | null;
  unresolved_points?: { prosecutor_first: UnresolvedPoint[]; defender_first: UnresolvedPoint[] } | null;
  transcript: Transcript | null;
  stored_sample?: { source: string; note: string };
};

export type LiveSubmissionState = {
  live_submission_enabled: boolean;
  batch_running: boolean;
  override_active: boolean;
  reason: string | null;
  estimated_tokens_per_live_claim: number;
  batch: {
    claims_finished?: number | null;
    claims_total?: number | null;
    current_claim?: string | null;
    waiting_until?: string | null;
    updated_at?: string | null;
  } | null;
};

export type SampleSummary = {
  claim_id: string;
  claim_type: "auto" | "property";
  claim_amount: number;
  description: string;
  status: ClaimStatus;
  decision: Decision | null;
  confidence_tier: Tier | null;
  gate: Gate | null;
  cap_applied: boolean | null;
  source: string;
};

export type ClaimSummary = {
  id: number;
  claim_id: string;
  claim_type: "auto" | "property";
  claim_amount: number;
  status: ClaimStatus;
  decision: Decision | null;
  confidence_tier: Tier | null;
  gate: Gate | null;
  cap_applied: boolean | null;
  created_at: string;
  updated_at: string;
};

export type StatusResponse = {
  id: number;
  claim_id: string;
  status: ClaimStatus;
  steps_completed: string[];
  error: string | null;
  updated_at: string;
};

export type SubmitResponse = { id: number; claim_id: string; status: ClaimStatus; status_url: string };

export type SystemMetrics = {
  correct: number;
  high_confidence: number;
  high_confidence_wrong: number;
  false_positives: number;
  false_negatives: number;
  fraud_amount_caught: number;
  fraud_amount_total: number;
  high_confidence_rule: string;
};

export type Analytics = {
  evaluation: {
    sample_size: number;
    held_out_size: number;
    registered_on: string;
    seed: number;
    claim_ids_sha256: string;
    processing_order: string;
    model: string | null;
    settings: { temperature?: number; reasoning_effort?: string } | null;
  };
  progress: {
    total: number;
    complete: number;
    failed: number;
    in_progress: number;
    not_started: number;
    reported: number;
    is_final: boolean;
    batch_running: boolean;
    waiting_until: string | null;
  };
  composition: { fraud: number; legitimate: number };
  reference: { always_approve_correct: number; out_of: number; full_sample_always_approve_correct: number; full_sample_size: number };
  baseline: SystemMetrics;
  claimlens: SystemMetrics & {
    auto_resolved: number;
    auto_resolved_fraud: number;
    human_review: number;
    tier_counts: Record<Tier, number>;
    tier_before_cap_high: number;
    tier_before_cap_high_wrong: number;
    cap_applied: number;
    cap_applied_on_wrong_decisions: number;
    orderings_disagreed: number;
    manual_review_minutes_assumed: number;
    adjuster_hours_saved: number;
  };
  notes: string[];
};

export type QueueFilters = { status?: string; confidence_tier?: string; gate?: string };

export class ApiError extends Error {
  status: number;
  unreachable: boolean; // true when the backend did not answer at all (down, or still waking up)

  constructor(status: number, message: string, unreachable = false) {
    super(message);
    this.status = status;
    this.unreachable = unreachable;
  }
}

type ValidationItem = { loc?: unknown[]; msg?: string };

// FastAPI errors come back as {"detail": "text"} or {"detail": [{loc, msg}, ...]}.
function describeError(body: unknown, status: number): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return (detail as ValidationItem[])
        .map((item) => {
          const where = (item.loc ?? []).filter((part) => part !== "body").join(".");
          return where ? `${where}: ${item.msg}` : String(item.msg);
        })
        .join("; ");
    }
  }
  return `Request failed (HTTP ${status})`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      cache: "no-store",
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError(0, "Could not reach the ClaimLens backend.", true);
  }
  const body: unknown = await response.json().catch(() => null);
  // A non-JSON 5xx comes from the /api proxy when the backend itself isn't answering.
  if (!response.ok && body === null && response.status >= 500) {
    throw new ApiError(response.status, "The ClaimLens backend is not responding.", true);
  }
  if (!response.ok) throw new ApiError(response.status, describeError(body, response.status));
  return body as T;
}

function queryString(filters: QueueFilters): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value) params.set(key, value);
  }
  const text = params.toString();
  return text ? `?${text}` : "";
}

export const api = {
  config: () => request<LiveSubmissionState>("/config"),
  samples: () => request<SampleSummary[]>("/samples"),
  sample: (claimId: string) => request<CaseDetail>(`/samples/${encodeURIComponent(claimId)}`),
  claims: (filters: QueueFilters = {}) => request<ClaimSummary[]>(`/claims${queryString(filters)}`),
  submitClaim: (claim: Claim) => request<SubmitResponse>("/claims", { method: "POST", body: JSON.stringify(claim) }),
  status: (id: number) => request<StatusResponse>(`/claims/${id}/status`),
  claim: (id: number) => request<CaseDetail>(`/claims/${id}`),
  analytics: () => request<Analytics>("/analytics"),
};
