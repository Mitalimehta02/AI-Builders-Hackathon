"use client";

// Portfolio analytics (Stage 10): Part 5 metrics on the pre-registered evaluation sample.
// Part 5b reporting rules: raw counts only, the always-approve line beside every accuracy figure,
// sample size and pre-registration stated on the page, and "N of 15 complete" while the batch runs.

import { useEffect, useState, type ReactNode } from "react";
import { api, type Analytics } from "@/lib/api";
import { money } from "@/lib/labels";

const REFRESH_MS = 60_000;

export default function AnalyticsPage() {
  const [data, setData] = useState<Analytics | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = () =>
      api.analytics()
        .then((next) => { if (!cancelled) { setData(next); setError(null); } })
        .catch((reason: Error) => { if (!cancelled) setError(reason.message); });
    load();
    const timer = setInterval(load, REFRESH_MS);
    return () => { cancelled = true; clearInterval(timer); };
  }, []);

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-6 py-8">
      <header>
        <h1 className="text-2xl font-semibold text-zinc-900">Portfolio analytics</h1>
        <p className="text-sm text-zinc-600">Naive single-pass baseline vs. ClaimLens, on the same claims, model and settings.</p>
      </header>
      {error && <p className="rounded-md bg-rose-50 p-4 text-sm text-rose-800">{error}</p>}
      {!data && !error && <p className="text-sm text-zinc-500">Loading…</p>}
      {data && <AnalyticsView data={data} />}
    </main>
  );
}

function AnalyticsView({ data }: { data: Analytics }) {
  const { progress, evaluation, reference, baseline, claimlens: lens, composition } = data;
  const n = progress.complete;

  return (
    <>
      {/* ---- Progress and pre-registration: always first ---- */}
      <section className={`rounded-lg border-2 p-5 ${progress.is_final ? "border-emerald-400 bg-emerald-50" : "border-amber-400 bg-amber-50"}`}>
        <p className="text-xs font-semibold uppercase tracking-wide text-zinc-600">{progress.is_final ? "Final" : "Interim — evaluation still running"}</p>
        <p className="mt-1 text-3xl font-bold text-zinc-900">{progress.complete} of {progress.total} claims complete</p>
        <p className="mt-1 text-sm text-zinc-800">
          {progress.failed > 0 && `${progress.failed} failed · `}
          {progress.in_progress} in progress · {progress.not_started} not started
          {progress.waiting_until && ` · batch waiting for the daily model allowance until ${new Date(progress.waiting_until).toLocaleTimeString()}`}
        </p>
        {!progress.is_final && (
          <p className="mt-2 text-sm font-medium text-amber-900">These counts will change as the batch continues. They are not final results.</p>
        )}
        <p className="mt-3 text-sm text-zinc-700">
          <span className="font-semibold">Pre-registered sample:</span> {evaluation.sample_size} of the {evaluation.held_out_size} held-out
          claims, chosen by stratified random sampling (seed {evaluation.seed}) on {evaluation.registered_on}, before any held-out claim
          was run. None of these claims was used to develop the system. Processing order: {evaluation.processing_order}. ID list
          SHA-256 {evaluation.claim_ids_sha256.slice(0, 12)}….
        </p>
        <p className="mt-1 text-sm text-zinc-700">
          Completed so far: {composition.fraud} fraud and {composition.legitimate} legitimate claims · model {evaluation.model ?? "—"},
          temperature {evaluation.settings?.temperature ?? "—"}. With a sample this small, every figure below is a raw count.
        </p>
      </section>

      {data.notes.length > 0 && (
        <ul className="flex flex-col gap-1 rounded-lg border border-zinc-200 bg-white p-4 text-sm text-zinc-700">
          {data.notes.map((note, index) => <li key={index}>• {note}</li>)}
        </ul>
      )}

      {n === 0 ? (
        <p className="rounded-lg border border-zinc-200 bg-white p-6 text-sm text-zinc-600">No claims are complete yet, so there is nothing to count.</p>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          <Card title="Decision accuracy" subtitle={`Correct recommendations out of ${n} completed claims`}>
            <Bar label="Baseline" count={baseline.correct} outOf={n} color="bg-zinc-500" />
            <Bar label="ClaimLens" count={lens.correct} outOf={n} color="bg-sky-600" />
            <Bar label="Always approve (reference)" count={reference.always_approve_correct} outOf={n} color="bg-zinc-300" />
            <p className="text-xs text-zinc-500">
              Always answering APPROVE would be right on {reference.always_approve_correct} of these {n}, and on{" "}
              {reference.full_sample_always_approve_correct} of all {reference.full_sample_size} sample claims.
            </p>
          </Card>

          <Card title="Confidently wrong" subtitle="Wrong answers among high-confidence answers — the headline metric">
            <Count label="Baseline" main={`${baseline.high_confidence_wrong} wrong`} detail={`of ${baseline.high_confidence} high-confidence answers (${baseline.high_confidence_rule})`} />
            <Count label="ClaimLens" main={`${lens.high_confidence_wrong} wrong`} detail={`of ${lens.high_confidence} answers with final tier HIGH`} />
            <Count label="ClaimLens before the cap" main={`${lens.tier_before_cap_high_wrong} wrong`}
              detail={`of ${lens.tier_before_cap_high} answers where both judge rulings said HIGH`} />
            <p className="text-xs text-zinc-500">
              The confidence cap fired on {lens.cap_applied} claim{lens.cap_applied === 1 ? "" : "s"}, {lens.cap_applied_on_wrong_decisions} of
              which had a wrong recommendation.
            </p>
          </Card>

          <Card title="Auto-resolution" subtitle="ClaimLens only auto-resolves HIGH-tier approvals">
            <Bar label="Auto-resolved" count={lens.auto_resolved} outOf={n} color="bg-emerald-600" />
            <Bar label="Sent to human review" count={lens.human_review} outOf={n} color="bg-zinc-400" />
            <p className={`text-sm ${lens.auto_resolved_fraud > 0 ? "font-semibold text-rose-700" : "text-zinc-600"}`}>
              Fraud claims auto-resolved: {lens.auto_resolved_fraud} of {lens.auto_resolved}
            </p>
          </Card>

          <Card title="Confidence tiers" subtitle="ClaimLens final tier, and how often the judge's two orderings disagreed">
            <Bar label="HIGH" count={lens.tier_counts.HIGH} outOf={n} color="bg-emerald-600" />
            <Bar label="MEDIUM" count={lens.tier_counts.MEDIUM} outOf={n} color="bg-amber-500" />
            <Bar label="LOW" count={lens.tier_counts.LOW} outOf={n} color="bg-rose-600" />
            <p className="text-xs text-zinc-500">Orderings disagreed on {lens.orderings_disagreed} claim{lens.orderings_disagreed === 1 ? "" : "s"}.</p>
          </Card>

          <Card title="False positives" subtitle="Legitimate claims recommended for denial (customer harm)">
            <Count label="Baseline" main={`${baseline.false_positives}`} detail={`of ${composition.legitimate} legitimate claims`} />
            <Count label="ClaimLens" main={`${lens.false_positives}`} detail={`of ${composition.legitimate} legitimate claims`} />
          </Card>

          <Card title="False negatives" subtitle="Fraud claims recommended for approval (losses)">
            <Count label="Baseline" main={`${baseline.false_negatives}`} detail={`of ${composition.fraud} fraud claims`} />
            <Count label="ClaimLens" main={`${lens.false_negatives}`} detail={`of ${composition.fraud} fraud claims`} />
          </Card>

          <Card title="Estimated fraud dollars caught" subtitle="Amounts of fraud claims correctly recommended for denial">
            <Count label="Baseline" main={money(baseline.fraud_amount_caught)} detail={`of ${money(baseline.fraud_amount_total)} claimed on fraud claims`} />
            <Count label="ClaimLens" main={money(lens.fraud_amount_caught)} detail={`of ${money(lens.fraud_amount_total)} claimed on fraud claims`} />
          </Card>

          <Card title="Estimated adjuster time saved" subtitle="Auto-resolved claims × assumed manual review time">
            <p className="text-3xl font-bold text-zinc-900">{lens.adjuster_hours_saved} hours</p>
            <p className="text-sm text-zinc-700">
              {lens.auto_resolved} auto-resolved claim{lens.auto_resolved === 1 ? "" : "s"} × {lens.manual_review_minutes_assumed} minutes each.
            </p>
            <p className="text-xs text-zinc-500">Assumption: an adjuster spends {lens.manual_review_minutes_assumed} minutes reviewing a routine claim.</p>
          </Card>
        </div>
      )}
    </>
  );
}

function Card({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-3 rounded-lg border border-zinc-200 bg-white p-5">
      <div>
        <h2 className="text-base font-semibold text-zinc-900">{title}</h2>
        <p className="text-xs text-zinc-500">{subtitle}</p>
      </div>
      {children}
    </section>
  );
}

// A count shown as "x of n" with a proportional bar (the bar width is visual only; no percentage is displayed).
function Bar({ label, count, outOf, color }: { label: string; count: number; outOf: number; color: string }) {
  return (
    <div className="flex flex-col gap-1">
      <div className="flex justify-between text-sm">
        <span className="text-zinc-700">{label}</span>
        <span className="font-semibold text-zinc-900">{count} of {outOf}</span>
      </div>
      <div className="h-3 w-full rounded bg-zinc-100">
        <div className={`h-3 rounded ${color}`} style={{ width: `${outOf ? (count / outOf) * 100 : 0}%` }} />
      </div>
    </div>
  );
}

function Count({ label, main, detail }: { label: string; main: string; detail: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-zinc-100 pb-2 text-sm last:border-0">
      <span className="text-zinc-700">{label}</span>
      <span className="text-right">
        <span className="font-semibold text-zinc-900">{main}</span> <span className="text-xs text-zinc-500">{detail}</span>
      </span>
    </div>
  );
}
