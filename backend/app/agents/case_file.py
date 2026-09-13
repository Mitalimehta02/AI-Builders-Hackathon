"""
The case file: exactly what every decision-making agent is shown about a claim.

The naive baseline (Stage 4) and the debate agents (Stage 5+) must all build their prompt
input with build_case_file(), and use the shared CASE_FILE_GUIDE, DECISION_DEFINITIONS and
REVIEW_GUIDANCE text. That way the Stage 11 comparison is same inputs, same model, same
settings: only the architecture differs.

What goes in: the sanitized claim + its Stage 3 evidence object, as compact JSON.
What is left out, identically for every agent:
- personal identifiers (name, phone, email, date of birth): irrelevant to whether a loss is
  genuine, and a known source of model bias
- data the evidence object already carries in enriched form (policy change history, prior
  claims) and raw coordinates (only needed for the weather lookup)

CASE_FILE_GUIDE spells out every convention a careful reader could otherwise guess wrong
(e.g. the claimed amount is BEFORE the deductible). Changes to it are recorded in
docs/METHODOLOGY.md, because they change the input of every agent at once.
"""

import copy
import json

from app.agents.sanitize import find_label_keys

EXCLUDED_POLICYHOLDER_FIELDS = ("name", "phone", "email", "date_of_birth")

DECISION_DEFINITIONS = """APPROVE = the claim describes a genuine loss, as reported.
DENY = the claim is fraudulent or materially misrepresented.
The decision is only about whether the claim is genuine. Deductibles, coverage limits and payout amounts are applied separately when a claim is paid, so a genuine loss is APPROVE even if the deductible means little or nothing will be paid."""

CASE_FILE_GUIDE = """The case file has two parts. All amounts are in US dollars. All day counts are calendar days.

CLAIM: the claim as submitted.
- claim_type is "auto" or "property". filed_date is the date the claim was reported to the insurer.
- policyholder.address is the policyholder's home address. Personal identifiers have been removed.
- policy.start_date is the date this policy first took effect with this insurer (not the latest renewal date).
- policy.coverages (auto) are the coverages in force on the incident date. Collision pays for damage to the insured vehicle from hitting a vehicle or object. Comprehensive pays for theft, fire, weather, vandalism and animal strikes. Liability pays for damage the policyholder causes to others, not for the policyholder's own vehicle.
- policy.deductible is the amount the policyholder bears on each claim. The insurer subtracts it when paying, so the amount actually paid is the claim_amount minus the deductible.
- policy.insured_vehicle.estimated_value is the vehicle's actual cash value just before the loss: its market value, which is what a total loss is settled on (before the deductible). It is not the price of a new replacement vehicle and not a dealer trade-in offer.
- policy.dwelling_coverage and policy.contents_coverage (property) are the most the policy will pay for damage to the building and to belongings, respectively.
- incident gives the date and place of the loss. incident.description and incident.damage are the policyholder's own account as submitted; nobody has verified them.
- claim_amount is the total amount claimed for this loss BEFORE the deductible, including parts, labor and any sales tax.
- supporting_documents are the titles of the documents submitted with the claim. A listed document is in the file, but its contents are not reproduced here. A number in brackets is a count (for example, of photos). A document that is not listed was not submitted.

EVIDENCE: facts gathered automatically for this claim by lookups and fixed rules. They are neutral observations, not conclusions.
- timeline: key dates and the number of days between policy start, the latest policy change, the incident and filing.
- policy: coverage details; changes lists every change made to the policy since it started, with how many days before the incident it was made; claim_amount_pct_of_vehicle_value is claim_amount divided by estimated_value, times 100 (both before the deductible).
- claim_history: prior claims by this policyholder found in this insurer's records and in an industry-wide claims database covering other insurers. An empty list means no prior claims were found anywhere. Each entry gives how many days before this incident it happened, the amount claimed, and its outcome (status). words_shared_with_this_claim is a mechanical word overlap with this claim's description, not a judgement of similarity.
- location: compares the incident's city and state with the home address (no distance is calculated); for property claims, whether the incident street address exactly matches the insured property's address.
- documents: documents_mentioned_but_absent comes from fixed keyword rules (for example, the description mentions police but no police document is listed). The rules cover common document types only, so an empty list does not prove the file is complete. listed_as_not_yet_provided are documents promised but not supplied. dated_documents gives dates written in document titles, relative to the incident date (negative = before).
- weather: recorded historical weather from a weather archive for the incident date and the two days before, at the coordinates of the incident city (not the exact street). Temperatures are daily minimums and maximums in degrees Celsius, precipitation is in millimetres and snowfall in centimetres. weather_terms_in_description lists weather words the description uses. status "unavailable" means the lookup could not be done; it is not a record of calm weather."""

REVIEW_GUIDANCE = """How to review the claim:
- Check whether the whole story holds together: the incident description against the damage and the amount; the amount against the insured vehicle's value; the documents against what the description says happened; the timeline against the policy start date and any policy changes; prior claims against this claim; the incident location against the home or insured address; and the recorded weather against any weather the description mentions.
- An unusual fact is not proof of fraud on its own. New policies, prior claims, incidents away from home and large amounts all have ordinary explanations, and the case file may contain documents that supply them. Equally, a routine-looking claim can hide one specific contradiction that matters.
- Use only facts in the case file. Do not invent facts, and do not assume documents exist that are not listed."""


def build_case_file(claim, evidence):
    """Render a sanitized claim and its evidence object as the text given to a model."""
    leaked = find_label_keys(claim) + find_label_keys(evidence, path="evidence")
    if leaked:
        raise ValueError(f"build_case_file() requires sanitized inputs; found label keys at {leaked}")
    if evidence.get("claim_id") != claim.get("claim_id"):
        raise ValueError(f"evidence is for {evidence.get('claim_id')}, but the claim is {claim.get('claim_id')}")

    claim_view = copy.deepcopy(claim)
    for field in EXCLUDED_POLICYHOLDER_FIELDS:
        claim_view.get("policyholder", {}).pop(field, None)
    claim_view.get("policy", {}).pop("coverage_history", None)  # enriched copy is in evidence.policy.changes
    claim_view.pop("prior_claims", None)                          # enriched copy is in evidence.claim_history
    location = claim_view.get("incident", {}).get("location", {})
    location.pop("latitude", None)
    location.pop("longitude", None)

    return f"CLAIM:\n{compact_json(claim_view)}\n\nEVIDENCE:\n{compact_json(evidence)}"


def compact_json(value):
    return json.dumps(value, separators=(",", ":"))
