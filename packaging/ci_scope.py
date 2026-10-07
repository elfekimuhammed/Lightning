"""CI helpers for the Windows app workflow (.github/workflows/desktop-probe.yml). Standard library only.

    python packaging/ci_scope.py                      # sets build_windows, suite, phone, reuse_run, reuse_artifact
    python packaging/ci_scope.py --check-release-tag  # a tag must match the source version and sit on main

Whether to build (owner, 2026-10-06: Actions minutes are limited and Windows minutes count double): a push
to main runs only the Linux suite. Tags always build. The daily scheduled run builds unless every file
changed since the last commit whose Windows build SUCCEEDED is one that cannot reach the app (documentation,
feedback notes, Linux launchers), or nothing changed at all. Comparing with that commit means code whose
build was cancelled or failed is never skipped; anything uncertain builds.

A manual run on main makes the matched PC and phone test builds (docs/ARCHITECTURE.md › Build and release) and
does nothing twice: if an earlier run of this workflow built and tested the Windows app of this exact commit
and its artifact has not expired, that ZIP is reused (reuse_run, reuse_artifact) and Windows is not built;
if an earlier run passed the Linux suite on this commit, the suite is skipped. A manual run elsewhere builds
Windows only, as before.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Files that never reach the Windows app or its build. Anything else (code, tests, packaging, locks,
# the workflow itself, Markdown inside lightning/ or packaging/) triggers a build.
_NEVER_SHIPPED = (
    re.compile(r"^docs/"),
    re.compile(r"^user feedback/"),
    re.compile(r"^Claude outputs/"),
    re.compile(r"^tools/"),  # helpers for the people and AIs working here; nothing imports them
    re.compile(r"^(?!lightning/|packaging/)[^\n]*\.md$"),
    re.compile(r"^Lightning\.desktop$"),
    re.compile(r"^run\.sh$"),
    # The phone app's own build: the Windows app never contains it.
    re.compile(r"^android/"),
    re.compile(r"^requirements/android\."),
    re.compile(r"^\.github/workflows/android-"),
    re.compile(r"^packaging/(phone_build\.py|android-)"),
)


def cannot_reach_app(path: str) -> bool:
    return any(pattern.search(path) for pattern in _NEVER_SHIPPED)


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


# The Windows job's name now, and before 2026-10-03.
WINDOWS_JOBS = {"Build and test the Windows app", "windows-probe"}
PHONE_JOBS = {"Phone app / Build and check the phone app"}  # the phone build as this workflow calls it
# Files that reach the phone app or its build; the daily run builds the phone when one of them changed.
_REACHES_PHONE = (
    re.compile(r"^lightning/"),
    re.compile(r"^android/"),
    re.compile(r"^requirements/android\."),
    re.compile(r"^packaging/(phone_build\.py|android-)"),
    re.compile(r"^\.github/workflows/(android-app|desktop-probe)\.yml$"),
    re.compile(r"^tests/fixtures/roundtrip/"),
)


def reaches_phone(path: str) -> bool:
    return any(pattern.search(path) for pattern in _REACHES_PHONE)
SUITE_JOB = "Full test suite (Linux)"
SUITE_STEP = "Full test suite"  # the step that ran it: the job also succeeds when the suite was skipped
# Documents only: a push that changes nothing else since the last full suite runs the tests that read them.
_DOCS_ONLY = (
    re.compile(r"^docs/"),
    re.compile(r"^user feedback/"),
    re.compile(r"^Claude outputs/"),
    re.compile(r"^[^/]+\.md$"),  # NOW, OWNER, CHANGELOG, AGENTS, README and the like
)
ALWAYS_DOCS_TESTS = ("tests/test_docs_structure.py", "tests/test_changelog.py")


def docs_only(path: str) -> bool:
    return any(pattern.search(path) for pattern in _DOCS_ONLY)


def suite_passed(job: dict) -> bool:
    """Whether this job ran the full Linux suite and it passed (not merely skipped it)."""
    return job.get("name") == SUITE_JOB and any(
        step.get("name") == SUITE_STEP and step.get("conclusion") == "success" for step in job.get("steps", []))


def docs_tests(changed: list[str], tests_dir: Path | None = None) -> list[str]:
    """The tests for a documents-only change: the documentation tests, and every test file that names a
    changed document (a test that reads a document names it)."""
    tests_dir = tests_dir or ROOT / "tests"
    names = {Path(path).name for path in changed}
    chosen = set(ALWAYS_DOCS_TESTS)
    for test in sorted(tests_dir.glob("test_*.py")):
        text = test.read_text(encoding="utf-8")
        if any(name in text for name in names):
            chosen.add(f"tests/{test.name}")
    return sorted(chosen)
WINDOWS_ARTIFACT = re.compile(r"Lightning-v\S+-dev-\S+-Windows-x64")  # a development build's ZIP artifact


def github_api(path: str) -> dict:
    request = urllib.request.Request(
        f"{os.environ.get('GITHUB_API_URL', 'https://api.github.com')}{path}",
        headers={"Authorization": f"Bearer {os.environ['GH_TOKEN']}", "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def _workflow() -> tuple[str, str]:
    """This repository and this workflow's file name, or empty strings outside GitHub Actions."""
    if not os.environ.get("GH_TOKEN"):
        return "", ""
    return (os.environ.get("GITHUB_REPOSITORY", ""),
            os.environ.get("GITHUB_WORKFLOW_REF", "").split("@")[0].rsplit("/", 1)[-1])


def last_windows_build(api=github_api, jobs_wanted: set[str] = WINDOWS_JOBS) -> str | None:
    """The commit of the newest run on main whose Windows job (or, with PHONE_JOBS, phone job) succeeded,
    or None if unknown. Only daily and manual runs build either on main, so only they are read: a day of
    pushes would fill a page of all runs."""
    repo, workflow = _workflow()
    if not repo or not workflow:
        return None
    try:
        runs = []
        for event in ("schedule", "workflow_dispatch"):
            runs += api(f"/repos/{repo}/actions/workflows/{workflow}/runs?branch=main&event={event}"
                        "&status=completed&per_page=20").get("workflow_runs", [])
        runs.sort(key=lambda run: run.get("created_at", ""), reverse=True)
        for run in runs:
            jobs = api(f"/repos/{repo}/actions/runs/{run['id']}/jobs?per_page=100")
            if any(job.get("name") in jobs_wanted and job.get("conclusion") == "success"
                   for job in jobs.get("jobs", [])):
                return run["head_sha"]
    except Exception as exc:  # no answer means no baseline, and no baseline means build
        print(f"Could not read earlier runs ({type(exc).__name__}); building to be safe.")
    return None


def last_full_suite(api=github_api) -> str | None:
    """The commit of the newest run on main that ran the full Linux suite and passed it, or None."""
    repo, workflow = _workflow()
    if not repo or not workflow:
        return None
    try:
        runs = api(f"/repos/{repo}/actions/workflows/{workflow}/runs?branch=main&status=completed&per_page=30")
        for run in runs.get("workflow_runs", []):
            jobs = api(f"/repos/{repo}/actions/runs/{run['id']}/jobs?per_page=100").get("jobs", [])
            if any(suite_passed(job) for job in jobs):
                return run["head_sha"]
    except Exception as exc:  # no answer means the full suite
        print(f"Could not read earlier runs ({type(exc).__name__}); running the full suite.")
    return None


def push_suite(baseline: str | None, sha: str) -> tuple[str, list[str], str]:
    """For a push to main: "docs" and the tests to run when only documents changed since the last commit
    whose full suite passed (so a cancelled run's code is never let through), else "run"."""
    changed, why = changed_since(baseline, sha, "full-suite")
    if changed is None:
        return "run", [], why
    if changed and all(docs_only(path) for path in changed):
        return "docs", docs_tests(changed), f"only documents changed since {baseline[:8]}, the last full suite"
    return "run", [], "code changed since the last full suite" if changed else "nothing changed; run anyway"


def earlier_runs(sha: str, api=github_api) -> dict[str, str]:
    """What earlier runs of this workflow already did for this exact commit: the newest run whose Windows
    build succeeded and whose ZIP artifact has not expired (reuse_run, reuse_artifact), and whether the
    Linux suite passed on it (suite=skip). An unknown answer means build and test."""
    nothing = {"reuse_run": "", "reuse_artifact": "", "suite": "run"}
    repo, workflow = _workflow()
    if not repo or not workflow or not re.fullmatch(r"[0-9a-f]{40}", sha):
        return nothing
    found = dict(nothing)
    current = os.environ.get("GITHUB_RUN_ID", "")
    try:
        runs = api(f"/repos/{repo}/actions/workflows/{workflow}/runs?head_sha={sha}&status=completed&per_page=30")
        for run in runs.get("workflow_runs", []):
            if run.get("head_sha") != sha or str(run.get("id")) == current:
                continue
            jobs = api(f"/repos/{repo}/actions/runs/{run['id']}/jobs?per_page=100").get("jobs", [])
            passed = {job.get("name") for job in jobs if job.get("conclusion") == "success"}
            if any(suite_passed(job) for job in jobs):
                found["suite"] = "skip"
            if not found["reuse_run"] and passed & WINDOWS_JOBS:
                artifacts = api(f"/repos/{repo}/actions/runs/{run['id']}/artifacts?per_page=100").get("artifacts", [])
                usable = [a["name"] for a in artifacts
                          if WINDOWS_ARTIFACT.fullmatch(a.get("name", "")) and not a.get("expired", True)]
                if usable:
                    found.update(reuse_run=str(run["id"]), reuse_artifact=usable[0], suite="skip")
    except Exception as exc:  # no answer means build and test
        print(f"Could not read earlier runs of this commit ({type(exc).__name__}); building and testing.")
        return nothing
    return found


def changed_since(baseline: str | None, sha: str, what: str) -> tuple[list[str] | None, str]:
    """The files changed from the last successful build to this commit, or None and why that is unknown."""
    if not baseline:
        return None, f"no earlier successful {what} build to compare with"
    if _git("cat-file", "-e", f"{baseline}^{{commit}}").returncode != 0:
        return None, f"last built commit {baseline[:8]} is not in this history"
    if _git("merge-base", "--is-ancestor", baseline, sha).returncode != 0:
        return None, f"last built commit {baseline[:8]} is not an ancestor of this push"
    # --no-renames: a file moved out of the app (say into docs/) lists its old path too, so it builds.
    diff = _git("diff", "--no-renames", "--name-only", baseline, sha)
    if diff.returncode != 0:
        return None, "could not list changed files"
    return [line for line in diff.stdout.splitlines() if line.strip()], ""


def build_phone_daily(event: str, ref: str, baseline: str | None, sha: str) -> tuple[bool, str]:
    """Whether the daily run builds and checks the phone app (no key needed, nothing offered): only when a
    file that reaches the phone changed since its last successful build. Anything uncertain builds."""
    if event != "schedule" or ref != "refs/heads/main":
        return False, "only the daily run builds the phone on its own"
    changed, why = changed_since(baseline, sha, "phone")
    if changed is None:
        return True, why
    reaching = [path for path in changed if reaches_phone(path)]
    if reaching:
        return True, f"{len(reaching)} changed file(s) reach the phone, e.g. {reaching[0]}"
    return False, f"nothing that reaches the phone changed since {baseline[:8]}"


def build_windows(event: str, ref: str, baseline: str | None, sha: str) -> tuple[bool, str]:
    if ref.startswith("refs/tags/"):
        return True, "release tag"
    if event == "push":
        return False, "a push runs the Linux suite only; Windows builds daily, on a tag or when run by hand"
    if event != "schedule":
        return True, f"{event or 'manual'} run"
    changed, why = changed_since(baseline, sha, "Windows")
    if changed is None:
        return True, why
    if not changed:
        return False, f"nothing changed since the last build ({baseline[:8]})"
    reaching = [path for path in changed if not cannot_reach_app(path)]
    if reaching:
        return True, f"{len(reaching)} changed file(s) can reach the app, e.g. {reaching[0]}"
    return False, f"only documentation changed since {baseline[:8]}, the last commit built ({len(changed)} file(s))"


def source_version() -> str:
    text = (ROOT / "lightning" / "__init__.py").read_text(encoding="utf-8")
    found = re.search(r'^DISPLAY_VERSION = "([^"]+)"$', text, re.M)
    if not found:
        raise SystemExit("::error::lightning/__init__.py has no DISPLAY_VERSION")
    return found.group(1)


def check_release_tag(tag: str, sha: str) -> list[str]:
    """Problems that stop a release; empty when the tag may be released."""
    problems = []
    version = source_version()
    if tag != f"v{version}":
        problems.append(f"Tag {tag} does not match the source version v{version} (lightning/__init__.py). "
                        "Bump the version in lightning/__init__.py and pyproject.toml, push, then tag that commit.")
    if _git("fetch", "--no-tags", "origin", "main").returncode != 0:
        problems.append("Could not fetch origin/main to check where the tag points.")
    elif _git("merge-base", "--is-ancestor", sha, "origin/main").returncode != 0:
        problems.append(f"Tag {tag} points at {sha[:8]}, which is not on main. Release only commits on main.")
    return problems


def manual_run_notes(ref: str, sha: str, values: dict[str, str], reason: str, has_key: bool,
                     has_fingerprint: bool) -> list[tuple[str, str]]:
    """What a manual run will make, as (level, text) lines for the run's page, said in its first minute."""
    if values["phone"] != "true":
        return [("warning", f"A manual run on {ref.removeprefix('refs/heads/')} builds the Windows app only; "
                            "the matched PC and phone test builds run only on main.")]
    windows = reason if values["reuse_run"] else "built and tested in this run"
    notes = [("notice", f"Matched test builds of {sha[:8]}. Windows: {windows}. Linux suite: "
                        + ("already passed on this commit, not run again." if values["suite"] == "skip" else "runs now."))]
    if not has_key:
        notes.append(("warning", "No test key yet (OWNER.md, Phone test key): both apps are built and checked, "
                                 "the Windows ZIP is uploaded, but the phone build stops at signing and no matched "
                                 "pair is offered."))
    elif not has_fingerprint:
        notes.append(("warning", "The test key is set but its fingerprint is not committed as "
                                 "packaging/android-test-certificate.sha256: the phone build will stop after signing."))
    return notes


def tell(notes: list[tuple[str, str]]) -> None:
    """Annotations on the run's page, and the same lines in its summary."""
    for level, text in notes:
        print(f"::{level}::{text}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary and notes:
        with open(summary, "a", encoding="utf-8") as stream:
            stream.write("".join(f"- {text}\n" for _, text in notes))


def main(argv: list[str]) -> int:
    sha = os.environ.get("GITHUB_SHA", "HEAD")
    if "--check-release-tag" in argv:
        tag = os.environ.get("GITHUB_REF_NAME", "")
        problems = check_release_tag(tag, sha)
        for problem in problems:
            print(f"::error::{problem}")
        if not problems:
            print(f"Release tag {tag} matches the source version and is on main.")
        return 1 if problems else 0
    event, ref = os.environ.get("GITHUB_EVENT_NAME", ""), os.environ.get("GITHUB_REF", "")
    # Only the daily run compares with the last Windows build (a push never builds Windows).
    baseline = last_windows_build() if event == "schedule" and ref == "refs/heads/main" else None
    build, reason = build_windows(event, ref, baseline, sha)
    values = {"reuse_run": "", "reuse_artifact": "", "suite": "run", "phone": "false", "phone_daily": "false",
              "docs_tests": ""}
    if event == "push" and ref == "refs/heads/main":
        suite, tests, why = push_suite(last_full_suite(), sha)
        values.update(suite=suite, docs_tests=" ".join(tests))
        print(f"Linux suite: {suite} ({why})" + (f": {' '.join(tests)}" if tests else ""))
    if event == "schedule" and ref == "refs/heads/main":
        daily, why = build_phone_daily(event, ref, last_windows_build(jobs_wanted=PHONE_JOBS), sha)
        values["phone_daily"] = "true" if daily else "false"
        print(f"Build the phone app: {'yes' if daily else 'no'} ({why})")
    if event == "workflow_dispatch" and ref == "refs/heads/main":
        values.update(earlier_runs(sha), phone="true")
        if values["reuse_run"]:
            build, reason = False, f"run {values['reuse_run']} built and tested this commit; its ZIP is reused"
    print(f"Build the Windows app: {'yes' if build else 'no'} ({reason})")
    print(f"Linux suite: {values['suite']}; phone app and test bundle: {'yes' if values['phone'] == 'true' else 'no'}")
    if event == "workflow_dispatch":
        tell(manual_run_notes(ref, sha, values, reason, os.environ.get("HAS_TEST_KEY") == "true",
                              (ROOT / "packaging" / "android-test-certificate.sha256").exists()))
    values["build_windows"] = "true" if build else "false"
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as stream:
            stream.write("".join(f"{key}={value}\n" for key, value in values.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
