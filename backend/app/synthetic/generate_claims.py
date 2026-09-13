"""
Synthetic insurance claims generator (Stage 2).

Creates exactly 40 fictional insurance claims (auto + property), each with a hidden
ground-truth label, and saves them to backend/data/synthetic_claims.json.

How it works
------------
1. SCENARIOS is a hand-written table with one row per claim: what kind of incident it is,
   whether it is fraud, how hard it should be to judge, and which "signals" to bake in.
2. build_base_claim() creates a clean, realistic claim for that row using faker + templates.
3. Each signal in the row is applied by a small function that edits the claim. For example,
   early_claim() moves the policy start date to a few days before the incident.
4. The answer (is_fraud, difficulty, signals) is stored under a separate "ground_truth" key.
   Later stages MUST remove "ground_truth" before showing a claim to any AI agent.

Two kinds of signals:
- FRAUD signals are genuine red flags (e.g. a duplicate of a claim paid 3 months ago).
- LOOK-ALIKE signals appear on legitimate claims. They look suspicious at first glance
  (e.g. a brand-new policy) but come with documents that explain them innocently. These
  make the benchmark honest: an agent can't score well by flagging anything unusual.

Everything is seeded, so every run produces the identical file. No LLM calls are made.

Run from the backend/ folder:
    .\\.venv\\Scripts\\python.exe -m app.synthetic.generate_claims
"""

import json
import math
import random
import re
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from faker import Faker

SEED = 42
NUM_CLAIMS = 40

# A fixed "today" so the output never depends on when the script is run.
AS_OF_DATE = date(2026, 9, 1)

# backend/app/synthetic/generate_claims.py -> backend/data/synthetic_claims.json
OUTPUT_PATH = Path(__file__).resolve().parents[2] / "data" / "synthetic_claims.json"

fake = Faker("en_US")
rng = random.Random(SEED)


# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

# Real US cities with approximate coordinates, so Stage 3 can look up real historical
# weather for the incident location.
#   cold = reliably below freezing in mid-winter
#   hot  = never anywhere near freezing in summer
CITIES = [
    {"city": "Minneapolis", "state": "MN", "lat": 44.9778, "lon": -93.2650, "climate": "cold"},
    {"city": "Chicago", "state": "IL", "lat": 41.8781, "lon": -87.6298, "climate": "cold"},
    {"city": "Detroit", "state": "MI", "lat": 42.3314, "lon": -83.0458, "climate": "cold"},
    {"city": "Buffalo", "state": "NY", "lat": 42.8864, "lon": -78.8784, "climate": "cold"},
    {"city": "Denver", "state": "CO", "lat": 39.7392, "lon": -104.9903, "climate": "cold"},
    {"city": "Phoenix", "state": "AZ", "lat": 33.4484, "lon": -112.0740, "climate": "hot"},
    {"city": "Houston", "state": "TX", "lat": 29.7604, "lon": -95.3698, "climate": "hot"},
    {"city": "Miami", "state": "FL", "lat": 25.7617, "lon": -80.1918, "climate": "hot"},
    {"city": "Las Vegas", "state": "NV", "lat": 36.1699, "lon": -115.1398, "climate": "hot"},
    {"city": "Tampa", "state": "FL", "lat": 27.9506, "lon": -82.4572, "climate": "hot"},
    {"city": "Seattle", "state": "WA", "lat": 47.6062, "lon": -122.3321, "climate": "mild"},
    {"city": "Portland", "state": "OR", "lat": 45.5152, "lon": -122.6784, "climate": "mild"},
    {"city": "Atlanta", "state": "GA", "lat": 33.7490, "lon": -84.3880, "climate": "mild"},
    {"city": "Charlotte", "state": "NC", "lat": 35.2271, "lon": -80.8431, "climate": "mild"},
    {"city": "Nashville", "state": "TN", "lat": 36.1627, "lon": -86.7816, "climate": "mild"},
    {"city": "Columbus", "state": "OH", "lat": 39.9612, "lon": -82.9988, "climate": "mild"},
    {"city": "Sacramento", "state": "CA", "lat": 38.5816, "lon": -121.4944, "climate": "mild"},
    {"city": "San Diego", "state": "CA", "lat": 32.7157, "lon": -117.1611, "climate": "mild"},
    {"city": "Raleigh", "state": "NC", "lat": 35.7796, "lon": -78.6382, "climate": "mild"},
    {"city": "Kansas City", "state": "MO", "lat": 39.0997, "lon": -94.5786, "climate": "mild"},
]
CITY_BY_NAME = {c["city"]: c for c in CITIES}

# (make, model, approximate price when new in USD)
VEHICLES = [
    ("Toyota", "Camry", 27000),
    ("Honda", "Civic", 24000),
    ("Ford", "F-150", 38000),
    ("Chevrolet", "Equinox", 29000),
    ("Nissan", "Altima", 26000),
    ("Subaru", "Outback", 31000),
    ("Hyundai", "Elantra", 21000),
    ("Jeep", "Grand Cherokee", 40000),
    ("Tesla", "Model 3", 42000),
    ("Kia", "Sorento", 32000),
]

# Incident templates. "amount" is either a (min, max) range in USD, or "vehicle_value"
# for total losses / thefts where the payout is roughly what the car is worth.
# "{street}" and "{shop}" are filled in when a claim is built.
INCIDENT_TEMPLATES = {
    # ----- auto -----
    "rear_end": {
        "claim_type": "auto",
        "summary": "Rear-end collision; rear bumper and tail lights",
        "description": "I was stopped at a red light on {street} when another vehicle hit the back of my car. The other driver stopped and we exchanged insurance details.",
        "damage": "Rear bumper cover, trunk lid and both tail lights damaged; car still drivable.",
        "amount": (2500, 7500),
        "documents": ["Police report", "Photos of damage (8)", "Repair estimate from {shop}", "Other driver's insurance details"],
    },
    "parking_lot": {
        "claim_type": "auto",
        "summary": "Parked car hit in a parking lot; door and fender dents",
        "description": "My parked car was hit in a grocery store parking lot on {street}. The other driver left a note with their phone number.",
        "damage": "Dented front passenger door and scraped front fender.",
        "amount": (900, 3200),
        "documents": ["Photos of damage (5)", "Repair estimate from {shop}", "Photo of the note left by the other driver"],
    },
    "deer_strike": {
        "claim_type": "auto",
        "summary": "Hit a deer; front grille, hood and headlight",
        "description": "I hit a deer that ran onto {street} around dusk. I pulled over and called the police non-emergency line.",
        "damage": "Front grille, hood and driver-side headlight damaged; radiator leaking.",
        "amount": (3000, 6500),
        "documents": ["Photos of damage (6)", "Repair estimate from {shop}", "Police incident number"],
    },
    "intersection_collision": {
        "claim_type": "auto",
        "summary": "Side-impact collision at an intersection; total loss",
        "description": "A driver ran a red light on {street} and hit the driver's side of my car. The airbags deployed and the car was towed from the scene.",
        "damage": "Driver-side doors crushed, airbags deployed, frame damage. Assessed as a total loss.",
        "amount": "vehicle_value",
        "documents": ["Police report (other driver cited for running a red light)", "Tow receipt", "Photos of damage (12)", "Total loss valuation report", "Urgent care visit summary"],
    },
    "icy_skid": {
        "claim_type": "auto",
        "summary": "Slid on ice into a guardrail; front-end damage",
        "description": "My car slid on black ice on {street} after freezing overnight temperatures and hit a guardrail.",
        "damage": "Front bumper, right headlight and right front quarter panel damaged.",
        "amount": (3500, 9000),
        "documents": ["Photos of damage (7)", "Repair estimate from {shop}", "Tow receipt"],
    },
    "vehicle_theft": {
        "claim_type": "auto",
        "summary": "Vehicle stolen from outside home",
        "description": "My car was stolen overnight from outside my home at {street}. I noticed it was gone at 6am and called the police.",
        "damage": "Vehicle stolen and not recovered.",
        "amount": "vehicle_value",
        "documents": ["Police theft report", "Both sets of keys handed to adjuster", "Vehicle title copy"],
    },
    "minor_reversing_bump": {
        "claim_type": "auto",
        "summary": "Low-speed bump while reversing; rear bumper",
        "description": "While reversing out of a parking space on {street} at walking speed, I bumped into a concrete post.",
        "damage": "Scuffed and cracked rear bumper cover.",
        "amount": (700, 1800),
        "documents": ["Photos of damage (4)", "Repair estimate from {shop}"],
    },
    # ----- property -----
    "frozen_pipe": {
        "claim_type": "property",
        "summary": "Frozen pipe burst; basement water damage",
        "description": "During a cold snap, a water pipe in an exterior wall froze and burst while we were at work. Water spread across the ground floor before we could shut off the main valve.",
        "damage": "Ground-floor drywall, carpet and baseboards damaged; mold remediation needed.",
        "amount": (6000, 18000),
        "documents": ["Plumber invoice", "Water mitigation company invoice", "Photos of damage (10)"],
    },
    "kitchen_fire": {
        "claim_type": "property",
        "summary": "Kitchen grease fire; cabinets and smoke damage",
        "description": "A pan of oil caught fire on the stove and spread to the cabinets. The fire department came and put it out.",
        "damage": "Kitchen cabinets, countertops, range hood and ceiling destroyed; smoke damage to the living room.",
        "amount": (18000, 45000),
        "documents": ["Fire department incident report", "Photos of damage (15)", "Repair estimate from {shop}", "Hotel receipts while the home was unlivable"],
    },
    "burglary": {
        "claim_type": "property",
        "summary": "Burglary; electronics and jewelry stolen",
        "description": "Our home was broken into while we were away for the weekend. The back door had been forced open.",
        "damage": "Stolen: laptop, TV, jewelry and a camera. Back door frame broken.",
        "amount": (3000, 12000),
        "documents": ["Police report", "Photos of forced back door", "Purchase receipts for stolen items", "List of stolen items"],
    },
    "washer_hose_leak": {
        "claim_type": "property",
        "summary": "Washing machine hose split; floor water damage",
        "description": "The supply hose on our washing machine split while we were asleep, and water spread through the laundry room and hallway.",
        "damage": "Laminate flooring in the hallway and laundry room ruined; lower drywall damaged.",
        "amount": (4000, 11000),
        "documents": ["Plumber invoice (replaced hose)", "Photos of damage (9)", "Repair estimate from {shop}"],
    },
    "electrical_fire": {
        "claim_type": "property",
        "summary": "Small electrical fire from a faulty outlet",
        "description": "An outlet in the bedroom sparked and started a small fire. We put it out with an extinguisher and called an electrician.",
        "damage": "Bedroom wall, carpet and furniture burned; wiring on that circuit replaced.",
        "amount": (5000, 14000),
        "documents": ["Electrician report on the failed outlet", "Photos of damage (8)", "Repair estimate from {shop}"],
    },
    "sink_leak": {
        "claim_type": "property",
        "summary": "Slow leak under kitchen sink; cabinet base",
        "description": "We noticed a slow leak under the kitchen sink.",
        "damage": "Cabinet base under the sink warped and needs replacing.",
        "amount": (1200, 3500),
        "documents": ["Plumber invoice", "Photos of damage (4)"],
    },
}

# Incidents that only make sense in freezing weather. Stage 3 can check these against
# real historical temperatures for the incident date and location.
FREEZE_KINDS = {"icy_skid", "frozen_pipe"}

# Auto incidents whose story places them at the policyholder's home ("outside my home").
AT_HOME_AUTO_KINDS = {"vehicle_theft"}

# Stories that imply a day of the week, so the incident date must fit the story.
WEEKEND_STORY_KINDS = {"burglary"}     # "while we were away for the weekend"
WORKDAY_STORY_KINDS = {"frozen_pipe"}  # "while we were at work"


# ---------------------------------------------------------------------------
# The 40 claims to generate
# ---------------------------------------------------------------------------
# Each row: (incident kind, is_fraud, difficulty, signals applied in this order)
#   easy      = the answer is clear from the evidence
#   ambiguous = one moderate red flag (fraud) or one innocent look-alike flag (legit)
#   hard      = subtle fraud, or legitimate claims with two innocent look-alike flags

SCENARIOS = [
    # ----- FRAUD / easy (5): several strong red flags at once -----
    ("minor_reversing_bump", True, "easy", ["early_claim", "severity_mismatch", "document_gap"]),
    ("washer_hose_leak", True, "easy", ["early_claim", "duplicate_claim"]),
    ("icy_skid", True, "easy", ["weather_mismatch", "early_claim"]),
    ("burglary", True, "easy", ["location_mismatch", "document_gap"]),
    ("minor_reversing_bump", True, "easy", ["severity_mismatch", "duplicate_claim"]),
    # ----- FRAUD / ambiguous (6): a single moderate red flag -----
    ("deer_strike", True, "ambiguous", ["early_claim"]),
    ("sink_leak", True, "ambiguous", ["severity_mismatch"]),
    ("rear_end", True, "ambiguous", ["location_mismatch"]),
    ("frozen_pipe", True, "ambiguous", ["weather_mismatch"]),
    ("vehicle_theft", True, "ambiguous", ["document_gap"]),
    ("electrical_fire", True, "ambiguous", ["duplicate_claim"]),
    # ----- FRAUD / hard (5): one subtle red flag -----
    ("parking_lot", True, "hard", ["duplicate_claim"]),
    ("burglary", True, "hard", ["document_inconsistency"]),
    ("vehicle_theft", True, "hard", ["recent_coverage_upgrade"]),
    ("deer_strike", True, "hard", ["amount_exceeds_value"]),
    ("washer_hose_leak", True, "hard", ["location_mismatch"]),
    # ----- LEGITIMATE / easy (9): clean, nothing unusual -----
    ("rear_end", False, "easy", []),
    ("parking_lot", False, "easy", []),
    ("deer_strike", False, "easy", []),
    ("rear_end", False, "easy", []),
    ("minor_reversing_bump", False, "easy", []),
    ("burglary", False, "easy", []),
    ("washer_hose_leak", False, "easy", []),
    ("electrical_fire", False, "easy", []),
    ("sink_leak", False, "easy", []),
    # ----- LEGITIMATE / ambiguous (8): one innocent look-alike flag -----
    ("rear_end", False, "ambiguous", ["early_claim_benign"]),
    ("frozen_pipe", False, "ambiguous", ["winter_weather_benign"]),
    ("parking_lot", False, "ambiguous", ["far_location_benign"]),
    ("kitchen_fire", False, "ambiguous", ["high_amount_benign"]),
    ("deer_strike", False, "ambiguous", ["prior_claims_benign"]),
    ("burglary", False, "ambiguous", ["early_claim_benign"]),
    ("icy_skid", False, "ambiguous", ["winter_weather_benign"]),
    ("washer_hose_leak", False, "ambiguous", ["prior_claims_benign"]),
    # ----- LEGITIMATE / hard (7): two innocent look-alike flags -----
    ("intersection_collision", False, "hard", ["early_claim_benign", "high_amount_benign"]),
    ("kitchen_fire", False, "hard", ["prior_claims_benign", "high_amount_benign"]),
    ("icy_skid", False, "hard", ["winter_weather_benign", "far_location_benign"]),
    ("frozen_pipe", False, "hard", ["winter_weather_benign", "early_claim_benign"]),
    ("rear_end", False, "hard", ["prior_claims_benign", "far_location_benign"]),
    ("kitchen_fire", False, "hard", ["high_amount_benign", "early_claim_benign"]),
    ("vehicle_theft", False, "hard", ["early_claim_benign", "prior_claims_benign"]),
]


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def distance_km(a, b):
    """Straight-line distance between two cities (haversine formula)."""
    lat1, lon1, lat2, lon2 = map(math.radians, [a["lat"], a["lon"], b["lat"], b["lon"]])
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def pick_city(climate=None, far_from=None, exclude=None):
    """Random city, optionally limited to a climate, >800 km from a city, or not a given city."""
    options = CITIES
    if climate:
        options = [c for c in options if c["climate"] == climate]
    if far_from:
        options = [c for c in options if distance_km(c, far_from) > 800]
    if exclude:
        options = [c for c in options if c["city"] != exclude["city"]]
    if not options:
        raise ValueError("No city matches the requested filters")
    return rng.choice(options)


def random_date(start, end):
    return start + timedelta(days=rng.randint(0, (end - start).days))


def any_incident_date():
    return random_date(date(2024, 10, 1), date(2026, 8, 15))


def winter_date():
    """Mid-winter dates, when cold cities are reliably below freezing."""
    start, end = rng.choice([(date(2024, 12, 20), date(2025, 2, 10)), (date(2025, 12, 20), date(2026, 2, 10))])
    return random_date(start, end)


def summer_date():
    start, end = rng.choice([(date(2025, 6, 20), date(2025, 8, 20)), (date(2026, 6, 15), date(2026, 8, 15))])
    return random_date(start, end)


def match_story_day_of_week(kind, incident_date):
    """Move the date forward (deterministically, no random draw) so it fits the story's day of the week."""
    weekday = incident_date.weekday()  # Monday = 0 ... Sunday = 6
    if kind in WEEKEND_STORY_KINDS and weekday < 5:
        return incident_date + timedelta(days=6 - weekday)  # the Sunday of that week
    if kind in WORKDAY_STORY_KINDS and weekday >= 5:
        return incident_date + timedelta(days=7 - weekday)  # the following Monday
    return incident_date


def adult_date_of_birth(date_of_birth):
    """Move a date of birth back 8 years if the person would be under 30 (no random draw)."""
    if (AS_OF_DATE - date_of_birth).days >= 30 * 365.25:
        return date_of_birth
    try:
        return date_of_birth.replace(year=date_of_birth.year - 8)
    except ValueError:  # 29 February in a non-leap year
        return date_of_birth.replace(year=date_of_birth.year - 8, day=28)


def make_location(city, street=None):
    return {
        "street": street or fake.street_address(),
        "city": city["city"],
        "state": city["state"],
        "latitude": city["lat"],
        "longitude": city["lon"],
    }


def make_vehicle(incident_date):
    make, model, new_price = rng.choice(VEHICLES)
    year = rng.randint(2013, 2024)
    # Actual cash value just before the loss: lose ~15% of value per year of age at the incident date.
    value = round(new_price * 0.85 ** max(incident_date.year - year, 0), -2)
    return {"year": year, "make": make, "model": model, "license_plate": fake.license_plate(), "estimated_value": value}


def add_prior_claim(claim, prior_date, summary, amount):
    """Add an earlier claim to the policyholder's history (from any insurer)."""
    insurer = "This policy" if prior_date >= claim["policy"]["start_date"] else "Previous insurer (industry claims database)"
    claim["prior_claims"].append({
        "date": prior_date,
        "claim_type": claim["claim_type"],
        "summary": summary,
        "amount": round(amount, 2),
        "status": "Paid",
        "insurer": insurer,
    })
    claim["prior_claims"].sort(key=lambda p: p["date"])


# ---------------------------------------------------------------------------
# Build one clean claim
# ---------------------------------------------------------------------------

def build_base_claim(scenario):
    kind = scenario["kind"]
    template = INCIDENT_TEMPLATES[kind]
    claim_type = template["claim_type"]

    # Where and when. Freeze-related incidents need matching weather: legitimate ones happen
    # in cold cities in winter; the weather_mismatch fraud puts them in hot cities in summer.
    if kind in FREEZE_KINDS and "weather_mismatch" in scenario["signals"]:
        home, incident_date = pick_city(climate="hot"), summer_date()
    elif kind in FREEZE_KINDS:
        home, incident_date = pick_city(climate="cold"), winter_date()
    else:
        home, incident_date = pick_city(), any_incident_date()
    incident_date = match_story_day_of_week(kind, incident_date)

    home_location = make_location(home)
    home_address = {k: home_location[k] for k in ("street", "city", "state")}

    # Auto incidents happen on a street in the home city; property incidents at the home itself.
    # A street name is always drawn, so the random sequence (and every other claim) is unchanged.
    street_name = fake.street_name()
    if kind in AT_HOME_AUTO_KINDS:
        street_name = home_address["street"]  # the story says it happened outside the home
    incident_location = make_location(home, street=street_name) if claim_type == "auto" else dict(home_location)

    policy = {
        "policy_number": f"{'PA' if claim_type == 'auto' else 'HO'}-{rng.randint(1000000, 9999999)}",
        "start_date": incident_date - timedelta(days=rng.randint(400, 2500)),
        "coverage_history": [],
    }
    if claim_type == "auto":
        vehicle = make_vehicle(incident_date)
        shop = f"{fake.last_name()} Auto Body"
        policy.update({
            "policy_type": "Personal Auto",
            "coverages": ["Liability", "Collision", "Comprehensive"],
            "deductible": rng.choice([250, 500, 1000]),
            "insured_vehicle": vehicle,
        })
    else:
        dwelling = rng.choice([250000, 350000, 450000, 600000])
        shop = f"{fake.last_name()} Home Restoration"
        policy.update({
            "policy_type": "Homeowners (HO-3)",
            "insured_property": {
                **home_address,
                "property_type": rng.choice(["Single-family home", "Townhouse"]),
                "year_built": rng.randint(1950, 2018),
            },
            "dwelling_coverage": dwelling,
            "contents_coverage": dwelling // 2,
            "deductible": rng.choice([500, 1000, 2500]),
        })

    if template["amount"] == "vehicle_value":
        amount = policy["insured_vehicle"]["estimated_value"] * rng.uniform(0.9, 1.0)
    else:
        amount = rng.uniform(*template["amount"])
        if claim_type == "auto":
            # A real repair bill stays well below the car's value (otherwise it would be
            # written off as a total loss). Only the amount_exceeds_value fraud breaks this.
            amount = min(amount, policy["insured_vehicle"]["estimated_value"] * 0.7)

    return {
        "claim_id": None,  # assigned after all claims are built
        "claim_type": claim_type,
        "filed_date": incident_date + timedelta(days=rng.randint(0, 4)),
        "policyholder": {
            "name": fake.name(),
            # Drawn exactly as before (so faker's random sequence is unchanged), then made at least 30
            # so the policyholder was an adult at policy start and at any prior claim.
            "date_of_birth": adult_date_of_birth(fake.date_of_birth(minimum_age=22, maximum_age=75)),
            "phone": fake.phone_number(),
            "email": fake.safe_email(),
            "address": home_address,
        },
        "policy": policy,
        "incident": {
            "date": incident_date,
            "location": incident_location,
            "description": template["description"].format(street=street_name),
            "damage": template["damage"],
        },
        "claim_amount": round(amount, 2),
        "supporting_documents": [doc.format(shop=shop) for doc in template["documents"]],
        "prior_claims": [],
        # THE ANSWER SHEET. Never show this to an agent.
        "ground_truth": {
            "is_fraud": scenario["is_fraud"],
            "difficulty": scenario["difficulty"],
            "signals": list(scenario["signals"]),
        },
    }


# ---------------------------------------------------------------------------
# FRAUD signals: genuine red flags
# ---------------------------------------------------------------------------

def early_claim(claim, scenario):
    """Policy was bought only days before the incident."""
    claim["policy"]["start_date"] = claim["incident"]["date"] - timedelta(days=rng.randint(3, 14))


def recent_coverage_upgrade(claim, scenario):
    """Theft cover was added to an existing policy just days before the car was 'stolen'."""
    claim["policy"]["coverage_history"].append({
        "date": claim["incident"]["date"] - timedelta(days=rng.randint(4, 9)),
        "change": "Added Comprehensive coverage (policy was previously Liability + Collision only)",
    })


def location_mismatch(claim, scenario):
    """The incident location doesn't fit the policyholder's story or insured address."""
    home = CITY_BY_NAME[claim["policyholder"]["address"]["city"]]
    incident = claim["incident"]
    if claim["claim_type"] == "auto":
        # Says it happened on their daily commute, but the location is 800+ km from home.
        far = pick_city(far_from=home)
        incident["location"] = make_location(far, street=incident["location"]["street"])
        incident["description"] += " This happened on my usual commute to work."
    elif scenario["difficulty"] == "hard":
        # Subtle: same city, but a different street from the insured property.
        incident["location"] = make_location(home)
    else:
        # Obvious: a different city from the insured property.
        incident["location"] = make_location(pick_city(exclude=home))


def duplicate_claim(claim, scenario):
    """Near-identical damage was already claimed and paid recently."""
    days_before = {"easy": (60, 120), "ambiguous": (150, 240), "hard": (330, 480)}[scenario["difficulty"]]
    add_prior_claim(
        claim,
        prior_date=claim["incident"]["date"] - timedelta(days=rng.randint(*days_before)),
        summary=INCIDENT_TEMPLATES[scenario["kind"]]["summary"],
        amount=claim["claim_amount"] * rng.uniform(0.9, 1.1),
    )


def severity_mismatch(claim, scenario):
    """The damage and amount are far bigger than the incident described could cause."""
    if claim["claim_type"] == "auto":
        claim["incident"]["damage"] = "Rear bumper, tailgate, both rear quarter panels and parking sensors replaced; rear frame straightening required."
        # Still a repair (not a write-off), so like every other repair claim it stays below the
        # car's value; the designed mismatch is between the minor incident and the damage listed.
        value = claim["policy"]["insured_vehicle"]["estimated_value"]
        claim["claim_amount"] = round(min(rng.uniform(14000, 21000), value * 0.7), 2)
    else:
        claim["incident"]["damage"] = "Full kitchen replacement: all cabinets, countertops, hardwood floor and subfloor, plus dishwasher and refrigerator."
        claim["claim_amount"] = round(rng.uniform(18000, 26000), 2)


def amount_exceeds_value(claim, scenario):
    """Repair bill for a repairable car is well above what the car is worth."""
    value = claim["policy"]["insured_vehicle"]["estimated_value"]
    claim["claim_amount"] = round(value * rng.uniform(1.35, 1.6), 2)


def document_gap(claim, scenario):
    """Key proof (police report, photos) is missing and what's provided is weak."""
    docs = [d for d in claim["supporting_documents"] if not d.startswith(("Police", "Photos"))]
    if scenario["kind"] == "vehicle_theft":
        docs = [d for d in docs if not d.startswith("Both sets of keys")]
        docs.append("Only one key provided; policyholder says the spare key was lost")
    elif claim["claim_type"] == "auto":
        docs = [d for d in docs if not d.startswith("Repair estimate")]
        docs.append("Repair estimate from an independent mechanic (handwritten, cash payment requested)")
    else:
        docs = [d for d in docs if not d.startswith("Purchase receipts")]
        docs.append("Receipts for stolen items: policyholder says they will be provided later")
    claim["supporting_documents"] = docs


def document_inconsistency(claim, scenario):
    """One receipt for a 'stolen' item is dated AFTER the burglary."""
    incident_date = claim["incident"]["date"]
    receipts = [
        f"Receipt: 65-inch TV, $1,899, dated {incident_date + timedelta(days=rng.randint(5, 12))}",
        f"Receipt: laptop, $1,349, dated {incident_date - timedelta(days=rng.randint(200, 600))}",
        f"Receipt: DSLR camera, $1,150, dated {incident_date - timedelta(days=rng.randint(300, 900))}",
    ]
    docs = [d for d in claim["supporting_documents"] if not d.startswith("Purchase receipts")]
    claim["supporting_documents"] = docs + receipts
    # The claimed total must at least cover the itemised receipts (the jewelry and door are extra).
    receipts_total = 1899 + 1349 + 1150
    if claim["claim_amount"] < receipts_total + 1000:
        claim["claim_amount"] = round(claim["claim_amount"] + receipts_total, 2)


def weather_mismatch(claim, scenario):
    """A freeze-related incident in a hot city in summer.
    Handled in build_base_claim (it picks a hot city and a summer date); nothing more to do."""


# ---------------------------------------------------------------------------
# LOOK-ALIKE signals: suspicious at first glance, innocent with the full picture
# ---------------------------------------------------------------------------

def early_claim_benign(claim, scenario):
    """New policy, but because they just bought the car/home, with strong corroboration."""
    start = claim["incident"]["date"] - timedelta(days=rng.randint(6, 25))
    claim["policy"]["start_date"] = start
    docs = claim["supporting_documents"]
    if claim["claim_type"] == "auto":
        docs.append(f"Bill of sale: vehicle purchased {start - timedelta(days=1)} (policy started with the purchase)")
        if scenario["kind"] in ("rear_end", "intersection_collision"):
            docs.append("Letter from the other driver's insurer accepting fault")
        if scenario["kind"] == "vehicle_theft":
            docs.append("Neighbor's doorbell camera video showing the car being stolen")
    else:
        docs.append(f"Home purchase closing documents dated {start}")
        docs.append("Pre-purchase home inspection report")


def far_location_benign(claim, scenario):
    """Incident far from home, explained by a documented road trip."""
    home = CITY_BY_NAME[claim["policyholder"]["address"]["city"]]
    # A freeze incident on a road trip still needs to happen somewhere cold.
    climate = "cold" if scenario["kind"] in FREEZE_KINDS else None
    far = pick_city(climate=climate, far_from=home)
    incident = claim["incident"]
    incident["location"] = make_location(far, street=incident["location"]["street"])
    incident["description"] = f"We were on a family road trip to {far['city']}. " + incident["description"]
    claim["supporting_documents"] += [
        f"Hotel receipt ({far['city']}, {far['state']}) covering the incident date",
        "Fuel receipts along the route",
    ]


def prior_claims_benign(claim, scenario):
    """Has claimed before, but years ago and for unrelated, modest incidents."""
    unrelated_kinds = [
        k for k, t in INCIDENT_TEMPLATES.items()
        if k != scenario["kind"] and t["claim_type"] == claim["claim_type"]
        and t["amount"] != "vehicle_value" and t["amount"][1] <= 15000
    ]
    for kind in rng.sample(unrelated_kinds, rng.randint(1, 2)):
        low, high = INCIDENT_TEMPLATES[kind]["amount"]
        add_prior_claim(
            claim,
            prior_date=claim["incident"]["date"] - timedelta(days=rng.randint(3 * 365, 7 * 365)),
            summary=INCIDENT_TEMPLATES[kind]["summary"],
            amount=rng.uniform(low, high),
        )


def high_amount_benign(claim, scenario):
    """Large claim, but the damage is severe and independently verified."""
    if claim["claim_type"] == "auto":
        claim["supporting_documents"].append("Written statement from an independent witness")
    else:
        claim["supporting_documents"].append("Independent adjuster's on-site inspection report")


def winter_weather_benign(claim, scenario):
    """A freeze-related incident in a cold city in winter (consistent with real weather).
    Handled in build_base_claim (it picks a cold city and a winter date); nothing more to do."""


SIGNAL_FUNCTIONS = {
    # fraud
    "early_claim": early_claim,
    "recent_coverage_upgrade": recent_coverage_upgrade,
    "location_mismatch": location_mismatch,
    "duplicate_claim": duplicate_claim,
    "severity_mismatch": severity_mismatch,
    "amount_exceeds_value": amount_exceeds_value,
    "document_gap": document_gap,
    "document_inconsistency": document_inconsistency,
    "weather_mismatch": weather_mismatch,
    # look-alike (legitimate)
    "early_claim_benign": early_claim_benign,
    "far_location_benign": far_location_benign,
    "prior_claims_benign": prior_claims_benign,
    "high_amount_benign": high_amount_benign,
    "winter_weather_benign": winter_weather_benign,
}


def add_routine_policy_changes(claim):
    """Harmless policy edits on some long-standing policies, so that 'the policy was changed'
    on its own never gives the answer away."""
    start, incident_date = claim["policy"]["start_date"], claim["incident"]["date"]
    policy_age_days = (incident_date - start).days
    if policy_age_days > 400 and rng.random() < 0.35:
        claim["policy"]["coverage_history"].append({
            "date": start + timedelta(days=rng.randint(30, policy_age_days - 90)),
            "change": rng.choice([
                "Added roadside assistance",
                "Updated mailing address",
                "Raised deductible to lower premium",
                "Added a second named driver" if claim["claim_type"] == "auto" else "Added a home security system discount",
            ]),
        })
        claim["policy"]["coverage_history"].sort(key=lambda change: change["date"])


# ---------------------------------------------------------------------------
# Generate, check, save, summarise
# ---------------------------------------------------------------------------

def generate_claims():
    fake.seed_instance(SEED)
    rng.seed(SEED)

    scenarios = [
        {"kind": kind, "is_fraud": is_fraud, "difficulty": difficulty, "signals": signals}
        for kind, is_fraud, difficulty, signals in SCENARIOS
    ]
    rng.shuffle(scenarios)  # so fraud cases aren't grouped together by claim ID

    claims = []
    for number, scenario in enumerate(scenarios, start=1):
        claim = build_base_claim(scenario)
        for signal in scenario["signals"]:
            SIGNAL_FUNCTIONS[signal](claim, scenario)
        add_routine_policy_changes(claim)
        claim["claim_id"] = f"CLM-{number:04d}"
        claims.append(claim)

    validate(claims)
    return claims


def validate(claims):
    """Basic sanity checks so we never save an impossible claim."""
    assert len(claims) == NUM_CLAIMS, f"Expected {NUM_CLAIMS} claims, got {len(claims)}"
    for claim in claims:
        cid, incident_date = claim["claim_id"], claim["incident"]["date"]
        assert claim["policy"]["start_date"] < incident_date, f"{cid}: incident before policy start"
        assert incident_date <= claim["filed_date"] <= AS_OF_DATE, f"{cid}: bad filed date"
        assert claim["claim_amount"] > 0, f"{cid}: non-positive amount"
        assert all(p["date"] < incident_date for p in claim["prior_claims"]), f"{cid}: prior claim after incident"
        assert all(c["date"] < incident_date for c in claim["policy"]["coverage_history"]), f"{cid}: policy change after incident"

        # Consistency rules added with the benchmark data fixes (see docs/METHODOLOGY.md).
        description = claim["incident"]["description"]
        if "outside my home" in description:
            assert claim["incident"]["location"]["street"] == claim["policyholder"]["address"]["street"], f"{cid}: home street mismatch"
        if "away for the weekend" in description:
            assert incident_date.weekday() >= 5, f"{cid}: weekend story dated on a weekday"
        if "while we were at work" in description:
            assert incident_date.weekday() < 5, f"{cid}: workday story dated on a weekend"
        if claim["claim_type"] == "auto" and "amount_exceeds_value" not in claim["ground_truth"]["signals"]:
            assert claim["claim_amount"] <= claim["policy"]["insured_vehicle"]["estimated_value"], f"{cid}: amount above vehicle value"
        receipts_total = sum(int(amount.replace(",", "")) for doc in claim["supporting_documents"]
                             if doc.startswith("Receipt:") for amount in re.findall(r"\$([\d,]+)", doc))
        assert receipts_total <= claim["claim_amount"], f"{cid}: itemised receipts exceed the claimed amount"
        earliest_event = min([claim["policy"]["start_date"]] + [p["date"] for p in claim["prior_claims"]])
        assert (earliest_event - claim["policyholder"]["date_of_birth"]).days >= 18 * 365.25, f"{cid}: policyholder under 18"


def print_summary(claims):
    total = len(claims)
    fraud = sum(c["ground_truth"]["is_fraud"] for c in claims)
    legit = total - fraud

    print(f"Saved {total} synthetic claims to {OUTPUT_PATH.relative_to(OUTPUT_PATH.parents[1])}")
    print()
    print(f"Total claims:  {total}")
    print(f"  Fraud:       {fraud} ({fraud / total:.0%})")
    print(f"  Legitimate:  {legit} ({legit / total:.0%})")
    print()
    print(f"{'By difficulty':<16}{'fraud':>6}{'legit':>7}{'total':>7}")
    for level in ("easy", "ambiguous", "hard"):
        in_level = [c for c in claims if c["ground_truth"]["difficulty"] == level]
        n_fraud = sum(c["ground_truth"]["is_fraud"] for c in in_level)
        print(f"  {level:<14}{n_fraud:>6}{len(in_level) - n_fraud:>7}{len(in_level):>7}")
    print()
    print("By claim type:")
    for claim_type, count in sorted(Counter(c["claim_type"] for c in claims).items()):
        print(f"  {claim_type:<14}{count:>3}")
    print()
    fraud_signals = Counter(s for c in claims if c["ground_truth"]["is_fraud"] for s in c["ground_truth"]["signals"])
    benign_signals = Counter(s for c in claims if not c["ground_truth"]["is_fraud"] for s in c["ground_truth"]["signals"])
    print("Fraud red flags baked in (number of claims):")
    for signal, count in fraud_signals.most_common():
        print(f"  {signal:<26}{count:>3}")
    print()
    print("Innocent look-alike flags on legitimate claims:")
    for signal, count in benign_signals.most_common():
        print(f"  {signal:<26}{count:>3}")


def main():
    claims = generate_claims()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(claims, f, indent=2, default=str)  # default=str writes dates as YYYY-MM-DD
    print_summary(claims)


if __name__ == "__main__":
    main()
