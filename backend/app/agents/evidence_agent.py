"""
Evidence-gathering agent (Stage 3).

Given ONE sanitized claim, builds a compact, structured case file:
  timeline      - key dates and the gaps between them
  policy        - coverage terms and every policy change, timed against the incident
  claim_history - prior claims, when they happened, and words they share with this claim
  location      - where the incident happened vs. the policyholder's home / insured property
  documents     - documents the description calls for but that aren't in the list,
                  documents listed as "not yet provided", and document dates vs. the incident
  weather       - real historical weather at the incident location (Open-Meteo archive)

Ground rules (these matter for the whole project):
1. No LLM calls. Everything here is a deterministic lookup, calculation or tool call.
2. Sanitized claims only. A claim that still carries label keys is rejected with an error.
3. Facts, not conclusions. This file states what is there and what isn't ("no police report
   among supporting documents", "policy changed 5 days before incident"). It never says
   whether something is suspicious. Interpreting the facts is the debate layer's job.
4. Compact. This object is pasted into every debate prompt, so it avoids repeating claim
   fields the prompt will already contain (description, amounts, raw document list).

Usage:
    from app.agents.sanitize import sanitize_claim
    from app.agents.evidence_agent import gather_evidence
    evidence = gather_evidence(sanitize_claim(raw_claim))
"""

import re
from datetime import date, timedelta

from app.agents.sanitize import find_label_keys
from app.tools.weather_tool import get_historical_weather

# Weather is checked for the incident date and the days just before it.
WEATHER_WINDOW_DAYS = 3

# Words in a description that describe weather, matched as whole words.
WEATHER_TERMS = re.compile(
    r"\b(froze|frozen|freez\w*|ice|icy|black ice|snow\w*|sleet|cold snap|hail\w*|storm\w*|wind\w*|rain\w*|flood\w*|lightning)\b",
    re.IGNORECASE,
)

# Documents a description calls for. A rule applies when the claim's description or damage
# text contains any "mentions" phrase (and none of the "unless" phrases). It is satisfied
# when any supporting document contains one of the "satisfied_by" words.
DOCUMENT_RULES = [
    {"document": "photos of damage", "mentions": [""], "unless": ["car was stolen"], "satisfied_by": ["photo"]},
    {"document": "repair estimate or invoice", "mentions": [""], "unless": ["stolen", "broken into"], "satisfied_by": ["estimate", "invoice", "valuation"]},
    {"document": "police report or incident number", "mentions": ["police", "stolen", "broken into"], "unless": [], "satisfied_by": ["police"]},
    {"document": "proof of ownership (receipts, title or bill of sale)", "mentions": ["stolen"], "unless": [], "satisfied_by": ["receipt", "title", "bill of sale"]},
    {"document": "all vehicle keys", "mentions": ["car was stolen", "vehicle was stolen"], "unless": [], "satisfied_by": ["both sets of keys", "all keys"]},
    {"document": "fire department report", "mentions": ["fire department"], "unless": [], "satisfied_by": ["fire department"]},
    {"document": "tow receipt", "mentions": ["towed"], "unless": [], "satisfied_by": ["tow"]},
    {"document": "other driver's details or police report", "mentions": ["another vehicle", "other driver", "a driver"], "unless": [], "satisfied_by": ["other driver", "police"]},
    # Home-repair trades only apply to property claims (a car's "radiator leaking" needs no plumber).
    {"document": "plumber invoice", "mentions": ["leak", "burst", "hose split"], "unless": [], "satisfied_by": ["plumber"], "only_for": "property"},
    {"document": "electrician report", "mentions": ["electrician"], "unless": [], "satisfied_by": ["electrician"], "only_for": "property"},
]

# Phrases meaning a document is promised but not actually supplied yet.
NOT_YET_PROVIDED = ["provided later", "will be provided", "to follow"]

# Common words ignored when comparing a prior claim's summary with this claim.
STOPWORDS = {
    "with", "from", "this", "that", "while", "were", "when", "into", "onto", "after", "before",
    "them", "they", "their", "there", "have", "been", "also", "only", "over", "damage", "about",
}


def gather_evidence(claim, weather_lookup=get_historical_weather):
    """Build the evidence object for one sanitized claim.

    weather_lookup can be swapped out (e.g. in tests) for a function with the same
    signature as get_historical_weather, so tests don't need the network.
    """
    leaked = find_label_keys(claim)
    if leaked:
        raise ValueError(f"gather_evidence() requires a sanitized claim; found label keys at {leaked}")

    incident_date = date.fromisoformat(claim["incident"]["date"])
    return {
        "claim_id": claim["claim_id"],
        "timeline": check_timeline(claim, incident_date),
        "policy": check_policy(claim, incident_date),
        "claim_history": check_claim_history(claim, incident_date),
        "location": check_location(claim),
        "documents": check_documents(claim, incident_date),
        "weather": check_weather(claim, incident_date, weather_lookup),
    }


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def check_timeline(claim, incident_date):
    filed_date = date.fromisoformat(claim["filed_date"])
    policy_start = date.fromisoformat(claim["policy"]["start_date"])
    change_dates = [date.fromisoformat(c["date"]) for c in claim["policy"].get("coverage_history", [])]
    last_change = max(change_dates, default=None)
    return {
        "incident_date": incident_date.isoformat(),
        "filed_date": filed_date.isoformat(),
        "policy_start_date": policy_start.isoformat(),
        "days_incident_to_filing": (filed_date - incident_date).days,
        "days_policy_start_to_incident": (incident_date - policy_start).days,
        "days_last_policy_change_to_incident": (incident_date - last_change).days if last_change else None,
    }


def check_policy(claim, incident_date):
    policy = claim["policy"]
    result = {"type": policy["policy_type"]}

    if claim["claim_type"] == "auto":
        vehicle = policy["insured_vehicle"]
        result["coverages"] = policy["coverages"]
        result["vehicle"] = f"{vehicle['year']} {vehicle['make']} {vehicle['model']}"
        result["vehicle_estimated_value"] = vehicle["estimated_value"]
        result["claim_amount_pct_of_vehicle_value"] = round(100 * claim["claim_amount"] / vehicle["estimated_value"], 1)
    else:
        prop = policy["insured_property"]
        result["property"] = f"{prop['property_type']}, built {prop['year_built']}"
        result["dwelling_coverage"] = policy["dwelling_coverage"]
        result["contents_coverage"] = policy["contents_coverage"]

    result["changes"] = [
        {"days_before_incident": (incident_date - date.fromisoformat(c["date"])).days, "change": c["change"]}
        for c in sorted(policy.get("coverage_history", []), key=lambda c: c["date"])
    ]
    return result


def check_claim_history(claim, incident_date):
    this_claim_text = f"{claim['incident']['description']} {claim['incident']['damage']}"
    this_claim_stems = {_stem(word) for word in _content_words(this_claim_text)}

    prior_claims = []
    for prior in sorted(claim.get("prior_claims", []), key=lambda p: p["date"]):
        shared = [word for word in _content_words(prior["summary"]) if _stem(word) in this_claim_stems]
        prior_claims.append({
            "days_before_incident": (incident_date - date.fromisoformat(prior["date"])).days,
            "claim_type": prior["claim_type"],
            "summary": prior["summary"],
            "amount": prior["amount"],
            "insurer": prior["insurer"],
            "words_shared_with_this_claim": sorted(set(shared)),
        })

    return {
        "prior_claims_count": len(prior_claims),
        "prior_claims_last_24_months": sum(p["days_before_incident"] <= 730 for p in prior_claims),
        "prior_claims": prior_claims,
    }


def check_location(claim):
    home = claim["policyholder"]["address"]
    incident = claim["incident"]["location"]
    result = {
        "incident_location": f"{incident['city']}, {incident['state']}",
        "policyholder_home": f"{home['city']}, {home['state']}",
        "same_city_as_home": _same(incident["city"], home["city"]) and _same(incident["state"], home["state"]),
        "same_state_as_home": _same(incident["state"], home["state"]),
    }
    if claim["claim_type"] == "property":
        insured = claim["policy"]["insured_property"]
        result["incident_address_matches_insured_property"] = all(
            _same(incident[field], insured[field]) for field in ("street", "city", "state")
        )
    return result


def check_documents(claim, incident_date):
    documents = claim["supporting_documents"]
    claim_text = f"{claim['incident']['description']} {claim['incident']['damage']}".lower()

    not_yet_provided = [d for d in documents if any(p in d.lower() for p in NOT_YET_PROVIDED)]
    provided = [d.lower() for d in documents if d not in not_yet_provided]

    expected_not_found = []
    for rule in DOCUMENT_RULES:
        if rule.get("only_for", claim["claim_type"]) != claim["claim_type"]:
            continue
        trigger = next((m for m in rule["mentions"] if m in claim_text), None)
        if trigger is None or any(u in claim_text for u in rule["unless"]):
            continue
        if not any(word in doc for doc in provided for word in rule["satisfied_by"]):
            reason = f" (description mentions '{trigger}')" if trigger else ""
            expected_not_found.append(rule["document"] + reason)

    dated_documents = []
    for doc in documents:
        for found in re.findall(r"\d{4}-\d{2}-\d{2}", doc):
            dated_documents.append({
                "document": doc,
                "days_relative_to_incident": (date.fromisoformat(found) - incident_date).days,
            })

    return {
        "documents_provided": len(documents) - len(not_yet_provided),
        "expected_but_not_found": expected_not_found,
        "listed_as_not_yet_provided": not_yet_provided,
        "dated_documents": dated_documents,  # negative = before incident, positive = after
    }


def check_weather(claim, incident_date, weather_lookup):
    location = claim["incident"]["location"]
    terms = []
    for match in WEATHER_TERMS.findall(f"{claim['incident']['description']} {claim['incident']['damage']}"):
        if match.lower() not in terms:
            terms.append(match.lower())

    if location.get("latitude") is None or location.get("longitude") is None:
        return {"status": "unavailable", "reason": "incident location has no coordinates", "weather_terms_in_description": terms}

    start_date = incident_date - timedelta(days=WEATHER_WINDOW_DAYS - 1)
    lookup = weather_lookup(location["latitude"], location["longitude"], start_date, incident_date)
    if lookup["status"] != "ok":
        return {"status": "unavailable", "reason": lookup["reason"], "weather_terms_in_description": terms}

    daily = lookup["response"].get("daily", {})
    lows = [t for t in daily.get("temperature_2m_min", []) if t is not None]
    highs = [t for t in daily.get("temperature_2m_max", []) if t is not None]
    if not lows or not highs:
        return {"status": "unavailable", "reason": "archive returned no temperature values for these dates", "weather_terms_in_description": terms}

    return {
        "status": "ok",
        "source": "Open-Meteo historical archive",
        "dates_checked": f"{start_date} to {incident_date}",
        "lowest_temp_c": min(lows),
        "highest_temp_c": max(highs),
        "days_with_low_below_freezing": sum(t < 0 for t in lows),
        "total_precipitation_mm": round(sum(v for v in daily.get("precipitation_sum", []) if v is not None), 1),
        "total_snowfall_cm": round(sum(v for v in daily.get("snowfall_sum", []) if v is not None), 1),
        "weather_terms_in_description": terms,
    }


# ---------------------------------------------------------------------------
# Small text helpers
# ---------------------------------------------------------------------------

def _same(a, b):
    return a.strip().lower() == b.strip().lower()


def _content_words(text):
    """Meaningful words (4+ letters, not common filler words), lowercased."""
    return [w for w in re.findall(r"[a-z]+", text.lower()) if len(w) >= 4 and w not in STOPWORDS]


def _stem(word):
    """Very rough stemming so 'dented' matches 'dents' and 'parked' matches 'parking'."""
    for suffix in ("ing", "ed", "es", "s", "e"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            return word[: -len(suffix)]
    return word
