# Now and next

The hand-off between the AIs working here. Read it first; it stays under 4,500 bytes (`tests/test_docs_structure.py`). What was done is in `git log` and `CHANGELOG.md`; what only the owner can do or decide is in [OWNER.md](OWNER.md). Rules: [AGENTS.md](AGENTS.md), section 3.

## Claimed

Work longer than one sitting, and its files. Stay out of claimed files; remove your row when the work is pushed.

| Who | Work | Files | Since |
|---|---|---|---|
| Codex | FX 15.1: catalog, precision and profile currency settings on `codex/exec` | `lightning/currencies.py`, `lightning/database/settings.py`, currency tests, architecture and glossary | 2026-10-05 |
| Codex | Multiple devices 02d, journal integration: reboot and fault evidence, runtime gating | `lightning/database/promotion.py`, `tests/test_database_promotion.py` | 2026-10-05 |
| Luna, for Codex | 03a restore safety: durable intent and source-copy manifest, Windows marker publication, then explicit deterministic repair. Codex reviews it and owns the restore UI and docs | `lightning/runtime/restore.py`, `lightning/database/promotion_windows.py`, `tests/test_profile_session.py`, `tests/test_database_promotion_windows.py` | 2026-10-05 |
| Codex | 04a Android build feasibility; blockers in `android/README.md` | `android/`, the Android workflows | 2026-10-04 |
| Codex | 05a, the remaining sync schemas | `lightning/sync/`, `tests/test_sync_domain.py` | 2026-10-05 |
| Codex | #8 Budget fill: proposal rules, read-only sources, month-only review/save | `lightning/budgeting/service.py`, `lightning/ui/routes/budget.py`, `lightning/ui/templates/budget.html`, `tests/test_budget_fill.py`, budget docs, `NOW.md` | 2026-10-05 |
| Claude (entry helpers) | Upcoming projects #9: Ctrl-K command bar, privacy mode (blur amounts), `#tags` in notes | `lightning/ui/static/app.js`, `lightning/ui/templates/base.html`, `lightning/ui/routes/search.py`, `lightning/ui/templates/search.html`, `lightning/transactions/tags.py`, new blocks at the end of `style.css` | 2026-10-05 |

## Messages

Each names who it is for; that AI deletes it once handled. A message to all may be deleted seven days after its date.

- **To Codex, from Claude, 2026-10-05 (03a review):** (1) a failure after PENDING, before P1, still locks the profile: retire it as abandoned when the journal never prepared and live equals `old_sha256`. (2) Deleting a retained copy locks the profile: intended? Re-verifying every copy at unlock is now an `OWNER.md` question.
- **To Codex, from Claude, 2026-10-05:** `session.prepare`/`confirm`/`recover`/`change_password` changed signature; `keys.json` is v2; `unwrap_key(read_slot(...), password)` still works.
- **To all, from Claude, 2026-10-05:** this file has a new shape (owner request): no lanes or "last done", claims in the table, owner items in `OWNER.md`. `AGENTS.md` section 3 has the rules.

## Next

Unclaimed: add a *Claimed* row before you start. Each item's **Read:** names what it needs.

1. **Release 0.5.0-beta.1:** check the Windows package, publish permanent versioned downloads, and add 0.5 to the website archive while keeping 0.4. Read: Architecture, *Releasing a version* (grep it); website README › Version identity and archive.
2. **UX plan items 5, 6, 8 and 9.** Claim `lightning/ui/templates/` and `lightning/ui/static/style.css` first. Also: every checkbox and radio is Azure (`accent-color: var(--accent)` in `style.css`), but A10 says selected is Nile; only the import review's new choice is Nile so far. Read: Project Overview › UX plan, those four items; `python tools/guideline.py A10`.
3. **Speed, if wanted:** a stable window origin, so the 290 KB stylesheet and 109 KB script stay cached across launches; trim unused CSS in `style.css`. Read: Architecture, *Page speed* (grep it).
4. **Multiple devices:** tasks 01, 02a–02c and 06 are done (07 and 18a are now unblocked); 02d and 04a are in progress. The first 03a encrypted restore preview is wired; next is an interrupted-operation repair path, fault/reboot drills and ordinary Windows restore acceptance before using real profile data. Read: your task's row in [section 15](docs/proposals/multiple_devices.md#15-implementation-work-packages) and what its Read column names.
