# Now and next

The hand-off between the AIs working here (Codex and Claude sessions). Read it first. It stays short on purpose: under 6,000 bytes, which `tests/test_docs_structure.py` checks. Finished work goes in `CHANGELOG.md`, not here. Rules: [AGENTS.md](AGENTS.md), section 3.

Last rewritten 2026-10-04 · Claude.

## Claude

- **Last done (2026-10-04):** reviewed the multiple-devices proposal at the owner's request. The review is appended at the end of [`docs/proposals/multiple_devices.md`](docs/proposals/multiple_devices.md) and, revised after the owner's feedback, recommends the proposal's checkout cut down for version 1: the phone lends the database to a PC in seconds and captures bank SMS while it is lent. Before that: made the docs cheaper to read (`NOW.md`, reading rules, `tools/guideline.py`).
- **In progress · claimed files:** none.

## Codex

- **Last done (2026-10-04):** wrote the multiple-devices proposal, now [`docs/proposals/multiple_devices.md`](docs/proposals/multiple_devices.md) (Claude moved it there with its content unchanged; no sync code yet). Set the source version to 0.5.0b1.
- **In progress · claimed files:** none.

## Next (unclaimed; claim it in your lane before you start)

1. **Release 0.5.0-beta.1:** check the Windows package, publish permanent versioned downloads, and add 0.5 to the website archive while keeping 0.4.
2. **UX plan items 5, 6, 8 and 9** (Project Overview › UX plan). Claim `lightning/ui/templates/` and `lightning/ui/static/style.css` first.
3. **Multiple devices (Codex):** read Claude's review at the end of the proposal. Record the owner's five requirements (the phone is a mobile home; connect once, then the PC works alone; the phone writes and captures bank SMS; a hand-off of seconds; the easiest path with the lowest downside), then revise the proposal or answer under *For the owner*.
4. **Speed, if wanted:** a stable window origin, so the 290 KB stylesheet and 109 KB script stay cached across launches; trim unused CSS in `style.css`.

## For the owner

- **Before the first tagged release (one-time):**
  1. Create a fine-grained token with Contents: read and write on `Lightning-downloads` only. Save it in this repository as the Actions secret `LIGHTNING_DOWNLOADS_TOKEN`.
  2. Turn on release immutability in `Lightning-downloads` › Settings.
  3. Release with `git tag v0.5.0-beta.1 <commit on main>` and `git push origin v0.5.0-beta.1`.
- **Retest:** on the PC whose window failed to start, try a ZIP downloaded in a browser. Builds from `f4e1603` on include the fix.
- **Questions:**
  1. *Multiple devices:* six questions at the end of the proposal (Review 5): how the phone accepts a return, hand back on close, captures during a lend, Play or APK for SMS, which banks first, extra backups.
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
  3. *UX:* recurring suggestions, and whether to add Accounts and Transactions to the main menu (Project Overview › UX plan, "Still open").
