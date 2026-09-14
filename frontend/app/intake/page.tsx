"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import ResultSummary from "@/components/ResultSummary";
import StatusTracker from "@/components/StatusTracker";
import {
  api,
  type CaseDetail,
  type Claim,
  type LiveSubmissionState,
  type SampleSummary,
  type StatusResponse,
} from "@/lib/api";
import { claimFromForm, emptyForm, formFromClaim, type ClaimForm } from "@/lib/claimForm";

const POLL_INTERVAL_MS = 1500;
const CONFIG_REFRESH_MS = 30_000;

export default function IntakePage() {
  const [config, setConfig] = useState<LiveSubmissionState | null>(null);
  const [configError, setConfigError] = useState<string | null>(null);
  const [samples, setSamples] = useState<SampleSummary[]>([]);
  const [samplesError, setSamplesError] = useState<string | null>(null);
  const [sample, setSample] = useState<CaseDetail | null>(null);
  const [baseClaim, setBaseClaim] = useState<Claim | null>(null);
  const [form, setForm] = useState<ClaimForm>(emptyForm);
  const [confirmSpend, setConfirmSpend] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submissionId, setSubmissionId] = useState<number | null>(null);
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [result, setResult] = useState<CaseDetail | null>(null);

  // Whether live submission is allowed. Refreshed regularly: the evaluation batch may start or finish.
  useEffect(() => {
    let cancelled = false;
    const load = () =>
      api.config()
        .then((next) => { if (!cancelled) { setConfig(next); setConfigError(null); } })
        .catch((error: Error) => { if (!cancelled) setConfigError(error.message); });
    load();
    const timer = setInterval(load, CONFIG_REFRESH_MS);
    return () => { cancelled = true; clearInterval(timer); };
  }, []);

  // Stored sample results (served from files - no model call).
  useEffect(() => {
    let cancelled = false;
    api.samples()
      .then((list) => { if (!cancelled) setSamples(list); })
      .catch((error: Error) => { if (!cancelled) setSamplesError(error.message); });
    return () => { cancelled = true; };
  }, []);

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
        if (!cancelled) setSubmitError((error as Error).message);
      }
    }
    const timer = setInterval(poll, POLL_INTERVAL_MS);
    poll();
    return () => { cancelled = true; clearInterval(timer); };
  }, [submissionId]);

  async function loadSample(claimId: string) {
    setSamplesError(null);
    try {
      const detail = await api.sample(claimId);
      setSample(detail);
      setBaseClaim(detail.claim);
      setForm(formFromClaim(detail.claim));
    } catch (error) {
      setSamplesError((error as Error).message);
    }
  }

  function startBlankClaim() {
    setSample(null);
    setBaseClaim(null);
    setForm(emptyForm());
  }

  async function submitLive(event: FormEvent) {
    event.preventDefault();
    if (!config?.live_submission_enabled || !confirmSpend) return;
    setSubmitting(true);
    setSubmitError(null);
    setStatus(null);
    setResult(null);
    try {
      const response = await api.submitClaim(claimFromForm(form, baseClaim));
      setSubmissionId(response.id);
    } catch (error) {
      setSubmitError((error as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  const update = (key: keyof ClaimForm) => (value: string) => setForm((previous) => ({ ...previous, [key]: value }));
  const liveEnabled = config?.live_submission_enabled === true;

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-6 py-8">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold text-zinc-900">Submit a claim</h1>
          <p className="text-sm text-zinc-600">Load a stored sample to see a finished result, or fill in a claim by hand.</p>
        </div>
        <Link href="/" className="text-sm text-sky-700 hover:underline">← ClaimLens home</Link>
      </header>

      <LiveSubmissionBanner config={config} error={configError} />

      <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
        {/* ---- Samples ---- */}
        <aside className="flex flex-col gap-3">
          <h2 className="text-lg font-semibold text-zinc-900">Load a sample claim</h2>
          <p className="text-xs text-zinc-500">Stored results for development-set claims. Opening one makes no model call.</p>
          {samplesError && <p className="rounded-md bg-rose-50 p-3 text-sm text-rose-800">{samplesError}</p>}
          {samples.map((item) => (
            <button key={item.claim_id} type="button" onClick={() => loadSample(item.claim_id)}
              className={`rounded-lg border p-3 text-left transition hover:border-sky-400 ${
                sample?.claim_id === item.claim_id ? "border-sky-500 bg-sky-50" : "border-zinc-200 bg-white"
              }`}>
              <div className="flex items-center justify-between text-sm font-semibold text-zinc-900">
                <span>{item.claim_id}</span>
                <span className="font-normal text-zinc-500">{item.claim_type} · ${item.claim_amount.toLocaleString()}</span>
              </div>
              <p className="mt-1 line-clamp-2 text-xs text-zinc-600">{item.description}</p>
              <span className="mt-2 inline-block rounded bg-zinc-100 px-2 py-0.5 text-[11px] text-zinc-600">stored result · no model call</span>
            </button>
          ))}
          <button type="button" onClick={startBlankClaim} className="rounded-lg border border-dashed border-zinc-300 p-3 text-sm text-zinc-700 hover:border-zinc-500">
            Start a blank claim
          </button>
        </aside>

        <section className="flex flex-col gap-6">
          {/* ---- Stored result for the loaded sample ---- */}
          {sample && (
            <div className="rounded-lg border border-zinc-200 bg-white p-5">
              <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
                <h2 className="text-lg font-semibold text-zinc-900">Stored result for {sample.claim_id}</h2>
                <Link href={`/cases/sample/${sample.claim_id}`} className="text-sm font-medium text-sky-700 hover:underline">View case →</Link>
              </div>
              <ResultSummary {...sample} />
              <p className="mt-3 text-xs text-zinc-500">{sample.stored_sample?.note} Produced by: {sample.stored_sample?.source}.</p>
            </div>
          )}

          {/* ---- Claim form ---- */}
          <form onSubmit={submitLive} className="flex flex-col gap-5 rounded-lg border border-zinc-200 bg-white p-5">
            <FormSection title="Claim">
              <label className="flex flex-col gap-1 text-sm">
                <span className="font-medium text-zinc-700">Claim type</span>
                <select value={form.claimType} onChange={(event) => update("claimType")(event.target.value)}
                  className="rounded-md border border-zinc-300 px-3 py-2 text-zinc-900">
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
              <TextArea label="What happened" value={form.description} onChange={update("description")} wide />
              <TextArea label="Damage" value={form.damage} onChange={update("damage")} wide />
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
              <TextArea label="One document per line" value={form.documents} onChange={update("documents")} wide />
            </FormSection>

            {/* ---- Live submission (spends model quota) ---- */}
            <div className={`flex flex-col gap-3 rounded-md p-4 ${liveEnabled ? "bg-amber-50" : "bg-zinc-100"}`}>
              <p className="text-sm font-semibold text-zinc-900">Live submission — uses the model</p>
              {liveEnabled ? (
                <label className="flex items-start gap-2 text-sm text-zinc-800">
                  <input type="checkbox" checked={confirmSpend} onChange={(event) => setConfirmSpend(event.target.checked)} className="mt-1" />
                  <span>I understand this runs the full debate and spends about {config?.estimated_tokens_per_live_claim.toLocaleString()} tokens of the shared daily model allowance.</span>
                </label>
              ) : (
                <p className="text-sm text-zinc-700">
                  {config?.reason ?? "Live submission is unavailable until the backend reports that it is allowed."}
                </p>
              )}
              <button type="submit" disabled={!liveEnabled || !confirmSpend || submitting}
                className="self-start rounded-md bg-sky-700 px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-zinc-400">
                {submitting ? "Submitting…" : "Submit live claim"}
              </button>
              {submitError && <p className="rounded-md bg-rose-50 p-3 text-sm text-rose-800">{submitError}</p>}
            </div>
          </form>

          {/* ---- Progress of a live submission ---- */}
          {submissionId !== null && (
            <div className="flex flex-col gap-4 rounded-lg border border-zinc-200 bg-white p-5">
              <h2 className="text-lg font-semibold text-zinc-900">Processing claim {status?.claim_id ?? ""}</h2>
              <StatusTracker status={status} />
              {result && (
                <>
                  <ResultSummary {...result} />
                  <Link href={`/cases/claim/${submissionId}`} className="text-sm font-medium text-sky-700 hover:underline">View case →</Link>
                </>
              )}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

function LiveSubmissionBanner({ config, error }: { config: LiveSubmissionState | null; error: string | null }) {
  if (error) {
    return <div className="rounded-lg bg-rose-50 p-4 text-sm text-rose-800">Could not check whether live submission is allowed: {error}</div>;
  }
  if (!config) return null;
  if (!config.live_submission_enabled) {
    const batch = config.batch;
    return (
      <div className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900">
        <p className="font-semibold">Live submission is switched off while the evaluation batch runs.</p>
        <p className="mt-1">{config.reason} Loading and viewing stored samples still works.</p>
        {batch && (
          <p className="mt-1 text-amber-800">
            Batch progress: {batch.claims_finished ?? 0} of {batch.claims_total ?? "?"} claims finished
            {batch.waiting_until ? `; waiting for the daily allowance to refill until ${new Date(batch.waiting_until).toLocaleTimeString()}` : ""}.
          </p>
        )}
      </div>
    );
  }
  return (
    <div className="rounded-lg border border-sky-200 bg-sky-50 p-4 text-sm text-sky-900">
      Live submission is available{config.override_active ? " (override active while the evaluation batch runs)" : ""}. Each
      live claim spends about {config.estimated_tokens_per_live_claim.toLocaleString()} tokens of the shared daily model allowance.
    </div>
  );
}

function FormSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <fieldset className="flex flex-col gap-3">
      <legend className="mb-2 text-sm font-semibold uppercase tracking-wide text-zinc-500">{title}</legend>
      <div className="grid gap-3 sm:grid-cols-2">{children}</div>
    </fieldset>
  );
}

function Field({ label, value, onChange, type = "text" }: { label: string; value: string; onChange: (value: string) => void; type?: string }) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="font-medium text-zinc-700">{label}</span>
      <input type={type} value={value} onChange={(event) => onChange(event.target.value)} step={type === "number" ? "any" : undefined}
        className="rounded-md border border-zinc-300 px-3 py-2 text-zinc-900 focus:border-sky-500 focus:outline-none" />
    </label>
  );
}

function TextArea({ label, value, onChange, wide }: { label: string; value: string; onChange: (value: string) => void; wide?: boolean }) {
  return (
    <label className={`flex flex-col gap-1 text-sm ${wide ? "sm:col-span-2" : ""}`}>
      <span className="font-medium text-zinc-700">{label}</span>
      <textarea value={value} onChange={(event) => onChange(event.target.value)} rows={3}
        className="rounded-md border border-zinc-300 px-3 py-2 text-zinc-900 focus:border-sky-500 focus:outline-none" />
    </label>
  );
}
