"use client";

// Adjuster dashboard (Stage 9): the case queue, filterable by status, confidence tier and outcome.
// Lists live submissions (GET /claims) and the stored development-set samples, clearly labelled.

import Link from "next/link";
import { useMemo, useState } from "react";
import { EmptyState, ErrorState, LoadingState, Page, PageHeader } from "@/components/ui";
import { api, type ClaimSummary, type QueueFilters } from "@/lib/api";
import { GATE_LABEL, money, STATUS_LABEL, TIER_STYLE } from "@/lib/labels";
import { useApi } from "@/lib/useApi";

type Row = {
  key: string;
  href: string;
  source: "Live submission" | "Stored sample";
  claimId: string;
  claimType: string;
  amount: number;
  status: ClaimSummary["status"];
  decision: ClaimSummary["decision"];
  tier: ClaimSummary["confidence_tier"];
  gate: ClaimSummary["gate"];
  capApplied: boolean | null;
};

export default function DashboardPage() {
  const [filters, setFilters] = useState<QueueFilters>({});
  const [includeSamples, setIncludeSamples] = useState(true);
  const claims = useApi(`claims:${JSON.stringify(filters)}`, () => api.claims(filters));
  const samples = useApi("samples", api.samples);

  const rows: Row[] = useMemo(() => {
    const live: Row[] = (claims.data ?? []).map((c) => ({
      key: `claim-${c.id}`, href: `/cases/claim/${c.id}`, source: "Live submission", claimId: c.claim_id,
      claimType: c.claim_type, amount: c.claim_amount, status: c.status, decision: c.decision, tier: c.confidence_tier,
      gate: c.gate, capApplied: c.cap_applied,
    }));
    // Stored samples are filtered here with the same rules the backend applies to live claims.
    const stored: Row[] = includeSamples
      ? (samples.data ?? [])
          .filter((s) => (!filters.status || s.status === filters.status)
            && (!filters.confidence_tier || s.confidence_tier === filters.confidence_tier)
            && (!filters.gate || s.gate === filters.gate))
          .map((s) => ({
            key: `sample-${s.claim_id}`, href: `/cases/sample/${s.claim_id}`, source: "Stored sample", claimId: s.claim_id,
            claimType: s.claim_type, amount: s.claim_amount, status: s.status, decision: s.decision, tier: s.confidence_tier,
            gate: s.gate, capApplied: s.cap_applied,
          }))
      : [];
    return [...live, ...stored];
  }, [claims.data, samples.data, filters, includeSamples]);

  const setFilter = (key: keyof QueueFilters) => (value: string) => setFilters((previous) => ({ ...previous, [key]: value || undefined }));
  const error = claims.error ?? samples.error;
  const firstLoad = (claims.loading && !claims.data) || (samples.loading && !samples.data);
  const hasFilters = Boolean(filters.status || filters.confidence_tier || filters.gate);

  return (
    <Page>
      <PageHeader
        title="Case queue"
        description="Every claim ClaimLens has processed. Open a case to see the evidence, the debate, both judge rulings and the confidence check."
      />

      <div className="grid gap-3 rounded-lg border border-zinc-200 bg-white p-4 sm:flex sm:flex-wrap sm:items-end sm:gap-4">
        <Select label="Status" value={filters.status ?? ""} onChange={setFilter("status")}
          options={Object.entries(STATUS_LABEL).map(([value, label]) => ({ value, label }))} />
        <Select label="Confidence tier" value={filters.confidence_tier ?? ""} onChange={setFilter("confidence_tier")}
          options={["HIGH", "MEDIUM", "LOW"].map((value) => ({ value, label: value }))} />
        <Select label="Outcome" value={filters.gate ?? ""} onChange={setFilter("gate")}
          options={Object.entries(GATE_LABEL).map(([value, label]) => ({ value, label }))} />
        <label className="flex min-h-11 items-center gap-2 text-sm text-zinc-800">
          <input type="checkbox" checked={includeSamples} onChange={(event) => setIncludeSamples(event.target.checked)} className="h-5 w-5" />
          Include stored samples
        </label>
        <p className="text-sm text-zinc-700 sm:ml-auto" aria-live="polite">{rows.length} case{rows.length === 1 ? "" : "s"}</p>
      </div>

      {error && <ErrorState error={error} onRetry={() => { claims.reload(); samples.reload(); }} />}
      {firstLoad && !error && <LoadingState label="Loading the case queue…" />}

      {!firstLoad && !error && rows.length === 0 && (
        <EmptyState title={hasFilters ? "No cases match these filters" : "No cases yet"}>
          {hasFilters ? "Try clearing a filter." : "Submit a claim on the Intake page, or turn on stored samples."}
        </EmptyState>
      )}

      {rows.length > 0 && (
        <>
          {/* Phones: one card per case */}
          <ul className="flex flex-col gap-3 md:hidden">
            {rows.map((row) => (
              <li key={row.key}>
                <Link href={row.href} className="flex flex-col gap-2 rounded-lg border border-zinc-200 bg-white p-4 hover:border-sky-500">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-semibold text-sky-800">{row.claimId}</span>
                    <span className="text-xs text-zinc-600">{row.source}</span>
                  </div>
                  <p className="text-sm text-zinc-700">{row.claimType} · {money(row.amount)} · {STATUS_LABEL[row.status]}</p>
                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    <DecisionText decision={row.decision} />
                    <TierBadge tier={row.tier} />
                    <CapBadge capApplied={row.capApplied} />
                    <span className="text-zinc-700">{row.gate ? GATE_LABEL[row.gate] : ""}</span>
                  </div>
                </Link>
              </li>
            ))}
          </ul>

          {/* Wider screens: a table */}
          <div className="hidden overflow-x-auto rounded-lg border border-zinc-200 bg-white md:block">
            <table className="w-full text-left text-sm">
              <thead className="bg-zinc-50 text-xs uppercase tracking-wide text-zinc-600">
                <tr>
                  <th className="px-3 py-2">Case</th>
                  <th className="px-3 py-2">Source</th>
                  <th className="px-3 py-2">Claim</th>
                  <th className="px-3 py-2">Status</th>
                  <th className="px-3 py-2">Recommendation</th>
                  <th className="px-3 py-2">Confidence</th>
                  <th className="px-3 py-2">Cap</th>
                  <th className="px-3 py-2">Outcome</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.key} className="border-t border-zinc-200 hover:bg-zinc-50">
                    <td className="px-3 py-2 font-semibold"><Link href={row.href} className="text-sky-800 underline-offset-2 hover:underline">{row.claimId}</Link></td>
                    <td className="px-3 py-2 text-zinc-700">{row.source}</td>
                    <td className="px-3 py-2 text-zinc-700">{row.claimType} · {money(row.amount)}</td>
                    <td className="px-3 py-2 text-zinc-700">{STATUS_LABEL[row.status]}</td>
                    <td className="px-3 py-2"><DecisionText decision={row.decision} /></td>
                    <td className="px-3 py-2"><TierBadge tier={row.tier} /></td>
                    <td className="px-3 py-2"><CapBadge capApplied={row.capApplied} /></td>
                    <td className="px-3 py-2 text-zinc-700">{row.gate ? GATE_LABEL[row.gate] : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      <p className="text-xs text-zinc-600">
        Stored samples are development-set claims processed under earlier settings (see each case for details). The held-out claims in
        the evaluation batch are not listed individually; their aggregate results are on the Analytics page.
      </p>
    </Page>
  );
}

function DecisionText({ decision }: { decision: ClaimSummary["decision"] }) {
  if (!decision) return <span className="text-zinc-600">—</span>;
  return <span className={`font-semibold ${decision === "DENY" ? "text-rose-800" : "text-sky-800"}`}>{decision}</span>;
}

function TierBadge({ tier }: { tier: ClaimSummary["confidence_tier"] }) {
  if (!tier) return <span className="text-zinc-600">—</span>;
  return <span className={`rounded px-2 py-0.5 text-xs font-semibold ${TIER_STYLE[tier]}`}>{tier}</span>;
}

function CapBadge({ capApplied }: { capApplied: boolean | null }) {
  if (capApplied) return <span className="rounded bg-rose-700 px-2 py-0.5 text-xs font-semibold text-white">Cap fired</span>;
  if (capApplied === false) return <span className="text-xs text-zinc-600">cap: no</span>;
  return <span className="text-xs text-zinc-600">cap: not recorded</span>;
}

function Select({ label, value, onChange, options }: {
  label: string; value: string; onChange: (value: string) => void; options: { value: string; label: string }[];
}) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="font-medium text-zinc-800">{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)} className="min-h-11 rounded-md border border-zinc-400 bg-white px-3 py-2 text-zinc-900">
        <option value="">All</option>
        {options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
      </select>
    </label>
  );
}
