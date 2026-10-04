# Now and next

The hand-off between the AIs working here (Codex and Claude sessions). Read it first. It stays short on purpose: under 6,000 bytes, which `tests/test_docs_structure.py` checks. Finished work goes in `CHANGELOG.md`, not here. Rules: [AGENTS.md](AGENTS.md), section 3.

Last rewritten 2026-10-04 · Claude.

## Claude

- **Last done (2026-10-04):** wrote [`docs/COMPETITION.md`](docs/COMPETITION.md), the competitor compass, from Google Play reviews read directly (Say, Qershnat, Masarifi, Masareef, Money Manager, Wallet). Before that: reviewed the multiple-devices proposal; made the docs cheaper to read.
- **Multiple devices (2026-10-04):** Claude agrees with Codex's reply to the review, which supersedes it where they differ:
  - prefetch pauses writes or uses `snapshot()`;
  - a locked phone holds a return as *received, checking* and accepts it at the next unlock;
  - a lend ends only on the borrower's durable, authenticated cancel for that checkout ID;
  - speed figures are targets until measured on a phone;
  - "3 minutes" holds only while recovery copies arrive.

  `audit_log` covers only transactions, physical items and revaluations. So detect changes by comparing file hashes, and compare the two copies table by table for take-back. Codex writes the revised proposal; Claude stays out of that file.
- **In progress · claimed files:** none.

## Codex

- **Last done (2026-10-04):** revised [`docs/proposals/multiple_devices.md`](docs/proposals/multiple_devices.md) for the owner's phone-home, PC-borrowing workflow; kept Claude's review with the requested supersession note. Recorded the owner's decisions in the Project Overview. No sync code yet.
- **In progress · claimed files:** none.

## Next (unclaimed; claim it in your lane before you start)

1. **Release 0.5.0-beta.1:** check the Windows package, publish permanent versioned downloads, and add 0.5 to the website archive while keeping 0.4.
2. **UX plan items 5, 6, 8 and 9** (Project Overview › UX plan). Claim `lightning/ui/templates/` and `lightning/ui/static/style.css` first.
3. **Competition research:** App Store, Reddit and Facebook reviews were not reachable; see the last section of `docs/COMPETITION.md`. Owner questions are in *For the owner*.
4. **Speed, if wanted:** a stable window origin, so the 290 KB stylesheet and 109 KB script stay cached across launches; trim unused CSS in `style.css`.

## For the owner

- **Before the first tagged release (one-time):**
  1. Create a fine-grained token with Contents: read and write on `Lightning-downloads` only. Save it in this repository as the Actions secret `LIGHTNING_DOWNLOADS_TOKEN`.
  2. Turn on release immutability in `Lightning-downloads` › Settings.
  3. Release with `git tag v0.5.0-beta.1 <commit on main>` and `git push origin v0.5.0-beta.1`.
- **Retest:** on the PC whose window failed to start, try a ZIP downloaded in a browser. Builds from `f4e1603` on include the fix.
- **Questions:**
  1. *Multiple devices:* none open now. Bank SMS samples will be logged bank by bank later (proposal › Review 5).
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
  3. *Competition:* should Lightning get gam'eya (rotating savings) and zakat, as Qershnat has them, and should its first-run be free with no card (Say's top complaint)?
  4. *UX:* recurring suggestions, and whether to add Accounts and Transactions to the main menu (Project Overview › UX plan, "Still open").
