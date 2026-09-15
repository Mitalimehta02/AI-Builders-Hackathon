"use client";

// Adjuster case view (Stage 9).
// /cases/sample/CLM-0040 shows a stored Stage 11 evaluation result; /cases/claim/12 shows a live submission.

import Link from "next/link";
import { useParams } from "next/navigation";
import CapExplanation from "@/components/CapExplanation";
import ConfidenceGauge from "@/components/ConfidenceGauge";
import DebateTranscript from "@/components/DebateTranscript";
import EvidencePanel from "@/components/EvidencePanel";
import JudgeComparison from "@/components/JudgeComparison";
import PointAccounting from "@/components/PointAccounting";
import { Card, EmptyState, ErrorState, LoadingState, Page } from "@/components/ui";
import { api, ApiError, type CaseDetail } from "@/lib/api";
import { money, STATUS_LABEL } from "@/lib/labels";
import { useApi } from "@/lib/useApi";

export default function CasePage() {
  const { source, id } = useParams<{ source: string; id: string }>();
  const knownSource = source === "sample" || source === "claim";
  const detail = useApi(`case:${source}:${id}`, () =>
    source === "sample" ? api.sample(id) : api.claim(Number(id)),
  );
  const notFound = !knownSource || (detail.error instanceof ApiError && (detail.error.status === 404 || detail.error.status === 422));

  return (
    <Page>
      <Link href="/dashboard" className="text-sm font-medium text-sky-800 hover:underline">← Back to the case queue</Link>
      {notFound && (
        <EmptyState title="Case not found">There is no {source === "sample" ? "stored sample" : "claim"} called &ldquo;{id}&rdquo;.</EmptyState>
      )}
      {!notFound && detail.error && <ErrorState error={detail.error} onRetry={detail.reload} />}
      {!notFound && !detail.error && !detail.data && <LoadingState label="Loading the case…" />}
      {!notFound && detail.data && <CaseView detail={detail.data} />}
    </Page>
  );
}

function CaseView({ detail }: { detail: CaseDetail }) {
  const { claim, transcript } = detail;
  const resolved = detail.status === "resolved";
  return (
    <>
      <header className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-2xl font-semibold text-zinc-900">Case {detail.claim_id}</h1>
          <span className="rounded bg-zinc-200 px-2 py-0.5 text-xs font-semibold text-zinc-800">
            {detail.stored_sample ? "Stored sample" : "Live submission"}
          </span>
          <span className="rounded bg-zinc-200 px-2 py-0.5 text-xs text-zinc-800">{STATUS_LABEL[detail.status]}</span>
        </div>
        <p className="text-sm text-zinc-700">
          {claim.claim_type === "auto" ? "Auto" : "Property"} claim · {money(claim.claim_amount)} claimed · filed {claim.filed_date} ·{" "}
          {claim.incident.location.city}, {claim.incident.location.state}
        </p>
        {detail.stored_sample && (
          <p className="text-xs text-zinc-600">{detail.stored_sample.note} Produced by: {detail.stored_sample.source}.</p>
        )}
      </header>

      {detail.status === "failed" && (
        <div role="alert" className="rounded-lg border-2 border-rose-400 bg-rose-50 p-4 text-sm text-rose-900">
          <p className="text-base font-semibold">Processing failed before a decision was reached</p>
          <p className="mt-1 [overflow-wrap:anywhere]">{detail.error}</p>
          <p className="mt-1">No recommendation was made, so this claim needs a human adjuster. Evidence gathered before the failure is shown below.</p>
        </div>
      )}
      {!resolved && detail.status !== "failed" && (
        <LoadingState label={`This claim is still being processed (${STATUS_LABEL[detail.status].toLowerCase()}). Reload the page to check again.`} />
      )}

      {resolved && (
        <Card>
          <div className="grid gap-5 md:grid-cols-[1fr_2fr_1fr] md:items-center">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-zinc-600">Recommendation</p>
              <p className={`text-2xl font-bold ${detail.decision === "DENY" ? "text-rose-800" : "text-sky-800"}`}>{detail.decision}</p>
            </div>
            <div>
              <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-zinc-600">Confidence</p>
              <ConfidenceGauge tier={detail.confidence_tier} tierBeforeCap={detail.tier_before_cap} />
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-zinc-600">Outcome</p>
              <p className={`text-lg font-bold ${detail.gate === "auto_resolved" ? "text-emerald-800" : "text-zinc-900"}`}>
                {detail.gate === "auto_resolved" ? "Auto-resolved" : "Sent to human review"}
              </p>
              <p className="text-xs text-zinc-600">Only a HIGH-confidence approval resolves without a human. Every denial goes to a person.</p>
            </div>
          </div>
        </Card>
      )}

      {resolved && <CapExplanation detail={detail} />}
      {transcript && <JudgeComparison first={transcript.judge_prosecutor_first} second={transcript.judge_defender_first} />}
      {transcript && <PointAccounting detail={detail} />}
      {transcript && <DebateTranscript transcript={transcript} />}
      <EvidencePanel evidence={detail.evidence} />

      <Card title="The claim as submitted">
        <p className="text-sm text-zinc-800"><span className="font-semibold">What happened:</span> {claim.incident.description}</p>
        <p className="text-sm text-zinc-800"><span className="font-semibold">Damage:</span> {claim.incident.damage}</p>
        <div className="text-sm text-zinc-800">
          <p className="font-semibold">Supporting documents:</p>
          {claim.supporting_documents.length ? (
            <ul className="list-disc pl-6 text-zinc-700">
              {claim.supporting_documents.map((document, index) => <li key={index}>{document}</li>)}
            </ul>
          ) : (
            <p className="text-zinc-700">None submitted.</p>
          )}
        </div>
      </Card>
    </>
  );
}
