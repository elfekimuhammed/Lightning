# Now and next

The hand-off between the AIs working here (Codex and Claude sessions). Read it first. It stays short on purpose: under 6,000 bytes, which `tests/test_docs_structure.py` checks. Finished work goes in `CHANGELOG.md`, not here. Rules: [AGENTS.md](AGENTS.md), section 3.

Last rewritten 2026-10-05 · Codex.

## Claude

- **Last done (2026-10-04):** wrote [`docs/COMPETITION.md`](docs/COMPETITION.md), the competitor compass, from Google Play reviews read directly (Say, Qershnat, Masarifi, Masareef, Money Manager, Wallet). Before that: reviewed the multiple-devices proposal; made the docs cheaper to read.
- **Multiple devices (2026-10-04):** Claude agrees with Codex's reply to the review, which supersedes it where they differ:
  - prefetch pauses writes or uses `snapshot()`;
  - a locked phone holds a return as *received, checking* and accepts it at the next unlock;
  - a lend ends only on the borrower's durable, authenticated cancel for that checkout ID;
  - speed figures are targets until measured on a phone;
  - "3 minutes" holds only while recovery copies arrive.

  `audit_log` covers only transactions, physical items and revaluations. So detect changes by comparing file hashes, and compare the two copies table by table for take-back. Codex writes the revised proposal; Claude stays out of that file.
- **Multiple-devices plan edited by Claude at the owner's request (2026-10-04):** task 05 split into 05a/05b, 18a builds after 06, a killed-app lend test, and a "what you will see" list in the Project Overview. Codex: please check it fits.
- **In progress · claimed files:** none.

## Codex

- **Last done (2026-10-05):** 01, 02a–02c and first 03a restore preview: inventory, promotion, platform adapters and encrypted restore. GitHub run 37239350883 passed Linux and Windows. 05a blocks stale grant replay; 21 tests pass. The Android wheel probe now tests two build-setting fixes, with no APK yet. Restore needs repair and Windows drills before real data. Checkout/return is in-memory only.
- **In progress · claimed files:** Task 02d journal integration (`lightning/database/promotion.py`, `tests/test_database_promotion.py` landed; reboot/fault evidence and runtime gating remain); task 03a safety hardening (Luna under Codex: `lightning/runtime/restore.py`, `lightning/database/promotion_windows.py`, `tests/test_profile_session.py`, `tests/test_database_promotion_windows.py`; Codex reviews and owns restore UI/docs). First: durable intent/source-copy manifest and Windows marker publication; next: explicit deterministic repair. Task 04a Android build feasibility (Codex: `android/` and Android workflows); remaining 05a schemas (Codex: `lightning/sync/`, `tests/test_sync_domain.py`). Android source-wheel blockers: `android/README.md`. Codex owns `NOW.md` and `CHANGELOG.md`.

## Next (unclaimed; claim it in your lane before you start)

1. **Release 0.5.0-beta.1:** check the Windows package, publish permanent versioned downloads, and add 0.5 to the website archive while keeping 0.4.
2. **UX plan items 5, 6, 8 and 9** (Project Overview › UX plan). Claim `lightning/ui/templates/` and `lightning/ui/static/style.css` first.
3. **Competition research:** App Store, Reddit and Facebook reviews were not reachable; see the last section of `docs/COMPETITION.md`. Owner questions are in *For the owner*.
4. **Speed, if wanted:** a stable window origin, so the 290 KB stylesheet and 109 KB script stay cached across launches; trim unused CSS in `style.css`.

5. **Multiple devices:** tasks 01 and 02a–02c are done; 02d and 04a are in progress. The first 03a encrypted restore preview is wired; next is an interrupted-operation repair path, fault/reboot drills and ordinary Windows restore acceptance before using real profile data. Follow the [dependencies and Read column](docs/proposals/multiple_devices.md#15-implementation-work-packages).

## For the owner

- **Before the first tagged release (one-time):**
  1. Create a fine-grained token with Contents: read and write on `Lightning-downloads` only. Save it in this repository as the Actions secret `LIGHTNING_DOWNLOADS_TOKEN`.
  2. Turn on release immutability in `Lightning-downloads` › Settings.
  3. Release with `git tag v0.5.0-beta.1 <commit on main>` and `git push origin v0.5.0-beta.1`.
- **Retest:** on the PC whose window failed to start, try a ZIP downloaded in a browser. Builds from `f4e1603` on include the fix.
- **Questions:**
  1. *Multiple devices — two choices:* offer optional fingerprint unlock on Android, or retain password-only? Keep two-PC lending as a test harness (recommended), or authorize a separately accepted PC-home interim product? Defaults remain password-only and phone-home. Windows in-app updates are already requested in the Overview; the first beta uses a manual-update path. Bank samples and platform evidence are engineering gates in the plan.
  2. *Review of Mohab's year:* which of these suggestions should be built? None has been started.
     1. Say *to* or *from* on transfer rows.
     2. Needs you lists expected income not yet received.
     3. The emergency fund suggests a top-up when it covers under one month.
     4. Early in the month, Change in net worth gets a note naming the expected income.
     5. The Investments sparkline marks sales.
     6. Reserves offers to complete a goal once its payment is linked.
     7. Check against bank offers "mark all checked up to this date" when the balances match.
     8. At phone width, the top menu and the accounts fit on screen.
     9. Loans still to pay and Check against bank show without opening a folded row.
  3. *Competition:* should Lightning get gam'eya (rotating savings) and zakat, as Qershnat has them? (Trial decided: 7 days free, never a lock; Project Overview › Product decisions.)
  4. *UX:* recurring suggestions, and whether to add Accounts and Transactions to the main menu (Project Overview › UX plan, "Still open").
