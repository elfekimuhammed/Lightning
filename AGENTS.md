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
- [App brand guideline](docs/APPLICATION_BRAND_GUIDE.md): current words, layout,
  controls, charts and responsive rules. Use its visual HTML companion for UI
  work; the app's CSS is authoritative where they differ.
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
