"""
Benchmark solvability check (no model calls).

For every claim labelled fraud, check that each fraud signal the Stage 2 generator designed
into it is still present in the current data. A fraud label with no fraud evidence left would
be a broken test case, not a hard one, and no architecture could solve it.

Each check measures the claim's own data (through the Stage 3 evidence agent, with weather
lookups switched off) against the parameters the generator used when it created that signal.

Measured details are printed for development-set claims and for failed checks only, so
held-out claims are not inspected beyond pass/fail.

Run from the backend/ folder:
    .\\.venv\\Scripts\\python.exe -m app.synthetic.check_signals
"""

import json
import sys

from app.agents.evidence_agent import gather_evidence
from app.agents.sanitize import sanitize_claim
from app.synthetic.eval_split import is_dev_claim
from app.synthetic.generate_claims import CITY_BY_NAME, OUTPUT_PATH

FREEZE_WORDS = ("froze", "frozen", "freezing", "black ice")


def no_weather_lookup(latitude, longitude, start_date, end_date):
    return {"status": "unavailable", "reason": "not needed for this check"}


# ---------------------------------------------------------------------------
# One check per designed signal: (present, what was measured)
# Parameters match the signal functions in generate_claims.py.
# ---------------------------------------------------------------------------

def check_early_claim(claim, evidence):
    days = evidence["timeline"]["days_policy_start_to_incident"]
    return days <= 14, f"policy started {days} days before the incident (designed: 3-14)"


def check_recent_coverage_upgrade(claim, evidence):
    upgrades = [c for c in evidence["policy"]["changes"] if "Added Comprehensive" in c["change"] and c["days_before_incident"] <= 9]
    detail = f"Comprehensive added {upgrades[0]['days_before_incident']} days before" if upgrades else "no Comprehensive addition in the 9 days before"
    return bool(upgrades), detail + " (designed: 4-9)"


def check_location_mismatch(claim, evidence):
    location = evidence["location"]
    if claim["claim_type"] == "auto":
        present = not location["same_city_as_home"] and "usual commute" in claim["incident"]["description"]
        return present, f"'usual commute' incident in {location['incident_location']}, home {location['policyholder_home']}"
    present = not location["incident_address_matches_insured_property"]
    return present, f"incident address matches insured property: {location['incident_address_matches_insured_property']}"


def check_duplicate_claim(claim, evidence):
    amount = claim["claim_amount"]
    matches = [
        p for p in evidence["claim_history"]["prior_claims"]
        if p["claim_type"] == claim["claim_type"] and p["days_before_incident"] <= 480
        and 0.85 <= p["amount"] / amount <= 1.15 and len(p["words_shared_with_this_claim"]) >= 2
    ]
    if not matches:
        return False, "no prior claim within 480 days with a similar amount and description"
    match = matches[0]
    return True, (f"prior claim {match['days_before_incident']} days earlier, ${match['amount']:,.2f} vs ${amount:,.2f}, "
                  f"shared words {match['words_shared_with_this_claim']}")


def check_severity_mismatch(claim, evidence):
    amount = claim["claim_amount"]
    description, damage = claim["incident"]["description"], claim["incident"]["damage"]
    if claim["claim_type"] == "auto":
        text_ok = "walking speed" in description and "frame straightening" in damage
        low, high = 14000, 21000
    else:
        text_ok = "slow leak" in description and "Full kitchen replacement" in damage
        low, high = 18000, 26000
    amount_ok = low <= amount <= high
    return text_ok and amount_ok, (f"minor incident vs extensive damage text: {text_ok}; "
                                   f"amount ${amount:,.2f} (designed: ${low:,}-${high:,})")


def check_amount_exceeds_value(claim, evidence):
    ratio = claim["claim_amount"] / claim["policy"]["insured_vehicle"]["estimated_value"]
    return 1.35 <= ratio <= 1.6, f"amount is {ratio:.0%} of vehicle value (designed: 135-160%)"


def check_document_gap(claim, evidence):
    documents = evidence["documents"]
    gaps = documents["documents_mentioned_but_absent"] + documents["listed_as_not_yet_provided"]
    return bool(gaps), f"gaps found: {gaps}" if gaps else "no missing or not-yet-provided documents"


def check_document_inconsistency(claim, evidence):
    after = [d for d in evidence["documents"]["dated_documents"]
             if d["document"].startswith("Receipt") and d["days_relative_to_incident"] > 0]
    detail = f"receipt dated {after[0]['days_relative_to_incident']} days after the incident" if after else "no receipt dated after the incident"
    return bool(after), detail


def check_weather_mismatch(claim, evidence):
    location = claim["incident"]["location"]
    month = int(claim["incident"]["date"][5:7])
    freeze_story = any(word in claim["incident"]["description"].lower() for word in FREEZE_WORDS)
    hot_city = CITY_BY_NAME[location["city"]]["climate"] == "hot"
    present = freeze_story and hot_city and month in (6, 7, 8)
    return present, f"freeze story: {freeze_story}; {location['city']} (hot: {hot_city}); month {month}"


SIGNAL_CHECKS = {
    "early_claim": check_early_claim,
    "recent_coverage_upgrade": check_recent_coverage_upgrade,
    "location_mismatch": check_location_mismatch,
    "duplicate_claim": check_duplicate_claim,
    "severity_mismatch": check_severity_mismatch,
    "amount_exceeds_value": check_amount_exceeds_value,
    "document_gap": check_document_gap,
    "document_inconsistency": check_document_inconsistency,
    "weather_mismatch": check_weather_mismatch,
}


def check_claim(raw_claim):
    """[(signal, present, detail)] for every designed fraud signal of one claim."""
    claim = sanitize_claim(raw_claim)
    evidence = gather_evidence(claim, weather_lookup=no_weather_lookup)
    return [(signal, *SIGNAL_CHECKS[signal](claim, evidence)) for signal in raw_claim["ground_truth"]["signals"]]


def main():
    sys.stdout.reconfigure(errors="replace")
    with open(OUTPUT_PATH, encoding="utf-8") as f:
        fraud_claims = [c for c in json.load(f) if c["ground_truth"]["is_fraud"]]

    missing = 0
    print(f"{'claim':<9} {'set':<9} {'designed signal':<24} {'present':<8} detail (dev claims and failures only)")
    for raw_claim in fraud_claims:
        claim_set = "dev" if is_dev_claim(raw_claim["claim_id"]) else "held-out"
        for signal, present, detail in check_claim(raw_claim):
            missing += not present
            shown = detail if (claim_set == "dev" or not present) else ""
            print(f"{raw_claim['claim_id']:<9} {claim_set:<9} {signal:<24} {'yes' if present else 'NO':<8} {shown}")
    print(f"\n{len(fraud_claims)} fraud claims checked; {missing} designed signal(s) missing")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
