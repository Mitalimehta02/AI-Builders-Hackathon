"""
Fill the Stage 11 result markers in the submission documents from the final /analytics output.

Why this exists: copying numbers by hand into three documents under deadline pressure is how a wrong
number ends up on a slide. This script takes every figure from one place - the same computation the
Analytics page shows (backend/app/routes/analytics.py) - and fills the markers in

    README.md, DECK_CONTENT.md, VIDEO_SCRIPT.md    (repository root; a missing file is skipped with a warning)

It enforces the PROJECT_PLAN.md Part 5b reporting rules itself, so a document cannot break them by accident:
- Raw counts only. Every filled value is checked, and the script stops if any contains a percentage.
- The "always approve" reference is built into every accuracy value. There is no marker that gives an
  accuracy count on its own.
- Every document that reports results must contain the sample note. It states the sample size and the
  pre-registration and, if fewer than all 15 claims completed, adds the truncation and failure disclosure
  automatically.
- A gap of one or two claims between the systems is described as directionally suggestive at most.
Before filling, the analytics are checked: they must be for the pre-registered sample (seed and claim-ID
hash), internally consistent, and final - or explicitly reported as truncated under the stopping rule.
Nothing is written unless every document passes every check.

Markers
-------
    [[PLACEHOLDER:key]]      a result; run with --list-keys to see every key and what it fills in.
                             An unknown key, or a marker without a key, stops the script.
    [[LIVE_URL:frontend]]    the deployed site  (filled only when --frontend-url is given)
    [[LIVE_URL:backend]]     the deployed API   (filled only when --backend-url is given)

Usage, from the repository root
-------------------------------
    # Once the batch has finished. Commit first, so the filled documents are a reviewable diff.
    backend\\.venv\\Scripts\\python.exe scripts\\fill_results.py --check    # validate and print values, write nothing
    backend\\.venv\\Scripts\\python.exe scripts\\fill_results.py            # fill the documents in place

    # The run did not finish before the deadline: report the first claims under the stopping rule.
    backend\\.venv\\Scripts\\python.exe scripts\\fill_results.py --truncated-at-deadline

    # Other sources: a running API, or a saved /analytics response.
    ... --from-url http://localhost:8000/analytics
    ... --from-file analytics.json

By default it reads the results files directly through compute_analytics(), so no server needs to be
running (use the backend venv interpreter, which has the backend's packages). The analytics used are
saved to backend/data/stage11_final_analytics.json next to the filled documents, so every figure can be
traced back.
"""

import argparse
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
SAMPLE_PATH = BACKEND_DIR / "data" / "stage11_sample.json"
DOCUMENTS = ("README.md", "DECK_CONTENT.md", "VIDEO_SCRIPT.md")
SNAPSHOT_PATH = Path("backend") / "data" / "stage11_final_analytics.json"   # relative to the documents' folder

SUGGESTIVE_ONLY_WITHIN = 2       # Part 5b: a gap of one or two claims is directionally suggestive at most
REQUIRED_KEY = "sample_and_truncation_note"
ACCURACY_KEYS = ("baseline_accuracy", "claimlens_accuracy", "accuracy_reading")

PLACEHOLDER = re.compile(r"\[\[PLACEHOLDER(.*?)\]\]")
KEYED = re.compile(r":([a-z_]+)")
LIVE_URL = re.compile(r"\[\[LIVE_URL:(frontend|backend)\]\]")
PERCENTAGE = re.compile(r"%|percent", re.IGNORECASE)

# Every key a document may use, and what it becomes. render_values() must produce exactly these keys.
KEY_DESCRIPTIONS = {
    REQUIRED_KEY: "REQUIRED wherever results appear: sample size, pre-registration, fraud/legitimate mix, and the "
                  "truncation / failure disclosure when fewer than all claims completed",
    "claims_complete": "completed claims the figures cover, e.g. '12'",
    "claims_total": "pre-registered sample size, '15'",
    "fraud_count": "completed fraud claims, e.g. '4'",
    "legitimate_count": "completed legitimate claims, e.g. '8'",
    "always_approve": "the always-approve reference on its own, 'Y of N'",
    "baseline_accuracy": "'X of N correct (always approve: Y of N)'",
    "claimlens_accuracy": "'X of N correct (always approve: Y of N)'",
    "accuracy_reading": "plain-language accuracy comparison, including always approve and the within-two-claims rule",
    "baseline_confidently_wrong": "'W of H high-confidence answers wrong' (confidence 80 or above)",
    "claimlens_confidently_wrong": "'W of H high-confidence answers wrong' (final tier HIGH)",
    "claimlens_confidently_wrong_before_cap": "the same for ClaimLens using the tier before the point-accounting cap",
    "confidently_wrong_reading": "plain-language comparison of confidently wrong answers, with the within-two-claims rule",
    "baseline_legitimate_denied": "'X of L legitimate claims' recommended for denial",
    "claimlens_legitimate_denied": "'X of L legitimate claims' recommended for denial",
    "baseline_fraud_approved": "'X of F fraud claims' recommended for approval",
    "claimlens_fraud_approved": "'X of F fraud claims' recommended for approval",
    "baseline_fraud_dollars_caught": "'$caught of $total' claimed on fraud claims recommended for denial",
    "claimlens_fraud_dollars_caught": "'$caught of $total' claimed on fraud claims recommended for denial",
    "claimlens_auto_resolved": "'X of N claims' auto-resolved without a human",
    "claimlens_auto_resolved_fraud": "'X of A': fraud claims among the auto-resolved ones",
    "claimlens_human_review": "'X of N claims' sent to an adjuster",
    "claimlens_tier_counts": "'HIGH a, MEDIUM b, LOW c'",
    "claimlens_cap_applied": "'X of N claims (W of them with a wrong decision)' where the cap lowered HIGH to MEDIUM",
    "claimlens_orderings_disagreed": "'X of N claims' where the two Judge orderings reached different decisions",
    "adjuster_hours_saved": "'H hours (A auto-resolved claims at an assumed M minutes of manual review each)'",
}


class StopError(Exception):
    """A check failed. Raised before anything is written."""


# ---------------------------------------------------------------- reading and checking the analytics

def load_analytics(args):
    if args.from_file:
        return json.loads(Path(args.from_file).read_text(encoding="utf-8")), f"file {args.from_file}"
    if args.from_url:
        with urllib.request.urlopen(args.from_url, timeout=120) as response:  # a sleeping free instance can take a minute
            return json.loads(response.read().decode("utf-8")), f"URL {args.from_url}"
    sys.path.insert(0, str(BACKEND_DIR))
    try:
        from app.routes.analytics import compute_analytics
    except ImportError as error:
        raise StopError(f"could not load the backend ({error}). Run this with backend\\.venv\\Scripts\\python.exe, "
                        "or use --from-url / --from-file.")
    return compute_analytics(), "backend/data results files via compute_analytics()"


def is_count(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def check_analytics(data, sample, truncated_at_deadline):
    """Stop unless the analytics are for the pre-registered sample, consistent, and final (or declared truncated)."""
    problems = []
    evaluation, progress, composition = data["evaluation"], data["progress"], data["composition"]
    reference, baseline, lens = data["reference"], data["baseline"], data["claimlens"]
    complete, total = progress["complete"], progress["total"]

    if evaluation["claim_ids_sha256"] != sample["claim_ids_sha256"] or evaluation["seed"] != sample["seed"]:
        problems.append("these analytics are not for the pre-registered sample (seed or claim-ID hash differs)")
    if evaluation["sample_size"] != sample["sample_size"] or total != sample["sample_size"]:
        problems.append(f"sample size is {total}, but {sample['sample_size']} claims were pre-registered")
    if not is_count(complete) or complete == 0:
        problems.append("no claims are complete, so there is nothing to report")
    if not progress["is_final"] and not truncated_at_deadline:
        problems.append(f"the run is not finished ({progress['reported']} of {total} claims reported; batch running: "
                        f"{progress['batch_running']}). Wait for it to finish, or pass --truncated-at-deadline to report "
                        "the first claims under the pre-registered stopping rule.")
    if progress["complete"] + progress["failed"] != progress["reported"]:
        problems.append("progress counts are inconsistent (complete + failed != reported)")
    if composition["fraud"] + composition["legitimate"] != complete:
        problems.append("fraud + legitimate does not equal the completed claims")
    if reference["always_approve_correct"] != composition["legitimate"] or reference["out_of"] != complete:
        problems.append("the always-approve reference does not match the completed claims")

    for name, system in (("baseline", baseline), ("claimlens", lens)):
        for key in ("correct", "high_confidence", "high_confidence_wrong", "false_positives", "false_negatives"):
            if not is_count(system[key]) or system[key] > complete:
                problems.append(f"{name}.{key} must be a whole count from 0 to {complete}, got {system[key]!r}")
        if system["high_confidence_wrong"] > system["high_confidence"]:
            problems.append(f"{name}: more confidently wrong answers than high-confidence answers")
        if system["false_positives"] > composition["legitimate"] or system["false_negatives"] > composition["fraud"]:
            problems.append(f"{name}: wrong-decision counts exceed the claims they are counted over")
        if not 0 <= system["fraud_amount_caught"] <= system["fraud_amount_total"]:
            problems.append(f"{name}: fraud dollars caught must be between 0 and the fraud total")
    for key in ("auto_resolved", "auto_resolved_fraud", "human_review", "tier_before_cap_high",
                "tier_before_cap_high_wrong", "cap_applied", "cap_applied_on_wrong_decisions", "orderings_disagreed"):
        if not is_count(lens[key]) or lens[key] > complete:
            problems.append(f"claimlens.{key} must be a whole count from 0 to {complete}, got {lens[key]!r}")
    if lens["auto_resolved"] + lens["human_review"] != complete:
        problems.append("claimlens: auto-resolved + human review does not equal the completed claims")
    if sum(lens["tier_counts"].values()) != complete:
        problems.append("claimlens: tier counts do not add up to the completed claims")
    if lens["auto_resolved_fraud"] > lens["auto_resolved"] or lens["tier_before_cap_high_wrong"] > lens["tier_before_cap_high"]:
        problems.append("claimlens: a sub-count is larger than the count it belongs to")
    if lens["adjuster_hours_saved"] != round(lens["auto_resolved"] * lens["manual_review_minutes_assumed"] / 60, 1):
        problems.append("claimlens: adjuster hours saved does not match auto-resolved claims x assumed minutes")
    if baseline["fraud_amount_total"] != lens["fraud_amount_total"]:
        problems.append("the two systems report different fraud totals for the same claims")

    if problems:
        raise StopError("the analytics failed checks:\n  - " + "\n  - ".join(problems))


# ---------------------------------------------------------------- turning counts into text

def plural(count, word, word_plural=None):
    return f"{count} {word if count == 1 else (word_plural or word + 's')}"


def dollars(amount):
    return f"${amount:,.0f}"


def compare(lens_count, baseline_count, singular, plural_word, complete):
    """ClaimLens against the baseline, with the within-two-claims rule applied."""
    gap = lens_count - baseline_count
    if gap == 0:
        return f"The two systems have the same number of {plural_word}."
    sentence = f"ClaimLens has {abs(gap)} {'more' if gap > 0 else 'fewer'} {singular if abs(gap) == 1 else plural_word} than the baseline"
    if abs(gap) <= SUGGESTIVE_ONLY_WITHIN:
        return sentence + ": a difference within two claims, so directionally suggestive at most."
    return sentence + f": on {complete} claims, an indication from a small sample, not an established rate."


def against_always_approve(name, correct, reference):
    gap = correct - reference
    if gap == 0:
        return f"{name} ties it"
    return f"{name} is {plural(abs(gap), 'claim')} {'above' if gap > 0 else 'below'} it"


def sample_note(data, sample):
    progress, composition, evaluation = data["progress"], data["composition"], data["evaluation"]
    complete, total, reported, failed = progress["complete"], progress["total"], progress["reported"], progress["failed"]
    note = (f"These figures cover {plural(complete, 'completed claim')} ({composition['fraud']} fraud, "
            f"{composition['legitimate']} legitimate) from a stratified random sample of {total} of the "
            f"{evaluation['held_out_size']} held-out claims, pre-registered on {evaluation['registered_on']} (seed "
            f"{evaluation['seed']}) before any held-out claim was run. With a sample this small, results are raw counts.")
    if complete == total:
        return note + f" All {total} pre-registered claims completed; nothing was truncated."
    if reported < total:
        selected = sample["label_counts"]
        note += (f" Truncated under the pre-registered stopping rule: the run did not finish before the deadline, so only "
                 f"the first {reported} of the {total} claims in the fixed processing order (ascending claim ID) are "
                 f"reported. That subset was set by the order, not chosen after seeing results. The full sample was "
                 f"{selected['fraud']['selected']} fraud and {selected['legitimate']['selected']} legitimate.")
    if failed:
        note += (f" {plural(failed, 'claim')} failed after repeated attempts; "
                 f"{'it keeps its position and is' if failed == 1 else 'they keep their positions and are'} not counted.")
    return note


def render_values(data, sample):
    progress, composition, reference = data["progress"], data["composition"], data["reference"]
    base, lens = data["baseline"], data["claimlens"]
    n, fraud, legit = progress["complete"], composition["fraud"], composition["legitimate"]
    approve_all = reference["always_approve_correct"]
    tiers = lens["tier_counts"]

    def accuracy(system):
        return f"{system['correct']} of {n} correct (always approve: {approve_all} of {n})"

    def confidently_wrong(wrong, high):
        return f"{wrong} of {plural(high, 'high-confidence answer')} wrong"

    accuracy_reading = (
        f"Correct recommendations on {n} claims: ClaimLens {lens['correct']}, baseline {base['correct']}, always approve "
        f"{approve_all}. Against always approving, {against_always_approve('ClaimLens', lens['correct'], approve_all)}, and "
        f"{against_always_approve('the baseline', base['correct'], approve_all)}. "
        + compare(lens["correct"], base["correct"], "correct recommendation", "correct recommendations", n))
    confidently_wrong_reading = (
        f"Confidently wrong answers: ClaimLens {lens['high_confidence_wrong']} of {lens['high_confidence']} HIGH-tier answers, "
        f"baseline {base['high_confidence_wrong']} of {base['high_confidence']} answers at confidence 80 or above. "
        + compare(lens["high_confidence_wrong"], base["high_confidence_wrong"], "confidently wrong answer",
                  "confidently wrong answers", n)
        + f" Before the point-accounting cap, ClaimLens had {lens['tier_before_cap_high_wrong']} wrong of "
          f"{lens['tier_before_cap_high']} HIGH-tier answers.")

    return {
        REQUIRED_KEY: sample_note(data, sample),
        "claims_complete": str(n),
        "claims_total": str(progress["total"]),
        "fraud_count": str(fraud),
        "legitimate_count": str(legit),
        "always_approve": f"{approve_all} of {n}",
        "baseline_accuracy": accuracy(base),
        "claimlens_accuracy": accuracy(lens),
        "accuracy_reading": accuracy_reading,
        "baseline_confidently_wrong": confidently_wrong(base["high_confidence_wrong"], base["high_confidence"]),
        "claimlens_confidently_wrong": confidently_wrong(lens["high_confidence_wrong"], lens["high_confidence"]),
        "claimlens_confidently_wrong_before_cap": confidently_wrong(lens["tier_before_cap_high_wrong"], lens["tier_before_cap_high"]),
        "confidently_wrong_reading": confidently_wrong_reading,
        "baseline_legitimate_denied": f"{base['false_positives']} of {plural(legit, 'legitimate claim')}",
        "claimlens_legitimate_denied": f"{lens['false_positives']} of {plural(legit, 'legitimate claim')}",
        "baseline_fraud_approved": f"{base['false_negatives']} of {plural(fraud, 'fraud claim')}",
        "claimlens_fraud_approved": f"{lens['false_negatives']} of {plural(fraud, 'fraud claim')}",
        "baseline_fraud_dollars_caught": f"{dollars(base['fraud_amount_caught'])} of {dollars(base['fraud_amount_total'])}",
        "claimlens_fraud_dollars_caught": f"{dollars(lens['fraud_amount_caught'])} of {dollars(lens['fraud_amount_total'])}",
        "claimlens_auto_resolved": f"{lens['auto_resolved']} of {plural(n, 'claim')}",
        "claimlens_auto_resolved_fraud": f"{lens['auto_resolved_fraud']} of {lens['auto_resolved']}",
        "claimlens_human_review": f"{lens['human_review']} of {plural(n, 'claim')}",
        "claimlens_tier_counts": f"HIGH {tiers['HIGH']}, MEDIUM {tiers['MEDIUM']}, LOW {tiers['LOW']}",
        "claimlens_cap_applied": f"{lens['cap_applied']} of {plural(n, 'claim')} ({lens['cap_applied_on_wrong_decisions']} of "
                                 f"them with a wrong decision)",
        "claimlens_orderings_disagreed": f"{lens['orderings_disagreed']} of {plural(n, 'claim')}",
        "adjuster_hours_saved": f"{lens['adjuster_hours_saved']} hours ({plural(lens['auto_resolved'], 'auto-resolved claim')} "
                                f"at an assumed {lens['manual_review_minutes_assumed']} minutes of manual review each)",
    }


def check_values(values):
    """The reporting rules, applied to the text that will actually be written."""
    problems = []
    if set(values) != set(KEY_DESCRIPTIONS):
        problems.append(f"internal: rendered keys and KEY_DESCRIPTIONS differ: {sorted(set(values) ^ set(KEY_DESCRIPTIONS))}")
    for key, value in values.items():
        if PERCENTAGE.search(value):
            problems.append(f"{key} contains a percentage ({value!r}); results must be raw counts")
    for key in ACCURACY_KEYS:
        if "always approv" not in values.get(key, "").lower():
            problems.append(f"{key} has no always-approve reference; every accuracy figure must carry one")
    if problems:
        raise StopError("the rendered values break the reporting rules:\n  - " + "\n  - ".join(problems))


# ---------------------------------------------------------------- filling the documents

def read_text(path):
    with open(path, encoding="utf-8", newline="") as f:   # keep the file's own line endings
        return f.read()


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def fill_document(name, text, values, urls):
    """Return (filled text, result keys used, problems, warnings). Problems block all writing."""
    problems, warnings, used = [], [], []

    def replace(match):
        keyed = KEYED.fullmatch(match.group(1))
        if not keyed or keyed.group(1) not in values:
            line = text.count("\n", 0, match.start()) + 1
            problems.append(f"{name}, line {line}: {match.group(0)!r} is not a known result marker (see --list-keys)")
            return match.group(0)
        used.append(keyed.group(1))
        return values[keyed.group(1)]

    filled = PLACEHOLDER.sub(replace, text)
    if not problems and "[[PLACEHOLDER" in filled:
        line = filled.count("\n", 0, filled.index("[[PLACEHOLDER")) + 1
        problems.append(f"{name}, around line {line}: a [[PLACEHOLDER marker is not closed on the same line")
    if used and REQUIRED_KEY not in used:
        problems.append(f"{name} reports results but has no [[PLACEHOLDER:{REQUIRED_KEY}]]: the sample size, "
                        "pre-registration and any truncation must be stated wherever results appear")

    filled = LIVE_URL.sub(lambda match: urls.get(match.group(1)) or match.group(0), filled)
    for kind in sorted(set(LIVE_URL.findall(filled))):
        warnings.append(f"{name}: [[LIVE_URL:{kind}]] left in place (pass --{kind}-url to fill it)")
    return filled, used, problems, warnings


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Fill the Stage 11 result markers in the documents from /analytics.")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--from-url", help="read a running API's /analytics, e.g. http://localhost:8000/analytics")
    source.add_argument("--from-file", help="read a saved /analytics JSON response")
    parser.add_argument("--check", action="store_true", help="validate and print the values; write nothing")
    parser.add_argument("--truncated-at-deadline", action="store_true",
                        help="report an unfinished run under the pre-registered stopping rule (first claims in order)")
    parser.add_argument("--frontend-url", help="deployed site URL for [[LIVE_URL:frontend]]")
    parser.add_argument("--backend-url", help="deployed API URL for [[LIVE_URL:backend]]")
    parser.add_argument("--root", help="folder holding the documents (default: repository root); for dry runs on copies")
    parser.add_argument("--list-keys", action="store_true", help="list every result marker key and exit")
    args = parser.parse_args(argv)

    if args.list_keys:
        for key, description in KEY_DESCRIPTIONS.items():
            print(f"[[PLACEHOLDER:{key}]]\n    {description}")
        return 0

    root = Path(args.root).resolve() if args.root else REPO_ROOT
    urls = {"frontend": args.frontend_url, "backend": args.backend_url}
    try:
        for kind, url in urls.items():
            if url and not re.match(r"https?://\S+$", url):
                raise StopError(f"--{kind}-url must be a full http(s) URL, got {url!r}")
        sample = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
        data, source_label = load_analytics(args)
        check_analytics(data, sample, args.truncated_at_deadline)
        values = render_values(data, sample)
        check_values(values)

        outputs, problems, warnings = {}, [], []
        for name in DOCUMENTS:
            path = root / name
            if not path.exists():
                warnings.append(f"{name}: not found in {root}, skipped")
                continue
            original = read_text(path)
            filled, used, doc_problems, doc_warnings = fill_document(name, original, values, urls)
            problems += doc_problems
            warnings += doc_warnings
            if filled == original:
                warnings.append(f"{name}: no markers to fill (already filled?)")
            else:
                outputs[path] = (filled, len(used))
        if problems:
            raise StopError("the documents failed checks:\n  - " + "\n  - ".join(problems))
    except StopError as error:
        print(f"STOPPED - nothing was written.\nReason: {error}")
        return 1

    progress = data["progress"]
    print(f"Analytics source: {source_label}")
    print(f"Claims: {progress['complete']} complete, {progress['failed']} failed, {progress['reported']} of "
          f"{progress['total']} reported; final: {progress['is_final']}; batch running: {progress['batch_running']}")
    if args.truncated_at_deadline and progress["batch_running"]:
        print("WARNING: the batch is still running. Stop it first, so the reported claims don't change after filling.")
    print("\nValues:")
    for key, value in values.items():
        print(f"  {key}: {value}")
    print()
    for warning in warnings:
        print(f"WARNING: {warning}")
    if args.check:
        print("\n--check: validation passed; nothing was written.")
        return 0
    if not outputs:
        print("\nNothing to write.")
        return 0

    for path, (filled, marker_count) in outputs.items():
        write_text(path, filled)
        print(f"filled {marker_count} result marker(s) in {path.name}")
    snapshot = {"filled_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "source": source_label,
                "documents": [path.name for path in outputs], "analytics": data}
    write_text(root / SNAPSHOT_PATH, json.dumps(snapshot, indent=2) + "\n")
    print(f"analytics used saved to {SNAPSHOT_PATH.as_posix()}")
    print("Review the diff (git diff) before committing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
