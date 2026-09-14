"use client";

// Basic case result page, the destination of the intake page's "View case" links.
// /cases/sample/CLM-0035 shows a stored sample; /cases/claim/12 shows a live submission.
// The full adjuster case view (readable evidence and transcript) is built in Stage 9.

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import ResultSummary from "@/components/ResultSummary";
import { api, type CaseDetail, type JudgeRuling } from "@/lib/api";

export default function CasePage() {
  const { source, id } = useParams<{ source: string; id: string }>();
  const [detail, setDetail] = useState<CaseDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const request = source === "sample" ? api.sample(id) : source === "claim" ? api.claim(Number(id)) : null;
    if (!request) {
      Promise.resolve().then(() => { if (!cancelled) setError(`Unknown case type "${source}"`); });
      return () => { cancelled = true; };
    }
    request
      .then((next) => { if (!cancelled) setDetail(next); })
      .catch((reason: Error) => { if (!cancelled) setError(reason.message); });
    return () => { cancelled = true; };
  }, [source, id]);

  return (
    <main className="mx-auto flex w-full max-w-4xl flex-col gap-6 px-6 py-8">
      <Link href="/intake" className="text-sm text-sky-700 hover:underline">← Back to intake</Link>
      {error && <p className="rounded-md bg-rose-50 p-4 text-sm text-rose-800">{error}</p>}
      {!detail && !error && <p className="text-sm text-zinc-500">Loading…</p>}
      {detail && (
        <>
          <header>
            <h1 className="text-2xl font-semibold text-zinc-900">Case {detail.claim_id}</h1>
            <p className="text-sm text-zinc-600">
              {detail.claim.claim_type} claim · ${detail.claim.claim_amount.toLocaleString()} · status {detail.status}
            </p>
            {detail.stored_sample && (
              <p className="mt-2 text-xs text-zinc-500">{detail.stored_sample.note} Produced by: {detail.stored_sample.source}.</p>
            )}
          </header>

          {detail.status === "resolved" ? (
            <section className="rounded-lg border border-zinc-200 bg-white p-5">
              <ResultSummary {...detail} />
            </section>
          ) : (
            <p className="rounded-md bg-zinc-100 p-4 text-sm text-zinc-700">
              {detail.status === "failed" ? `Processing failed: ${detail.error}` : "This claim is still being processed."}
            </p>
          )}

          <section className="rounded-lg border border-zinc-200 bg-white p-5">
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-zinc-500">What happened</h2>
            <p className="text-sm text-zinc-800">{detail.claim.incident.description}</p>
            <p className="mt-2 text-sm text-zinc-600">Damage: {detail.claim.incident.damage}</p>
          </section>

          {detail.transcript?.judge_prosecutor_first && (
            <section className="grid gap-4 md:grid-cols-2">
              <Ruling title="Judge — prosecutor's argument first" ruling={detail.transcript.judge_prosecutor_first} />
              {detail.transcript.judge_defender_first && (
                <Ruling title="Judge — defender's argument first" ruling={detail.transcript.judge_defender_first} />
              )}
            </section>
          )}

          <details className="rounded-lg border border-zinc-200 bg-white p-5">
            <summary className="cursor-pointer text-sm font-semibold text-zinc-800">Evidence (raw)</summary>
            <pre className="mt-3 overflow-x-auto text-xs text-zinc-700">{JSON.stringify(detail.evidence, null, 2)}</pre>
          </details>
          <details className="rounded-lg border border-zinc-200 bg-white p-5">
            <summary className="cursor-pointer text-sm font-semibold text-zinc-800">Full debate transcript (raw)</summary>
            <pre className="mt-3 overflow-x-auto text-xs text-zinc-700">{JSON.stringify(detail.transcript, null, 2)}</pre>
          </details>
        </>
      )}
    </main>
  );
}

function Ruling({ title, ruling }: { title: string; ruling: JudgeRuling }) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-5">
      <h3 className="text-sm font-semibold text-zinc-900">{title}</h3>
      <p className="mt-1 text-sm font-medium text-zinc-700">{ruling.decision} · {ruling.verbalized_confidence}</p>
      <p className="mt-2 text-sm text-zinc-700">{ruling.reasoning}</p>
      <p className="mt-2 text-xs text-zinc-500">Why this confidence: {ruling.confidence_justification}</p>
    </div>
  );
}
