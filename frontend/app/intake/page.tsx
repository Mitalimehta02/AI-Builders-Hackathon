"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import ResultSummary from "@/components/ResultSummary";
import StatusTracker from "@/components/StatusTracker";
import { buttonStyles, Card, EmptyState, ErrorState, LoadingState, Page, PageHeader } from "@/components/ui";
import { api, type CaseDetail, type Claim, type LiveSubmissionState, type StatusResponse } from "@/lib/api";
import { claimFromForm, emptyForm, formFromClaim, type ClaimForm } from "@/lib/claimForm";
import { money } from "@/lib/labels";
import { useApi } from "@/lib/useApi";

const POLL_INTERVAL_MS = 1500;
const CONFIG_REFRESH_MS = 30_000;

export default function IntakePage() {
  const config = useApi("config", api.config, CONFIG_REFRESH_MS);
  const samples = useApi("samples", api.samples);
  const [sample, setSample] = useState<CaseDetail | null>(null);
  const [sampleError, setSampleError] = useState<Error | null>(null);
  const [baseClaim, setBaseClaim] = useState<Claim | null>(null);
  const [form, setForm] = useState<ClaimForm>(emptyForm);
  const [confirmSpend, setConfirmSpend] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<Error | null>(null);
  const [submissionId, setSubmissionId] = useState<number | null>(null);
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [result, setResult] = useState<CaseDetail | null>(null);

  // Poll a live submission until it is resolved or failed.
  useEffect(() => {
    if (submissionId === null) return;
    let cancelled = false;
    async function poll() {
      try {
        const next = await api.status(submissionId as number);
        if (cancelled) return;
        setStatus(next);
        if (next.status === "resolved" || next.status === "failed") {
          clearInterval(timer);
          if (next.status === "resolved") {
            const detail = await api.claim(submissionId as number);
            if (!cancelled) setResult(detail);
          }
        }
      } catch (error) {
        if (!cancelled) setSubmitError(error as Error);
      }
    }
    const timer = setInterval(poll, POLL_INTERVAL_MS);
    poll();
    return () => { cancelled = true; clearInterval(timer); };
  }, [submissionId]);

  async function loadSample(claimId: string) {
    setSampleError(null);
    try {
      const detail = await api.sample(claimId);
      setSample(detail);
      setBaseClaim(detail.claim);
      setForm(formFromClaim(detail.claim));
    } catch (error) {
      setSampleError(error as Error);
    }
  }

  function startBlankClaim() {
    setSample(null);
    setBaseClaim(null);
    setForm(emptyForm());
  }

  async function submitLive(event: FormEvent) {
    event.preventDefault();
    if (!config.data?.live_submission_enabled || !confirmSpend) return;
    setSubmitting(true);
    setSubmitError(null);
    setStatus(null);
    setResult(null);
    try {
      const response = await api.submitClaim(claimFromForm(form, baseClaim));
      setSubmissionId(response.id);
    } catch (error) {
      setSubmitError(error as Error);
    } finally {
      setSubmitting(false);
    }
  }

  const update = (key: keyof ClaimForm) => (value: string) => setForm((previous) => ({ ...previous, [key]: value }));
  const liveEnabled = config.data?.live_submission_enabled === true;

  return (
    <Page>
      <PageHeader title="Submit a claim" description="Load a stored sample to see a finished result, or fill in a claim by hand." />

      {config.error ? (
        <ErrorState error={config.error} onRetry={config.reload} title={config.error instanceof Error && "unreachable" in config.error && config.error.unreachable ? undefined : "Could not check whether live submission is allowed"} />
      ) : (
        <LiveSubmissionBanner config={config.data} />
      )}

      <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
        {/* ---- Samples ---- */}
        <aside className="flex flex-col gap-3">
          <h2 className="text-lg font-semibold text-zinc-900">Load a sample claim</h2>
          <p className="text-sm text-zinc-600">Stored results for development-set claims. Opening one makes no model call.</p>
          {samples.loading && !samples.data && <LoadingState label="Loading samples…" />}
          {samples.error && !samples.data && <ErrorState error={samples.error} onRetry={samples.reload} />}
          {sampleError && <ErrorState error={sampleError} title="Could not open that sample" />}
          {samples.data?.length === 0 && <EmptyState title="No stored samples available" />}
          {samples.data?.map((item) => (
            <button key={item.claim_id} type="button" onClick={() => loadSample(item.claim_id)} aria-pressed={sample?.claim_id === item.claim_id}
              className={`rounded-lg border-2 p-3 text-left transition hover:border-sky-500 ${
                sample?.claim_id === item.claim_id ? "border-sky-700 bg-sky-50" : "border-zinc-200 bg-white"
              }`}>
              <div className="flex flex-wrap items-center justify-between gap-1 text-sm font-semibold text-zinc-900">
                <span>{item.claim_id}{sample?.claim_id === item.claim_id && <span className="ml-2 text-xs font-normal text-sky-800">loaded</span>}</span>
                <span className="font-normal text-zinc-600">{item.claim_type} · {money(item.claim_amount)}</span>
              </div>
              <p className="mt-1 line-clamp-2 text-xs text-zinc-700">{item.description}</p>
              <span className="mt-2 inline-block rounded bg-zinc-100 px-2 py-0.5 text-[11px] text-zinc-700">stored result · no model call</span>
            </button>
          ))}
          <button type="button" onClick={startBlankClaim} className={buttonStyles.secondary}>Start a blank claim</button>
        </aside>

        <section className="flex min-w-0 flex-col gap-6">
          {/* ---- Stored result for the loaded sample ---- */}
          {sample && (
            <Card>
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h2 className="text-lg font-semibold text-zinc-900">Stored result for {sample.claim_id}</h2>
                <Link href={`/cases/sample/${sample.claim_id}`} className="text-sm font-semibold text-sky-800 underline-offset-2 hover:underline">
                  View full case →
                </Link>
              </div>
              <ResultSummary {...sample} />
              <p className="text-xs text-zinc-600">{sample.stored_sample?.note} Produced by: {sample.stored_sample?.source}.</p>
            </Card>
          )}

          {/* ---- Claim form ---- */}
          <form onSubmit={submitLive} className="flex flex-col gap-5 rounded-lg border border-zinc-200 bg-white p-4 sm:p-5">
            <FormSection title="Claim">
              <label className="flex flex-col gap-1 text-sm">
                <span className="font-medium text-zinc-800">Claim type</span>
                <select value={form.claimType} onChange={(event) => update("claimType")(event.target.value)}
                  className="min-h-11 rounded-md border border-zinc-400 bg-white px-3 py-2 text-zinc-900">
                  <option value="auto">Auto</option>
                  <option value="property">Property</option>
                </select>
              </label>
              <Field label="Date filed" type="date" value={form.filedDate} onChange={update("filedDate")} />
              <Field label="Amount claimed (USD, before deductible)" type="number" value={form.claimAmount} onChange={update("claimAmount")} />
            </FormSection>

            <FormSection title="Incident">
              <Field label="Incident date" type="date" value={form.incidentDate} onChange={update("incidentDate")} />
              <Field label="Street" value={form.incidentStreet} onChange={update("incidentStreet")} />
              <Field label="City" value={form.incidentCity} onChange={update("incidentCity")} />
              <Field label="State" value={form.incidentState} onChange={update("incidentState")} />
              <Field label="Latitude (optional, for the weather check)" type="number" value={form.latitude} onChange={update("latitude")} />
              <Field label="Longitude (optional)" type="number" value={form.longitude} onChange={update("longitude")} />
              <TextArea label="What happened" value={form.description} onChange={update("description")} />
              <TextArea label="Damage" value={form.damage} onChange={update("damage")} />
            </FormSection>

            <FormSection title="Policyholder home address">
              <Field label="Street" value={form.homeStreet} onChange={update("homeStreet")} />
              <Field label="City" value={form.homeCity} onChange={update("homeCity")} />
              <Field label="State" value={form.homeState} onChange={update("homeState")} />
            </FormSection>

            <FormSection title="Policy">
              <Field label="Policy number" value={form.policyNumber} onChange={update("policyNumber")} />
              <Field label="Policy type" value={form.policyType} onChange={update("policyType")} />
              <Field label="Policy start date" type="date" value={form.policyStartDate} onChange={update("policyStartDate")} />
              <Field label="Deductible (USD)" type="number" value={form.deductible} onChange={update("deductible")} />
              {form.claimType === "auto" ? (
                <>
                  <Field label="Coverages (comma separated)" value={form.coverages} onChange={update("coverages")} />
                  <Field label="Vehicle year" type="number" value={form.vehicleYear} onChange={update("vehicleYear")} />
                  <Field label="Vehicle make" value={form.vehicleMake} onChange={update("vehicleMake")} />
                  <Field label="Vehicle model" value={form.vehicleModel} onChange={update("vehicleModel")} />
                  <Field label="Vehicle value before the loss (USD)" type="number" value={form.vehicleValue} onChange={update("vehicleValue")} />
                </>
              ) : (
                <>
                  <Field label="Property type" value={form.propertyType} onChange={update("propertyType")} />
                  <Field label="Year built" type="number" value={form.yearBuilt} onChange={update("yearBuilt")} />
                  <Field label="Dwelling coverage (USD)" type="number" value={form.dwellingCoverage} onChange={update("dwellingCoverage")} />
                  <Field label="Contents coverage (USD)" type="number" value={form.contentsCoverage} onChange={update("contentsCoverage")} />
                </>
              )}
            </FormSection>

            <FormSection title="Supporting documents">
              <TextArea label="One document per line" value={form.documents} onChange={update("documents")} />
            </FormSection>

            {/* ---- Live submission (spends model quota) ---- */}
            <div className={`flex flex-col gap-3 rounded-md border p-4 ${liveEnabled ? "border-amber-300 bg-amber-50" : "border-zinc-300 bg-zinc-100"}`}>
              <p className="text-sm font-semibold text-zinc-900">Live submission — uses the model</p>
              {liveEnabled ? (
                <label className="flex items-start gap-3 text-sm text-zinc-900">
                  <input type="checkbox" checked={confirmSpend} onChange={(event) => setConfirmSpend(event.target.checked)} className="mt-1 h-5 w-5 shrink-0" />
                  <span>I understand this runs the full debate and spends about {config.data?.estimated_tokens_per_live_claim.toLocaleString()} tokens of the shared daily model allowance.</span>
                </label>
              ) : (
                <p className="text-sm text-zinc-800">
                  {config.data?.reason ?? (config.loading ? "Checking whether live submission is allowed…" : "Live submission is unavailable until the backend confirms it is allowed.")}
                </p>
              )}
              <button type="submit" disabled={!liveEnabled || !confirmSpend || submitting} className={`${buttonStyles.primary} self-start`}>
                {submitting ? "Submitting…" : "Submit live claim"}
              </button>
              {submitError && <ErrorState error={submitError} title="The claim was not accepted" />}
            </div>
          </form>

          {/* ---- Progress of a live submission ---- */}
          {submissionId !== null && (
            <Card title={`Processing claim ${status?.claim_id ?? ""}`}>
              <StatusTracker status={status} />
              {result && (
                <>
                  <ResultSummary {...result} />
                  <Link href={`/cases/claim/${submissionId}`} className="text-sm font-semibold text-sky-800 hover:underline">View full case →</Link>
                </>
              )}
            </Card>
          )}
        </section>
      </div>
    </Page>
  );
}

function LiveSubmissionBanner({ config }: { config: LiveSubmissionState | null }) {
  if (!config) return <LoadingState label="Checking whether live submission is allowed…" />;
  if (!config.live_submission_enabled) {
    const batch = config.batch;
    return (
      <div role="status" className="rounded-lg border-2 border-amber-400 bg-amber-50 p-4 text-sm text-amber-950">
        <p className="font-semibold">Live submission is switched off.</p>
        <p className="mt-1">{config.reason} Loading and viewing stored samples still works.</p>
        {config.batch_running && batch && (
          <p className="mt-1">
            Evaluation progress: {batch.claims_finished ?? 0} of {batch.claims_total ?? "?"} claims finished
            {batch.waiting_until ? `; waiting for the daily allowance to refill until ${new Date(batch.waiting_until).toLocaleTimeString()}` : ""}.
          </p>
        )}
      </div>
    );
  }
  return (
    <div className="rounded-lg border border-sky-300 bg-sky-50 p-4 text-sm text-sky-950">
      Live submission is available{config.override_active ? " (override active while the evaluation batch runs)" : ""}. Each live claim spends about{" "}
      {config.estimated_tokens_per_live_claim.toLocaleString()} tokens of the shared daily model allowance.
    </div>
  );
}

function FormSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <fieldset className="flex min-w-0 flex-col gap-3">
      <legend className="mb-2 text-sm font-semibold uppercase tracking-wide text-zinc-700">{title}</legend>
      <div className="grid gap-3 sm:grid-cols-2">{children}</div>
    </fieldset>
  );
}

function Field({ label, value, onChange, type = "text" }: { label: string; value: string; onChange: (value: string) => void; type?: string }) {
  return (
    <label className="flex min-w-0 flex-col gap-1 text-sm">
      <span className="font-medium text-zinc-800">{label}</span>
      <input type={type} value={value} onChange={(event) => onChange(event.target.value)} step={type === "number" ? "any" : undefined}
        className="min-h-11 w-full rounded-md border border-zinc-400 px-3 py-2 text-zinc-900 focus:border-sky-700 focus:outline-none focus:ring-2 focus:ring-sky-200" />
    </label>
  );
}

function TextArea({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="flex min-w-0 flex-col gap-1 text-sm sm:col-span-2">
      <span className="font-medium text-zinc-800">{label}</span>
      <textarea value={value} onChange={(event) => onChange(event.target.value)} rows={3}
        className="w-full rounded-md border border-zinc-400 px-3 py-2 text-zinc-900 focus:border-sky-700 focus:outline-none focus:ring-2 focus:ring-sky-200" />
    </label>
  );
}
