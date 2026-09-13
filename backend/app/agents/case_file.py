"""
The case file: exactly what every decision-making agent is shown about a claim.

The naive baseline (Stage 4) and the debate agents (Stage 5+) must all build their prompt
input with build_case_file(), and use the shared CASE_FILE_GUIDE and DECISION_DEFINITIONS
text. That way the Stage 11 comparison is same inputs, same model, same settings: only the
architecture differs.

What goes in: the sanitized claim + its Stage 3 evidence object, as compact JSON.
What is left out, identically for every agent:
- personal identifiers (name, phone, email, date of birth): irrelevant to whether a loss is
  genuine, and a known source of model bias
- data the evidence object already carries in enriched form (policy change history, prior
  claims) and raw coordinates (only needed for the weather lookup)
"""

import copy
import json

from app.agents.sanitize import find_label_keys

EXCLUDED_POLICYHOLDER_FIELDS = ("name", "phone", "email", "date_of_birth")

DECISION_DEFINITIONS = """APPROVE = the claim describes a genuine loss, as reported, and should be paid.
DENY = the claim is fraudulent or materially misrepresented and should not be paid as submitted."""

CASE_FILE_GUIDE = """The case file has two parts.

CLAIM: the claim as submitted - claim type, filing date, policyholder's home address, the policy
(policy type, start date, coverages, the insured vehicle and its estimated value, or the insured
property and coverage limits), the incident (date, location, description, damage), the claimed
amount, and the list of supporting documents. Personal identifiers have been removed.

EVIDENCE: facts gathered automatically for this claim. They are neutral observations, not conclusions.
- timeline: key dates and the number of days between policy start, the latest policy change, the incident and filing
- policy: coverage details, and every policy change with how many days before the incident it was made
- claim_history: this policyholder's prior claims at any insurer, how long before this incident, and words each prior claim shares with this claim
- location: incident city vs. home city; for property claims, whether the incident address matches the insured property
- documents: documents the description refers to that are absent from the list, documents listed as not yet provided, and dates written on documents relative to the incident (negative = before)
- weather: recorded historical weather at the incident location for the incident date and the two days before, plus any weather words used in the description (status "unavailable" means the lookup could not be done)"""


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

    return f"CLAIM:\n{_compact_json(claim_view)}\n\nEVIDENCE:\n{_compact_json(evidence)}"


def _compact_json(value):
    return json.dumps(value, separators=(",", ":"))
