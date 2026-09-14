import type { ReactNode } from "react";
import type { Evidence } from "@/lib/api";
import { days, money } from "@/lib/labels";

// The Stage 3 evidence object in readable form: neutral facts gathered by lookups and fixed rules.
export default function EvidencePanel({ evidence }: { evidence: Evidence | null }) {
  if (!evidence) {
    return (
      <section className="rounded-lg border border-zinc-200 bg-white p-4 sm:p-5">
        <h2 className="text-lg font-semibold text-zinc-900">Evidence</h2>
        <p className="mt-1 text-sm text-zinc-600">No evidence has been gathered for this claim yet.</p>
      </section>
    );
  }
  const { timeline, policy, claim_history: history, location, documents, weather } = evidence;
  const absent = documents?.documents_mentioned_but_absent ?? documents?.expected_but_not_found ?? [];

  return (
    <section className="flex flex-col gap-3">
      <div>
        <h2 className="text-lg font-semibold text-zinc-900">Evidence</h2>
        <p className="text-sm text-zinc-600">Facts gathered automatically for this claim. They are observations, not conclusions.</p>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <Card title="Timeline">
          <Fact label="Policy started">{timeline?.policy_start_date}</Fact>
          <Fact label="Incident">{timeline?.incident_date}</Fact>
          <Fact label="Claim filed">{timeline?.filed_date}</Fact>
          <Fact label="Policy age at incident">{num(timeline?.days_policy_start_to_incident, days)}</Fact>
          <Fact label="Incident to filing">{num(timeline?.days_incident_to_filing, days)}</Fact>
          <Fact label="Latest policy change">
            {timeline?.days_last_policy_change_to_incident == null ? "none" : `${days(timeline.days_last_policy_change_to_incident)} before the incident`}
          </Fact>
        </Card>

        <Card title="Policy">
          <Fact label="Type">{policy?.type}</Fact>
          {policy?.coverages && <Fact label="Coverages">{policy.coverages.join(", ")}</Fact>}
          {policy?.vehicle && <Fact label="Vehicle">{policy.vehicle}</Fact>}
          {policy?.vehicle_estimated_value !== undefined && <Fact label="Vehicle value before loss">{money(policy.vehicle_estimated_value)}</Fact>}
          {policy?.claim_amount_pct_of_vehicle_value !== undefined && (
            <Fact label="Amount claimed vs vehicle value">{policy.claim_amount_pct_of_vehicle_value} per 100 of value</Fact>
          )}
          {policy?.property && <Fact label="Property">{policy.property}</Fact>}
          {policy?.dwelling_coverage !== undefined && <Fact label="Dwelling coverage">{money(policy.dwelling_coverage)}</Fact>}
          {policy?.contents_coverage !== undefined && <Fact label="Contents coverage">{money(policy.contents_coverage)}</Fact>}
          <Fact label="Policy changes">
            {policy?.changes?.length ? (
              <ul className="list-disc pl-4">
                {policy.changes.map((change, index) => (
                  <li key={index}>{change.change} — {days(change.days_before_incident)} before the incident</li>
                ))}
              </ul>
            ) : "none"}
          </Fact>
        </Card>

        <Card title="Claim history (this insurer and other insurers)">
          <Fact label="Prior claims">{history?.prior_claims_count ?? 0}</Fact>
          <Fact label="In the last 24 months">{history?.prior_claims_last_24_months ?? 0}</Fact>
          {history?.prior_claims?.map((prior, index) => (
            <div key={index} className="rounded-md bg-zinc-50 p-2 text-xs text-zinc-700">
              <p className="font-medium text-zinc-900">{prior.summary}</p>
              <p>{days(prior.days_before_incident)} before · {money(prior.amount)} · {prior.insurer}</p>
              {prior.words_shared_with_this_claim.length > 0 && (
                <p>Words in common with this claim: {prior.words_shared_with_this_claim.join(", ")}</p>
              )}
            </div>
          ))}
        </Card>

        <Card title="Location">
          <Fact label="Incident location">{location?.incident_location}</Fact>
          <Fact label="Policyholder home">{location?.policyholder_home}</Fact>
          <Fact label="Same city as home"><YesNo value={location?.same_city_as_home} /></Fact>
          {location?.incident_address_matches_insured_property !== undefined && (
            <Fact label="Matches insured property address"><YesNo value={location.incident_address_matches_insured_property} /></Fact>
          )}
        </Card>

        <Card title="Documents">
          <Fact label="Documents provided">{documents?.documents_provided ?? 0}</Fact>
          <Fact label="Mentioned in the description but absent">{absent.length ? absent.join("; ") : "none found by the checks"}</Fact>
          <Fact label="Listed as not yet provided">
            {documents?.listed_as_not_yet_provided?.length ? documents.listed_as_not_yet_provided.join("; ") : "none"}
          </Fact>
          {documents?.dated_documents?.map((dated, index) => (
            <Fact key={index} label="Dated document">
              {dated.document} ({dated.days_relative_to_incident < 0
                ? `${days(-dated.days_relative_to_incident)} before`
                : `${days(dated.days_relative_to_incident)} after`} the incident)
            </Fact>
          ))}
        </Card>

        <Card title="Recorded weather at the incident location">
          {weather?.status === "ok" ? (
            <>
              <Fact label="Dates checked">{weather.dates_checked}</Fact>
              <Fact label="Temperature range">{weather.lowest_temp_c} °C to {weather.highest_temp_c} °C</Fact>
              <Fact label="Days below freezing">{weather.days_with_low_below_freezing}</Fact>
              <Fact label="Precipitation / snowfall">{weather.total_precipitation_mm} mm / {weather.total_snowfall_cm} cm</Fact>
              <Fact label="Weather words in the description">
                {weather.weather_terms_in_description?.length ? weather.weather_terms_in_description.join(", ") : "none"}
              </Fact>
              <p className="text-xs text-zinc-600">Source: {weather.source}</p>
            </>
          ) : (
            <Fact label="Status">Unavailable{weather?.reason ? ` — ${weather.reason}` : ""}</Fact>
          )}
        </Card>
      </div>
    </section>
  );
}

function num(value: number | undefined, format: (n: number) => string) {
  return value === undefined ? "—" : format(value);
}

function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-2 rounded-lg border border-zinc-200 bg-white p-4">
      <h3 className="text-sm font-semibold text-zinc-900">{title}</h3>
      {children}
    </div>
  );
}

// Label above the value on phones; side by side on wider screens.
function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5 text-sm sm:grid sm:grid-cols-[11rem_1fr] sm:gap-2">
      <span className="text-zinc-600">{label}</span>
      <span className="text-zinc-900 [overflow-wrap:anywhere]">{children ?? "—"}</span>
    </div>
  );
}

function YesNo({ value }: { value: boolean | undefined }) {
  if (value === undefined) return <span>—</span>;
  return (
    <span className={`rounded px-2 py-0.5 text-xs font-semibold ${value ? "bg-zinc-100 text-zinc-800" : "bg-amber-100 text-amber-900"}`}>
      {value ? "Yes" : "No"}
    </span>
  );
}
