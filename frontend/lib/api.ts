// Typed helpers for the ClaimLens backend. The browser only calls this Next.js app;
// next.config.ts forwards everything under /api to the FastAPI server.

export type ClaimStatus = "pending" | "gathering_evidence" | "debating" | "calibrating" | "resolved" | "failed";
export type Decision = "APPROVE" | "DENY";
export type Tier = "HIGH" | "MEDIUM" | "LOW";
export type Gate = "auto_resolved" | "human_review";

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
  decision: Decision | null;
  confidence_tier: Tier | null;
  gate: Gate | null;
  source: string;
};

export type JudgeRuling = {
  decision: Decision;
  reasoning: string;
  verbalized_confidence: Tier;
  confidence_justification: string;
};

export type CaseDetail = {
  id: number | null;
  claim_id: string;
  status: ClaimStatus;
  error: string | null;
  claim: Claim;
  evidence: Record<string, unknown> | null;
  decision: Decision | null;
  confidence_tier: Tier | null;
  gate: Gate | null;
  auto_resolved: boolean | null;
  tier_before_cap?: Tier | null;
  cap_applied?: boolean | null;
  orderings_agree?: boolean | null;
  transcript: { judge_prosecutor_first?: JudgeRuling; judge_defender_first?: JudgeRuling; [key: string]: unknown } | null;
  stored_sample?: { source: string; note: string };
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

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
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
    throw new ApiError(0, "Could not reach the ClaimLens backend.");
  }
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(response.status, describeError(body, response.status));
  return body as T;
}

export const api = {
  config: () => request<LiveSubmissionState>("/config"),
  samples: () => request<SampleSummary[]>("/samples"),
  sample: (claimId: string) => request<CaseDetail>(`/samples/${encodeURIComponent(claimId)}`),
  submitClaim: (claim: Claim) => request<SubmitResponse>("/claims", { method: "POST", body: JSON.stringify(claim) }),
  status: (id: number) => request<StatusResponse>(`/claims/${id}/status`),
  claim: (id: number) => request<CaseDetail>(`/claims/${id}`),
};
