# For the owner

What only the owner can do or decide. Any AI adds an item here, and removes it once it is done or decided; a decision is first recorded where it belongs (usually Project Overview › Product decisions). AIs read this file only when their task is one of its items.

## To do

- **Before the first tagged release (one-time):**
  1. Create a fine-grained token with Contents: read and write on `Lightning-downloads` only. Save it in this repository as the Actions secret `LIGHTNING_DOWNLOADS_TOKEN`.
  2. Turn on release immutability in `Lightning-downloads` › Settings.
  3. Release with `git tag v0.5.0-beta.1 <commit on main>` and `git push origin v0.5.0-beta.1`.
- **Price packs (one-time):** the public repository `elfekimuhammed/Lightning_Market_Data` exists (2026-10-05); still to do: a fine-grained token with Contents: read and write on it only, saved here as the Actions secret `LIGHTNING_MARKET_TOKEN`, and the repository variable `MARKET_PUBLISH` set to `true`. Until then the collector runs and checks sources but publishes nothing. Only exchange rates (CBE) are published (decided 2026-10-05). A tagged release needs that pack published there, because the release ZIP carries it: until then `v0.5.0-beta.1` stops at its price-files step.
- **Review milestones 1 and 2 together, dummy data only:**
  1. Phone: install `lightning-android` from [Android run 37519507147](https://github.com/elfekimuhammed/Lightning/actions/runs/37519507147) (a new app called Lightning). PC: install the ZIP from [Windows run 37519503375](https://github.com/elfekimuhammed/Lightning/actions/runs/37519503375). Same Wi-Fi.
  2. PC: create a dummy profile and add an account. Phone: Bring a profile from your PC, Show a code. PC: Profile settings › Move to your phone, type the address and code. Both show the same six digits.
  3. Phone: unlock the profile with its password (the same one as on the PC; there is no other password). Look at Overview, Accounts, an account (add a transaction with the + button) and the other sections: does it feel like a phone app?
  4. PC: open it under From your phone and add something; the phone says "Lent to … · read only". Hand back; the phone has it.
  5. Borrow again, turn the phone's Wi-Fi off, Hand back on the PC: the PC keeps your edits; hand back later.
  6. Accounts › From SMS: paste a few of your CIB or NBE messages (a blank line between them), say which account each ending is, then post them on the review.
  7. Optional: on the phone, Devices › Take the ledger back while the PC holds it; the PC then offers Borrow again and keeps its copy as a backup.
  Known gaps: you type the phone's address; on the phone, a holding's horizon is still changed on the PC; SMS is pasted for now (the phone reading them by itself comes next).
- **For milestone 2: review the phone brand guideline.** Part C of the brand guideline (3.25, 2026-10-06) is the phone's own: bottom tab bar, 2 × 2 KPIs, phone forms of every chart. Check it, especially the five bottom sections (C03.1), then say it is final. Until then phone screens follow it as a draft.
- **For milestone 3: more bank SMS.** CIB and NBE are in `tests/fixtures/bank_sms.json` (details changed). Send other banks, and from these two a refund, a declined payment and a purchase in English if you get them; paste them in chat and I change the details before they go in.
- **GitHub spending limit (your choice, 2026-10-06):** GitHub › Settings › Billing and licensing › Budgets and alerts: set Actions to $0 (or the most you accept). CI then pauses until next month instead of charging you.
- **Website search:** add `lightningeg.com` to Google Search Console and Bing Webmaster Tools; submit `/sitemap.xml`.
- **Retest:** on the PC whose window failed to start, try a ZIP downloaded in a browser. Builds from `f4e1603` on include the fix.


## To decide

1. *Multiple devices — two choices:* offer optional fingerprint unlock on Android, or retain password-only? Keep two-PC lending as a test harness (recommended), or authorize a separately accepted PC-home interim product? Defaults remain password-only and phone-home. Windows in-app updates are already requested in the Overview; the first beta uses a manual-update path. Bank samples and platform evidence are engineering gates in the plan.
2. *Review of Mohab's year:* which of these suggestions should be built? None has been started.
   1. Say *to* or *from* on transfer rows.
   2. Needs you lists expected income not yet received.
   3. Early in the month, Change in net worth gets a note naming the expected income.
   4. The Investments sparkline marks sales.
   5. Reserves offers to complete a goal once its payment is linked.
   6. Check against bank offers "mark all checked up to this date" when the balances match.
   7. At phone width, the top menu and the accounts fit on screen.
   8. Loans still to pay and Check against bank show without opening a folded row.
3. *Phone: words or icons, and where to add (audit 2026-10-06; Competition › Phone flow, words and icons).* The best apps name every tab and keep adding one tap away. Three changes to guideline Part C, recommended in this order:
   1. Section tabs show words, not icons, even with four tabs (C03.3): Cash planning's Plan, Recurring, Loans, Reserves and Settings' four tabs as a 2 × 2 of words, or words alone at 13px. Today only the chosen tab has its word.
   2. The add button on every section's first page, not only Accounts and an account (C05.2): capture beats analysis (The compass, 1).
   3. The phone Overview as in C11.1: Get set up, Needs you, the four KPIs and Your position; Cash flow, Investments, Month by month and the rest open from rows into their own tabs. Today it is about seven screens long.
4. *Competition:* should Lightning get gam'eya (rotating savings) and zakat, as Qershnat has them? (Trial decided: 7 days free, never a lock; Project Overview › Product decisions.)
4. *Routine audit (2026-10-05):* pain points to decide: Housing 22% vs 45%, "Kept 0", "Split · 0 categories", a certificate named twice, Reserves dropdowns (A16: type and pick).
5. *Upcoming projects* (Project Overview): 17 ideas, each naming its source app. Financial health (#3) and the entry helpers (#9: sums, Ctrl-K, privacy mode, #tags) are built. New from you: multi-currency and FX revaluation (#15), US stocks (#16), reading PDF and Excel files (#17). Which enter *Next*, and where do US stock prices come from?
6. *Restore, from Claude's review of 03a:* unlock re-verifies every retained copy (2.7 s for three 23.5 MB restores). Keep that, or drop it?
7. *Ratios (2026-10-05):* when should a ratio turn strong rose (needs you)? Suggested: loan payments over 35% of income, fixed costs over 50% of it. Until then the four ratio cards on Loans and Recurring stay soft rose (Project Overview › Upcoming projects #3).
8. *Not in the brand guideline (2026-10-05):* the sidebar's Search well and privacy eye (styled as the dropdown's soft search well, pressed in Nile), and privacy mode's 6px blur on amounts. Keep them, or give the rule?
9. *Restore release risk:* after the ordinary Windows dummy-data reboot drill passes, accept real-data restore with abrupt power-loss durability still unverified, or defer it until a controlled power-cut drill passes? The precise failure and fail-closed behavior are in Architecture › Promotion durability risk and release gate. No process-kill or normal-reboot result should be described as power-cut evidence.
10. *Import link window (2026-10-05, [proposal 1.4](docs/proposals/temp-better-features.md#14-finding-the-same-transaction-on-import)):* keep 3 days either side, or widen to 7 like Actual? 7 catches slow card postings; 3 avoids offering last week's equal payment (a café, a class) as this week's. Default: keep 3.
