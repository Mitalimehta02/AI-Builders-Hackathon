"use client";

// Adjuster case view (Stage 9).
// /cases/sample/CLM-0035 shows a stored development-set sample; /cases/claim/12 shows a live submission.

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import CapExplanation from "@/components/CapExplanation";
import ConfidenceGauge from "@/components/ConfidenceGauge";
import DebateTranscript from "@/components/DebateTranscript";
import EvidencePanel from "@/components/EvidencePanel";
import JudgeComparison from "@/components/JudgeComparison";
import PointAccounting from "@/components/PointAccounting";
import { api, type CaseDetail } from "@/lib/api";
import { money, STATUS_LABEL } from "@/lib/labels";

export default function CasePage() {
  const { source, id } = useParams<{ source: string; id: string }>();
  const [detail, setDetail] = useState<CaseDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const request = source === "sample" ? api.sample(id) : source === "claim" ? api.claim(Number(id)) : null;
    const load = request ?? Promise.reject(new Error(`Unknown case type "${source}"`));
    load
      .then((next) => { if (!cancelled) setDetail(next); })
      .catch((reason: Error) => { if (!cancelled) setError(reason.message); });
    return () => { cancelled = true; };
  }, [source, id]);

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-col gap-8 px-6 py-8">
      <Link href="/dashboard" className="text-sm text-sky-700 hover:underline">← Back to the case queue</Link>
      {error && <p className="rounded-md bg-rose-50 p-4 text-sm text-rose-800">{error}</p>}
      {!detail && !error && <p className="text-sm text-zinc-500">Loading…</p>}
      {detail && <CaseView detail={detail} />}
    </main>
  );
}

function CaseView({ detail }: { detail: CaseDetail }) {
  const { claim, transcript } = detail;
  const resolved = detail.status === "resolved";
  return (
    <>
      <header className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold text-zinc-900">Case {detail.claim_id}</h1>
          <span className="rounded bg-zinc-100 px-2 py-0.5 text-xs font-semibold text-zinc-700">
            {detail.stored_sample ? "Stored sample" : "Live submission"}
          </span>
          <span className="rounded bg-zinc-100 px-2 py-0.5 text-xs text-zinc-700">{STATUS_LABEL[detail.status]}</span>
        </div>
        <p className="text-sm text-zinc-700">
          {claim.claim_type === "auto" ? "Auto" : "Property"} claim · {money(claim.claim_amount)} claimed · filed {claim.filed_date} ·{" "}
          {claim.incident.location.city}, {claim.incident.location.state}
        </p>
        {detail.stored_sample && (
          <p className="text-xs text-zinc-500">{detail.stored_sample.note} Produced by: {detail.stored_sample.source}.</p>
        )}
      </header>

      {!resolved && (
        <p className="rounded-md bg-zinc-100 p-4 text-sm text-zinc-700">
          {detail.status === "failed" ? `Processing failed: ${detail.error}` : "This claim is still being processed."}
        </p>
      )}

      {resolved && (
        <section className="grid gap-4 rounded-lg border border-zinc-200 bg-white p-5 md:grid-cols-[1fr_2fr_1fr] md:items-center">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Recommendation</p>
            <p className={`text-2xl font-bold ${detail.decision === "DENY" ? "text-rose-700" : "text-sky-800"}`}>{detail.decision}</p>
          </div>
          <div>
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-zinc-500">Confidence</p>
            <ConfidenceGauge tier={detail.confidence_tier} tierBeforeCap={detail.tier_before_cap} />
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Outcome</p>
            <p className={`text-lg font-bold ${detail.gate === "auto_resolved" ? "text-emerald-700" : "text-zinc-900"}`}>
              {detail.gate === "auto_resolved" ? "Auto-resolved" : "Sent to human review"}
            </p>
            <p className="text-xs text-zinc-500">Only a HIGH-confidence approval resolves without a human. Every denial goes to a person.</p>
          </div>
        </section>
      )}

      {resolved && <CapExplanation detail={detail} />}
      {transcript && <JudgeComparison first={transcript.judge_prosecutor_first} second={transcript.judge_defender_first} />}
      {transcript && <PointAccounting detail={detail} />}
      {transcript && <DebateTranscript transcript={transcript} />}
      <EvidencePanel evidence={detail.evidence} />

      <section className="flex flex-col gap-2 rounded-lg border border-zinc-200 bg-white p-5">
        <h2 className="text-lg font-semibold text-zinc-900">The claim as submitted</h2>
        <p className="text-sm text-zinc-800"><span className="font-medium">What happened:</span> {claim.incident.description}</p>
        <p className="text-sm text-zinc-800"><span className="font-medium">Damage:</span> {claim.incident.damage}</p>
        <p className="text-sm text-zinc-800"><span className="font-medium">Supporting documents:</span></p>
        <ul className="list-disc pl-6 text-sm text-zinc-700">
          {claim.supporting_documents.map((document, index) => <li key={index}>{document}</li>)}
        </ul>
      </section>
    </>
  );
}
