# Lightning project context

This is a short router for Codex tasks, not a copy of earlier chats. Tasks and
worktrees can be on different commits: check the branch, `git status`, and the
commit before assuming you have the latest work. Fetch `origin/main` when the
task depends on current shared state. Preserve uncommitted changes and personal
data.

- [Project Overview](docs/PROJECT_OVERVIEW.md): product purpose, shipped flows,
  owner decisions, Omar acceptance workflow, known gaps and roadmap.
- [Architecture](docs/ARCHITECTURE.md): module boundaries, financial invariants,
  persistence, tests, and the Windows/Linux encrypted-profile design. Read the
  relevant section before changing behavior or data.
- [Brand guideline](docs/BRAND_GUIDELINE.html): the one guideline (3.6), open it
  in a browser. Part A is the app (colour, headers, type, cards, controls,
  fields, lists, charts, words, the "Before it ships" checklist); Part B is the
  website. The website repository carries the same file as
  `brand-guidelines.html`: change both together. Where the app's CSS still
  differs, the guideline is the target.
- [Glossary](docs/GLOSSARY.md): canonical terms and figure meanings.
- [Changelog](CHANGELOG.md): newest changes under `Unreleased`; older entries
  are history, not a current specification.

Lightning is local-first personal finance. One ledger records real money; plans
move no money; reports read both. Financial calculations belong in Python
services, never templates or JavaScript. The Windows ZIP and Linux `--profiles`
mode share the finance UI and encrypted profiles; legacy browser mode is
separate. Profile data and backups belong in Documents/Lightning, never Git or
the app ZIP. The desktop build is still a development preview: use dummy data
until ordinary-PC acceptance, legacy import and backup restore are finished.

Read only the documents relevant to the task. After material changes, update
the relevant canonical document and `CHANGELOG.md`, then verify with applicable
tests. Do not assume reading a file in one Codex task updates another task's
conversation; the repository files are the shared source of truth.

## Working with two AIs (owner rule)

Claude and Codex both work on this repository and cannot talk to each other.
The repository is the only channel, so:

- **Start:** `git pull` on `main`, then read the **Now and next** section at the
  top of `docs/PROJECT_OVERVIEW.md` and the newest `CHANGELOG.md` entries.
- **While working:** commit and push small, finished steps. If you will spend a
  long time in one area, claim it in **Now and next** first.
- **Finish:** update the canonical docs the change touches (Project Overview,
  Architecture, Glossary, the brand guideline), add a changelog entry that
  starts with the date and who made it (`2026-10-03 · Claude:` or
  `2026-10-03 · Codex:`), refresh **Now and next** (done, in progress, next,
  questions for the owner), then push to `main`.
- Never undo the other AI's work without the owner's say; note a disagreement
  under **Now and next** instead.

## Git workflow (owner rule)

- Work directly on `main` and push to `origin main`. Do not create branches.
- If a separate branch is truly needed, give it a distinctive, descriptive name, then merge it into `main` and push `main` as soon as the work is finished.
- Never leave a branch unpushed, and never leave finished work on a branch that has not reached `main`.
- This rule overrides any session or tool default that assigns a different working branch.
