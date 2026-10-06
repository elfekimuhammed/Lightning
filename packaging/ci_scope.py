"""CI helpers for the Windows app workflow (.github/workflows/desktop-probe.yml). Standard library only.

    python packaging/ci_scope.py                      # sets build_windows=true|false for this push
    python packaging/ci_scope.py --check-release-tag  # a tag must match the source version and sit on main

Whether to build (owner, 2026-10-06: Actions minutes are limited and Windows minutes count double): a push
to main runs only the Linux suite. Tags and manual runs always build. The daily scheduled run builds unless
every file changed since the last commit whose Windows build SUCCEEDED is one that cannot reach the app
(documentation, feedback notes, Linux launchers), or nothing changed at all. Comparing with that commit means
code whose build was cancelled or failed is never skipped; anything uncertain builds.
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
)


def cannot_reach_app(path: str) -> bool:
    return any(pattern.search(path) for pattern in _NEVER_SHIPPED)


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


# The Windows job's name now, and before 2026-10-03.
WINDOWS_JOBS = {"Build and test the Windows app", "windows-probe"}


def github_api(path: str) -> dict:
    request = urllib.request.Request(
        f"{os.environ.get('GITHUB_API_URL', 'https://api.github.com')}{path}",
        headers={"Authorization": f"Bearer {os.environ['GH_TOKEN']}", "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def last_windows_build(api=github_api) -> str | None:
    """The commit of the newest run on main whose Windows job succeeded, or None if unknown."""
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    workflow = os.environ.get("GITHUB_WORKFLOW_REF", "").split("@")[0].rsplit("/", 1)[-1]
    if not repo or not workflow or not os.environ.get("GH_TOKEN"):
        return None
    try:
        runs = api(f"/repos/{repo}/actions/workflows/{workflow}/runs?branch=main&status=completed&per_page=30")
        for run in runs.get("workflow_runs", []):
            jobs = api(f"/repos/{repo}/actions/runs/{run['id']}/jobs?per_page=100")
            if any(job.get("name") in WINDOWS_JOBS and job.get("conclusion") == "success"
                   for job in jobs.get("jobs", [])):
                return run["head_sha"]
    except Exception as exc:  # no answer means no baseline, and no baseline means build
        print(f"Could not read earlier runs ({type(exc).__name__}); building to be safe.")
    return None


def build_windows(event: str, ref: str, baseline: str | None, sha: str) -> tuple[bool, str]:
    if ref.startswith("refs/tags/"):
        return True, "release tag"
    if event == "push":
        return False, "a push runs the Linux suite only; Windows builds daily, on a tag or when run by hand"
    if event != "schedule":
        return True, f"{event or 'manual'} run"
    if not baseline:
        return True, "no earlier successful Windows build to compare with"
    if _git("cat-file", "-e", f"{baseline}^{{commit}}").returncode != 0:
        return True, f"last built commit {baseline[:8]} is not in this history"
    if _git("merge-base", "--is-ancestor", baseline, sha).returncode != 0:
        return True, f"last built commit {baseline[:8]} is not an ancestor of this push"
    # --no-renames: a file moved out of the app (say into docs/) lists its old path too, so it builds.
    diff = _git("diff", "--no-renames", "--name-only", baseline, sha)
    if diff.returncode != 0:
        return True, "could not list changed files"
    changed = [line for line in diff.stdout.splitlines() if line.strip()]
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
    baseline = last_windows_build() if event == "push" and ref == "refs/heads/main" else None
    build, reason = build_windows(event, ref, baseline, sha)
    print(f"Build the Windows app: {'yes' if build else 'no'} ({reason})")
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as stream:
            stream.write(f"build_windows={'true' if build else 'false'}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
