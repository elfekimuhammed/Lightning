# For the owner

What only the owner can do or decide. Any AI adds an item here, and removes it once it is done or decided; a decision is first recorded where it belongs (usually Project Overview › Product decisions). AIs read this file only when their task is one of its items.

## To do

- **Before the first tagged release (one-time):**
  1. Create a fine-grained token with Contents: read and write on `Lightning-downloads` only. Save it in this repository as the Actions secret `LIGHTNING_DOWNLOADS_TOKEN`.
  2. Turn on release immutability in `Lightning-downloads` › Settings.
  3. Release with `git tag v0.5.0-beta.1 <commit on main>` and `git push origin v0.5.0-beta.1`.
- **Price packs (one-time):** the public repository `elfekimuhammed/Lightning_Market_Data` exists (2026-10-05); still to do: a fine-grained token with Contents: read and write on it only, saved here as the Actions secret `LIGHTNING_MARKET_TOKEN`, and the repository variable `MARKET_PUBLISH` set to `true`. Until then the collector runs and checks sources but publishes nothing. Only exchange rates (CBE) are published (decided 2026-10-05). A tagged release needs that pack published there, because the release ZIP carries it: until then `v0.5.0-beta.1` stops at its price-files step.
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
3. *Competition:* should Lightning get gam'eya (rotating savings) and zakat, as Qershnat has them? (Trial decided: 7 days free, never a lock; Project Overview › Product decisions.)
4. *UX:* recurring suggestions, and whether to add Accounts and Transactions to the main menu (Project Overview › UX plan, "Still open").
5. *Routine audit (2026-10-05):* should a certificate's interest count in its Net gain and return (link the interest to the certificate)? Pain points to decide: the "System" group name, Housing 22% vs 45%, "80 of 68" rounding, "Kept 0", "Split · 0 categories", a certificate named twice, Reserves dropdowns (A16: type and pick).
6. *Upcoming projects* (Project Overview): 17 ideas, each naming its source app. Financial health (#3) and the entry helpers (#9: sums, Ctrl-K, privacy mode, #tags) are built. New from you: multi-currency and FX revaluation (#15), US stocks (#16), reading PDF and Excel files (#17). Which enter *Next*, and where do US stock prices come from?
7. *Restore, from Claude's review of 03a:* unlock re-verifies every retained copy (2.7 s for three 23.5 MB restores). Keep that, or drop it?
8. *Ratios (2026-10-05):* when should a ratio turn strong rose (needs you)? Suggested: loan payments over 35% of income, fixed costs over 50% of it. Until then the four ratio cards on Loans and Recurring stay soft rose (Project Overview › Upcoming projects #3).
9. *Not in the brand guideline (2026-10-05):* the sidebar's Search well and privacy eye (styled as the dropdown's soft search well, pressed in Nile), and privacy mode's 6px blur on amounts. Keep them, or give the rule?
10. *Restore release risk:* after the ordinary Windows dummy-data reboot drill passes, accept real-data restore with abrupt power-loss durability still unverified, or defer it until a controlled power-cut drill passes? The precise failure and fail-closed behavior are in Architecture › Promotion durability risk and release gate. No process-kill or normal-reboot result should be described as power-cut evidence.
12. *Import link window (2026-10-05, [proposal 1.4](docs/proposals/temp-better-features.md#14-finding-the-same-transaction-on-import)):* keep 3 days either side, or widen to 7 like Actual? 7 catches slow card postings; 3 avoids offering last week's equal payment (a café, a class) as this week's. Default: keep 3.
13. *Layout (2026-10-06, [proposal](docs/proposals/two_level_layout.md)):* (a) six sections: Overview (Summary, Spending, Health, later Currencies), Budget, Plan, Investments (Holdings, Performance, Planner, Prices), Accounts (Accounts, Transactions, Held for others), Settings. Agree? (b) Each tab's settings behind a gear on that tab, Settings keeping only the profile-wide ones? (c) Drop the two tracking-suggestion fields and the carryover start month for defaults?
