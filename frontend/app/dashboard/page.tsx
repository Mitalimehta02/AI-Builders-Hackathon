"use client";

// Adjuster dashboard (Stage 9): the case queue, filterable by status, confidence tier and outcome.
// Lists live submissions (GET /claims) and the stored development-set samples, clearly labelled.

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { api, type ClaimSummary, type QueueFilters, type SampleSummary } from "@/lib/api";
import { GATE_LABEL, money, STATUS_LABEL, TIER_STYLE } from "@/lib/labels";

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
  const [claims, setClaims] = useState<ClaimSummary[]>([]);
  const [samples, setSamples] = useState<SampleSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api.claims(filters)
      .then((rows) => { if (!cancelled) { setClaims(rows); setError(null); } })
      .catch((reason: Error) => { if (!cancelled) setError(reason.message); });
    return () => { cancelled = true; };
  }, [filters]);

  useEffect(() => {
    let cancelled = false;
    api.samples()
      .then((rows) => { if (!cancelled) setSamples(rows); })
      .catch((reason: Error) => { if (!cancelled) setError(reason.message); });
    return () => { cancelled = true; };
  }, []);

  const rows: Row[] = useMemo(() => {
    const live: Row[] = claims.map((c) => ({
      key: `claim-${c.id}`, href: `/cases/claim/${c.id}`, source: "Live submission", claimId: c.claim_id,
      claimType: c.claim_type, amount: c.claim_amount, status: c.status, decision: c.decision, tier: c.confidence_tier,
      gate: c.gate, capApplied: c.cap_applied,
    }));
    // Stored samples are filtered here with the same rules the backend applies to live claims.
    const stored: Row[] = includeSamples
      ? samples
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
  }, [claims, samples, filters, includeSamples]);

  const setFilter = (key: keyof QueueFilters) => (value: string) => setFilters((previous) => ({ ...previous, [key]: value || undefined }));

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-6 py-8">
      <header>
        <h1 className="text-2xl font-semibold text-zinc-900">Case queue</h1>
        <p className="text-sm text-zinc-600">
          Every claim ClaimLens has processed. Open a case to see the evidence, the debate, both judge rulings and the confidence check.
        </p>
      </header>

      <div className="flex flex-wrap items-end gap-4 rounded-lg border border-zinc-200 bg-white p-4">
        <Select label="Status" value={filters.status ?? ""} onChange={setFilter("status")}
          options={Object.entries(STATUS_LABEL).map(([value, label]) => ({ value, label }))} />
        <Select label="Confidence tier" value={filters.confidence_tier ?? ""} onChange={setFilter("confidence_tier")}
          options={["HIGH", "MEDIUM", "LOW"].map((value) => ({ value, label: value }))} />
        <Select label="Outcome" value={filters.gate ?? ""} onChange={setFilter("gate")}
          options={Object.entries(GATE_LABEL).map(([value, label]) => ({ value, label }))} />
        <label className="flex items-center gap-2 text-sm text-zinc-700">
          <input type="checkbox" checked={includeSamples} onChange={(event) => setIncludeSamples(event.target.checked)} />
          Include stored samples
        </label>
        <p className="ml-auto text-sm text-zinc-500">{rows.length} case{rows.length === 1 ? "" : "s"}</p>
      </div>

      {error && <p className="rounded-md bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}

      <div className="overflow-x-auto rounded-lg border border-zinc-200 bg-white">
        <table className="w-full text-left text-sm">
          <thead className="bg-zinc-50 text-xs uppercase tracking-wide text-zinc-500">
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
            {rows.length === 0 && (
              <tr><td colSpan={8} className="px-3 py-6 text-center text-zinc-500">No cases match these filters.</td></tr>
            )}
            {rows.map((row) => (
              <tr key={row.key} className="border-t border-zinc-100 hover:bg-zinc-50">
                <td className="px-3 py-2 font-medium"><Link href={row.href} className="text-sky-700 hover:underline">{row.claimId}</Link></td>
                <td className="px-3 py-2 text-zinc-600">{row.source}</td>
                <td className="px-3 py-2 text-zinc-700">{row.claimType} · {money(row.amount)}</td>
                <td className="px-3 py-2 text-zinc-700">{STATUS_LABEL[row.status]}</td>
                <td className={`px-3 py-2 font-semibold ${row.decision === "DENY" ? "text-rose-700" : "text-sky-800"}`}>{row.decision ?? "—"}</td>
                <td className="px-3 py-2">
                  {row.tier ? <span className={`rounded px-2 py-0.5 text-xs font-semibold ${TIER_STYLE[row.tier]}`}>{row.tier}</span> : "—"}
                </td>
                <td className="px-3 py-2">
                  {row.capApplied ? (
                    <span className="rounded bg-rose-600 px-2 py-0.5 text-xs font-semibold text-white">Cap fired</span>
                  ) : row.capApplied === false ? (
                    <span className="text-xs text-zinc-500">no</span>
                  ) : (
                    <span className="text-xs text-zinc-400">not recorded</span>
                  )}
                </td>
                <td className="px-3 py-2 text-zinc-700">{row.gate ? GATE_LABEL[row.gate] : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-xs text-zinc-500">
        Stored samples are development-set claims processed under earlier settings (see each case for details). The held-out claims
        in the running evaluation batch are not listed individually; their aggregate results are on the Analytics page.
      </p>
    </main>
  );
}

function Select({ label, value, onChange, options }: {
  label: string; value: string; onChange: (value: string) => void; options: { value: string; label: string }[];
}) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="font-medium text-zinc-700">{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)} className="rounded-md border border-zinc-300 px-3 py-2 text-zinc-900">
        <option value="">All</option>
        {options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
      </select>
    </label>
  );
}
