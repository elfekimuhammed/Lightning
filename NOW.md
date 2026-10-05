# Now and next

The hand-off between the AIs working here. Read it first; it stays under 4,500 bytes (`tests/test_docs_structure.py`). What was done is in `git log` and `CHANGELOG.md`; what only the owner can do or decide is in [OWNER.md](OWNER.md). Rules: [AGENTS.md](AGENTS.md), section 3.

## Claimed

Work longer than one sitting, and its files. Stay out of claimed files; remove your row when the work is pushed.

| Who | Work | Files | Since |
|---|---|---|---|
| Codex | Multiple devices 02d, journal integration: reboot and fault evidence, runtime gating | `lightning/database/promotion.py`, `tests/test_database_promotion.py` | 2026-10-05 |
| Luna, for Codex | 03a restore safety: durable intent and source-copy manifest, Windows marker publication, then explicit deterministic repair. Codex reviews it and owns the restore UI and docs | `lightning/runtime/restore.py`, `lightning/database/promotion_windows.py`, `tests/test_profile_session.py`, `tests/test_database_promotion_windows.py` | 2026-10-05 |
| Codex | 04a Android build feasibility; blockers in `android/README.md` | `android/`, the Android workflows | 2026-10-04 |
| Codex | 05a, the remaining sync schemas | `lightning/sync/`, `tests/test_sync_domain.py` | 2026-10-05 |
| Claude (market data) | Price collector, market file, file import into profiles; assets' exchange and Financial assets page | `lightning/market/`, `tools/market/`, `lightning/assets/`, `lightning/workflows/market_prices.py`, asset and price routes and templates under Investments, `.github/workflows/market-data.yml`, `docs/proposals/market_data.md` | 2026-10-05 |

## Messages

Each names who it is for; that AI deletes it once handled. A message to all may be deleted seven days after its date.

- **To Codex, from Claude, 2026-10-05 (03a review):** (1) a failure after PENDING, before P1, still locks the profile: retire it as abandoned when the journal never prepared and live equals `old_sha256`. (2) Deleting a retained copy locks the profile: intended? Re-verifying every copy at unlock is now an `OWNER.md` question.
- **To Codex, from Claude, 2026-10-05:** `session.prepare`/`confirm`/`recover`/`change_password` changed signature; `keys.json` is v2; `unwrap_key(read_slot(...), password)` still works.
- **To all, from Claude, 2026-10-05:** this file has a new shape (owner request): no lanes or "last done", claims in the table, owner items in `OWNER.md`. `AGENTS.md` section 3 has the rules.
- **To Codex, from Claude, 2026-10-05:** the owner wants financial assets editable in Settings. The page is `/investments/assets`; please link it from Settings (the `investments` section) when your Settings claim ends. Its doc lines wait for your docs claim too.

## Next

Unclaimed: add a *Claimed* row before you start. Each item's **Read:** names what it needs.

1. **Release 0.5.0-beta.1:** check the Windows package, publish permanent versioned downloads, and add 0.5 to the website archive while keeping 0.4. Read: Architecture, *Releasing a version* (grep it); website README › Version identity and archive.
2. **UX plan 5, 6, 8, 9:** Claim UI templates and `style.css`. Checkbox/radio accent is Azure but A10 says Nile (only import review uses Nile). Read: Project Overview › UX plan; guideline A10.
3. **Speed (optional):** stable window origin for CSS/JS caching; trim unused CSS. Read: Architecture › Page speed.
4. **Multiple devices:** tasks 01, 02a–02c and 06 are done (07 and 18a are now unblocked); 02d and 04a are in progress. The first 03a encrypted restore preview is wired; next is an interrupted-operation repair path, fault/reboot drills and ordinary Windows restore acceptance before using real profile data. Read: your task's row in [section 15](docs/proposals/multiple_devices.md#15-implementation-work-packages) and what its Read column names.
