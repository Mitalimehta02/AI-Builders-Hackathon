"""
Pre-submission verification: one command that checks everything that must be true before submitting.

Run from the repository root with the backend venv interpreter:

    backend\\.venv\\Scripts\\python.exe scripts\\preflight.py --frontend-url https://<site> --backend-url https://<api>

Every check runs even if an earlier one fails, and each prints PASS, FAIL or SKIP with the reason.
A skipped check is NOT a pass: the script says READY only when every check passed.

    exit 0   every check passed
    exit 1   at least one check failed
    exit 2   nothing failed, but at least one check was skipped (so readiness is unproven)

Checks
    documents  no unfilled [[PLACEHOLDER...]], [[LIVE_URL...]] or other [[BRACKETED]] markers in README.md and the
               submission documents; a missing document fails
    git        working tree clean (no modified or untracked files) and HEAD identical to its origin branch
    secrets    no key-shaped strings in any commit or untracked file; .env and .venv never committed
    snapshot   backend/data/stage11_final_analytics.json is for the pre-registered sample (claim-ID hash)
    tests      the backend test suite passes (all 92), with the Groq key blanked so no model call can happen
    build      the frontend production build succeeds
    frontend   the live site responds, and its /api proxy reaches the backend       (needs --frontend-url)
    backend    the live API responds                                                (needs --backend-url)
    endpoints  the live API's /health, /samples and /analytics return 200, and /analytics is for the
               pre-registered sample                                                (needs --backend-url)

No model calls are made. The live checks allow up to two minutes per request, because a free Render instance
that has been asleep takes about a minute to wake.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND = REPO_ROOT / "backend"
FRONTEND = REPO_ROOT / "frontend"
DOCUMENTS = ("README.md", "docs/DECK_CONTENT.md", "docs/VIDEO_SCRIPT.md", "docs/DEVPOST_SUBMISSION.md")
SAMPLE_PATH = BACKEND / "data" / "stage11_sample.json"
SNAPSHOT_PATH = BACKEND / "data" / "stage11_final_analytics.json"

# Published in README.md and registered in commit 892f964, before any held-out claim was run.
PREREGISTERED_IDS_SHA256 = "bbcdf0fd5693fd7a1be43ee4516dd7c99ef71fbb238e696c6c190dc108d5b49a"
EXPECTED_TESTS = 92
HTTP_TIMEOUT_SECONDS = 120

# An unfilled marker: [[ followed by a capital letter, closed or not (e.g. [[PLACEHOLDER:key]], [[LIVE_URL:frontend]], [[TBD]]).
MARKER = re.compile(r"\[\[[A-Z][^\]\n]*(?:\]\])?")

# Key-shaped strings only, so ordinary code such as os.environ.get("GROQ_API_KEY", "") does not trip it.
_SECRET_CORE = (r"gsk_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY"
                r"|xox[baprs]-[A-Za-z0-9-]{10,}|gh[pousr]_[A-Za-z0-9]{30,}|AIza[0-9A-Za-z_-]{35}")
_ASSIGNED = r"(api[_-]?key|secret|password|passwd|access[_-]?token|auth[_-]?token)[\"']?SPACE*[:=]SPACE*[\"'][A-Za-z0-9_/+=.-]{16,}[\"']"
SECRET_GIT = _SECRET_CORE + "|" + _ASSIGNED.replace("SPACE", "[[:space:]]")       # POSIX ERE for git grep
SECRET_PY = re.compile(_SECRET_CORE + "|" + _ASSIGNED.replace("SPACE", r"\s"), re.IGNORECASE)
COMMITTED_ENV = re.compile(r"(^|/)\.env$|(^|/)\.env\.(?!example$)[^/]*$|(^|/)\.venv/")

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"


def run(command, cwd=REPO_ROOT, timeout=900, env=None):
    """Run a command; return (exit code, combined output). A missing program or timeout becomes a failure."""
    try:
        result = subprocess.run([str(part) for part in command], cwd=cwd, env=env, capture_output=True,
                                text=True, encoding="utf-8", errors="replace", timeout=timeout)
        return result.returncode, (result.stdout or "") + (result.stderr or "")
    except FileNotFoundError as error:
        return 127, f"program not found: {error}"
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout} seconds"


def git(*args):
    return run(["git", *args], env=dict(os.environ, GIT_TERMINAL_PROMPT="0"))


def last_lines(text, count=6):
    return " | ".join(line.strip() for line in text.strip().splitlines()[-count:])


# ---------------------------------------------------------------- checks

def check_documents(args):
    problems = []
    for name in DOCUMENTS:
        path = REPO_ROOT / name
        if not path.exists():
            problems.append(f"{name} is missing")
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for match in MARKER.finditer(line):
                problems.append(f"{name}:{number} {match.group(0)}")
    if not problems:
        return PASS, f"no unfilled markers in {len(DOCUMENTS)} documents"
    shown = problems[:12] + ([f"... and {len(problems) - 12} more"] if len(problems) > 12 else [])
    return FAIL, f"{len(problems)} problem(s):\n" + "\n".join(f"      {p}" for p in shown)


def check_git(args):
    code, output = git("fetch", "-q", "origin")
    if code:
        return FAIL, f"could not fetch origin: {last_lines(output, 2)}"
    problems = []
    _, status = git("status", "--porcelain")
    changes = [line for line in status.splitlines() if line.strip()]
    if changes:
        listed = ", ".join(line[3:] for line in changes[:8]) + (" ..." if len(changes) > 8 else "")
        problems.append(f"{len(changes)} uncommitted or untracked file(s): {listed}")
    code_head, head = git("rev-parse", "HEAD")
    code_up, upstream = git("rev-parse", "@{u}")
    if code_up:
        problems.append("the current branch has no upstream on origin")
    elif head.strip() != upstream.strip():
        _, counts = git("rev-list", "--left-right", "--count", "HEAD...@{u}")
        ahead, behind = (counts.split() + ["?", "?"])[:2]
        problems.append(f"HEAD differs from origin ({ahead} commit(s) not pushed, {behind} not pulled)")
    if problems:
        return FAIL, "; ".join(problems)
    return PASS, f"clean, and HEAD {head.strip()[:7]} matches origin"


def check_secrets(args):
    problems = []
    _, revisions = git("rev-list", "--all")
    revisions = revisions.split()
    hits = set()
    for revision in revisions:
        code, output = git("grep", "-I", "-l", "-i", "-E", SECRET_GIT, revision)
        if code == 0:
            hits.update(f"{line.split(':', 1)[1]} (commit {revision[:7]})" for line in output.splitlines() if ":" in line)
        elif code not in (0, 1):
            problems.append(f"git grep failed on {revision[:7]}: {last_lines(output, 1)}")
    if hits:
        problems.append("key-shaped strings in history: " + ", ".join(sorted(hits)[:8]))
    _, untracked = git("ls-files", "--others", "--exclude-standard")
    for name in untracked.splitlines():
        path = REPO_ROOT / name
        try:
            if path.stat().st_size <= 50_000_000 and SECRET_PY.search(path.read_text(encoding="utf-8", errors="ignore")):
                problems.append(f"key-shaped string in untracked file {name}")
        except OSError:
            pass
    _, paths = git("log", "--all", "--pretty=format:", "--name-only")
    committed_env = sorted({p for p in paths.splitlines() if COMMITTED_ENV.search(p)})
    if committed_env:
        problems.append("secret-bearing paths were committed: " + ", ".join(committed_env[:8]))
    if problems:
        return FAIL, "; ".join(problems)
    return PASS, f"{len(revisions)} commits and all untracked files scanned; no .env or .venv ever committed"


def check_snapshot(args):
    sample = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
    recomputed = hashlib.sha256("\n".join(sorted(sample["claim_ids"])).encode("utf-8")).hexdigest()
    if sample["claim_ids_sha256"] != PREREGISTERED_IDS_SHA256 or recomputed != PREREGISTERED_IDS_SHA256:
        return FAIL, "backend/data/stage11_sample.json no longer matches the pre-registered claim-ID hash"
    if not SNAPSHOT_PATH.exists():
        return FAIL, (f"{SNAPSHOT_PATH.relative_to(REPO_ROOT).as_posix()} not found; it is written by "
                      "scripts/fill_results.py when the documents are filled")
    try:
        snapshot_hash = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))["analytics"]["evaluation"]["claim_ids_sha256"]
    except (ValueError, KeyError, TypeError) as error:
        return FAIL, f"snapshot is unreadable or has no sample hash ({error})"
    if snapshot_hash != PREREGISTERED_IDS_SHA256:
        return FAIL, f"snapshot sample hash {snapshot_hash[:12]}... does not match the pre-registered {PREREGISTERED_IDS_SHA256[:12]}..."
    return PASS, f"snapshot sample hash matches the pre-registered {PREREGISTERED_IDS_SHA256[:12]}..."


def check_tests(args):
    python = BACKEND / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.exists():
        return FAIL, "backend/.venv not found; follow the README backend setup first"
    env = {**os.environ, "GROQ_API_KEY": ""}   # blank key: no model call can happen
    code, output = run([python, "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider"], cwd=BACKEND, env=env)
    passed = re.search(r"(\d+) passed", output)
    passed = int(passed.group(1)) if passed else 0
    if code != 0:
        return FAIL, f"pytest exited {code}: {last_lines(output, 4)}"
    if passed != EXPECTED_TESTS:
        return FAIL, f"{passed} tests passed, expected {EXPECTED_TESTS} (update EXPECTED_TESTS only if tests changed on purpose)"
    return PASS, f"{passed} passed"


def check_build(args):
    npm = shutil.which("npm")
    if not npm:
        return FAIL, "npm not found on PATH"
    if not (FRONTEND / "node_modules").exists():
        return FAIL, "frontend/node_modules not found; run npm install in frontend/ first"
    code, output = run([npm, "run", "build"], cwd=FRONTEND)
    if code != 0:
        return FAIL, f"npm run build exited {code}: {last_lines(output, 6)}"
    return PASS, "npm run build succeeded"


def http_get(url):
    """(status or None, body bytes or error text). One retry covers a sleeping instance that was waking up."""
    request = urllib.request.Request(url, headers={"User-Agent": "claimlens-preflight"})
    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as error:
            return error.code, error.read()
        except Exception as error:  # connection refused, DNS failure, timeout
            if attempt == 2:
                return None, str(error)
            time.sleep(5)


def check_frontend(args):
    if not args.frontend_url:
        return SKIP, "no --frontend-url given, so the live site was not checked"
    status, _ = http_get(args.frontend_url)
    if status != 200:
        return FAIL, f"{args.frontend_url} -> {status or 'no response'}"
    proxy_status, body = http_get(args.frontend_url + "/api/health")
    if proxy_status != 200 or b'"ok"' not in (body if isinstance(body, bytes) else b""):
        return FAIL, (f"site is up, but {args.frontend_url}/api/health -> {proxy_status or 'no response'}: "
                      "the frontend cannot reach the backend (check BACKEND_URL on Vercel, then redeploy)")
    return PASS, f"{args.frontend_url} -> 200; /api/health through the proxy -> 200"


def check_backend(args):
    if not args.backend_url:
        return SKIP, "no --backend-url given, so the live API was not checked"
    status, body = http_get(args.backend_url + "/health")
    if status is None:
        return FAIL, f"{args.backend_url} did not respond: {body}"
    return PASS, f"{args.backend_url} responded (HTTP {status})"


def check_endpoints(args):
    if not args.backend_url:
        return SKIP, "no --backend-url given, so /health, /samples and /analytics were not checked"
    problems, results = [], []
    for path in ("/health", "/samples", "/analytics"):
        status, body = http_get(args.backend_url + path)
        results.append(f"{path} {status or 'no response'}")
        if status != 200:
            problems.append(f"{path} -> {status or 'no response'}")
        elif path == "/analytics":
            try:
                live_hash = json.loads(body)["evaluation"]["claim_ids_sha256"]
                if live_hash != PREREGISTERED_IDS_SHA256:
                    problems.append("/analytics is not for the pre-registered sample (claim-ID hash differs)")
            except (ValueError, KeyError, TypeError):
                problems.append("/analytics returned 200 but not the expected JSON")
    if problems:
        return FAIL, "; ".join(problems)
    return PASS, ", ".join(results) + "; /analytics sample hash matches"


CHECKS = (
    ("documents", check_documents),
    ("git", check_git),
    ("secrets", check_secrets),
    ("snapshot", check_snapshot),
    ("tests", check_tests),
    ("build", check_build),
    ("frontend", check_frontend),
    ("backend", check_backend),
    ("endpoints", check_endpoints),
)


def normalise_url(url, flag):
    if url is None:
        return None
    url = url.strip().rstrip("/")
    if not re.match(r"https?://[^\s/]+", url):
        sys.exit(f"{flag} must be a full http(s) URL, got {url!r}")
    return url


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Pre-submission verification for ClaimLens.")
    parser.add_argument("--frontend-url", help="the deployed site, e.g. https://claimlens.vercel.app")
    parser.add_argument("--backend-url", help="the deployed API, e.g. https://claimlens-api.onrender.com")
    args = parser.parse_args(argv)
    args.frontend_url = normalise_url(args.frontend_url, "--frontend-url")
    args.backend_url = normalise_url(args.backend_url, "--backend-url")

    print(f"ClaimLens preflight - {REPO_ROOT}\n")
    outcomes = []
    for name, check in CHECKS:
        started = time.monotonic()
        try:
            status, detail = check(args)
        except Exception as error:  # a crashed check is a failed check, never a silent pass
            status, detail = FAIL, f"check crashed: {error.__class__.__name__}: {error}"
        outcomes.append((name, status))
        print(f"[{status}] {name:<9} {detail}  ({time.monotonic() - started:.0f}s)", flush=True)

    failed = [name for name, status in outcomes if status == FAIL]
    skipped = [name for name, status in outcomes if status == SKIP]
    print()
    if failed:
        print(f"NOT READY: {len(failed)} check(s) failed: {', '.join(failed)}"
              + (f"; {len(skipped)} skipped: {', '.join(skipped)}" if skipped else ""))
        return 1
    if skipped:
        print(f"NOT READY: nothing failed, but {len(skipped)} check(s) were skipped and are unproven: {', '.join(skipped)}")
        return 2
    print(f"READY: all {len(outcomes)} checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
