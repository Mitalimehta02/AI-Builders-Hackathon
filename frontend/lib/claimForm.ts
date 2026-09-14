// Converts between the intake form (plain text fields) and the claim JSON the backend expects.
// When a sample claim has been loaded, fields the form doesn't show (prior claims, policy change
// history, a different insured-property address, ...) are kept from that claim.

import type { Claim } from "@/lib/api";

export type ClaimForm = {
  claimType: "auto" | "property";
  filedDate: string;
  claimAmount: string;
  incidentDate: string;
  description: string;
  damage: string;
  incidentStreet: string;
  incidentCity: string;
  incidentState: string;
  latitude: string;
  longitude: string;
  homeStreet: string;
  homeCity: string;
  homeState: string;
  policyNumber: string;
  policyType: string;
  policyStartDate: string;
  deductible: string;
  coverages: string;
  vehicleYear: string;
  vehicleMake: string;
  vehicleModel: string;
  vehicleValue: string;
  propertyType: string;
  yearBuilt: string;
  dwellingCoverage: string;
  contentsCoverage: string;
  documents: string;
};

export function emptyForm(): ClaimForm {
  return {
    claimType: "auto",
    filedDate: "",
    claimAmount: "",
    incidentDate: "",
    description: "",
    damage: "",
    incidentStreet: "",
    incidentCity: "",
    incidentState: "",
    latitude: "",
    longitude: "",
    homeStreet: "",
    homeCity: "",
    homeState: "",
    policyNumber: "",
    policyType: "Personal Auto",
    policyStartDate: "",
    deductible: "",
    coverages: "Liability, Collision, Comprehensive",
    vehicleYear: "",
    vehicleMake: "",
    vehicleModel: "",
    vehicleValue: "",
    propertyType: "Single-family home",
    yearBuilt: "",
    dwellingCoverage: "",
    contentsCoverage: "",
    documents: "",
  };
}

const text = (value: unknown) => (value === undefined || value === null ? "" : String(value));

export function formFromClaim(claim: Claim): ClaimForm {
  const { policy, incident, policyholder } = claim;
  return {
    ...emptyForm(),
    claimType: claim.claim_type,
    filedDate: claim.filed_date,
    claimAmount: text(claim.claim_amount),
    incidentDate: incident.date,
    description: incident.description,
    damage: incident.damage,
    incidentStreet: incident.location.street,
    incidentCity: incident.location.city,
    incidentState: incident.location.state,
    latitude: text(incident.location.latitude),
    longitude: text(incident.location.longitude),
    homeStreet: policyholder.address.street,
    homeCity: policyholder.address.city,
    homeState: policyholder.address.state,
    policyNumber: policy.policy_number,
    policyType: policy.policy_type,
    policyStartDate: policy.start_date,
    deductible: text(policy.deductible),
    coverages: (policy.coverages ?? []).join(", "),
    vehicleYear: text(policy.insured_vehicle?.year),
    vehicleMake: text(policy.insured_vehicle?.make),
    vehicleModel: text(policy.insured_vehicle?.model),
    vehicleValue: text(policy.insured_vehicle?.estimated_value),
    propertyType: text(policy.insured_property?.property_type) || "Single-family home",
    yearBuilt: text(policy.insured_property?.year_built),
    dwellingCoverage: text(policy.dwelling_coverage),
    contentsCoverage: text(policy.contents_coverage),
    documents: claim.supporting_documents.join("\n"),
  };
}

// Blank numeric fields are left out, so the backend reports them as missing rather than as zero.
const number = (value: string) => (value.trim() === "" ? undefined : Number(value));
const lines = (value: string) => value.split("\n").map((line) => line.trim()).filter(Boolean);

export function claimFromForm(form: ClaimForm, base: Claim | null): Claim {
  const home = { street: form.homeStreet, city: form.homeCity, state: form.homeState };
  const policy: Claim["policy"] = {
    ...(base?.policy ?? {}),
    policy_number: form.policyNumber,
    policy_type: form.policyType,
    start_date: form.policyStartDate,
    deductible: number(form.deductible) as number,
  };

  if (form.claimType === "auto") {
    delete policy.insured_property;
    delete policy.dwelling_coverage;
    delete policy.contents_coverage;
    policy.coverages = form.coverages.split(",").map((c) => c.trim()).filter(Boolean);
    policy.insured_vehicle = {
      ...(base?.policy.insured_vehicle ?? {}),
      year: number(form.vehicleYear) as number,
      make: form.vehicleMake,
      model: form.vehicleModel,
      estimated_value: number(form.vehicleValue) as number,
    };
  } else {
    delete policy.coverages;
    delete policy.insured_vehicle;
    policy.insured_property = {
      ...(base?.policy.insured_property ?? home),
      property_type: form.propertyType,
      year_built: number(form.yearBuilt) as number,
    };
    policy.dwelling_coverage = number(form.dwellingCoverage);
    policy.contents_coverage = number(form.contentsCoverage);
  }

  return {
    ...(base ?? {}),
    claim_type: form.claimType,
    filed_date: form.filedDate,
    claim_amount: number(form.claimAmount) as number,
    policyholder: { ...(base?.policyholder ?? {}), address: home },
    policy,
    incident: {
      date: form.incidentDate,
      description: form.description,
      damage: form.damage,
      location: {
        street: form.incidentStreet,
        city: form.incidentCity,
        state: form.incidentState,
        latitude: number(form.latitude),
        longitude: number(form.longitude),
      },
    },
    supporting_documents: lines(form.documents),
  };
}
