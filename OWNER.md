# For the owner

What only the owner can do or decide. Any AI adds an item here, and removes it once it is done or decided; a decision is first recorded where it belongs (usually Project Overview › Product decisions). AIs read this file only when their task is one of its items.

## To do

- **Before the first tagged release (one-time):**
  1. Create a fine-grained token with Contents: read and write on `Lightning-downloads` only. Save it in this repository as the Actions secret `LIGHTNING_DOWNLOADS_TOKEN`.
  2. Turn on release immutability in `Lightning-downloads` › Settings.
  3. Release with `git tag v0.5.0-beta.1 <commit on main>` and `git push origin v0.5.0-beta.1`.
- **Price packs (one-time):** the public repository `elfekimuhammed/Lightning_Market_Data` exists (2026-10-05); still to do: a fine-grained token with Contents: read and write on it only, saved here as the Actions secret `LIGHTNING_MARKET_TOKEN`, and the repository variable `MARKET_PUBLISH` set to `true`. Until then the collector runs and checks sources but publishes nothing. Only exchange rates (CBE) are published (decided 2026-10-05). A tagged release needs that pack published there, because the release ZIP carries it: until then `v0.5.0-beta.1` stops at its price-files step.
- **04c on your phone:** from [run 37469368422](https://github.com/elfekimuhammed/Lightning/actions/runs/37469368422) install `lightning-android-dependency-probe` over the old probe. When the checks finish, tap **Open Lightning (04c)**, choose Dummy, type `dummy round-trip password`, open a few pages, then press Back. Send all the text shown (or screenshots), plus how the pages looked.
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
4. *Routine audit (2026-10-05):* pain points to decide: Housing 22% vs 45%, "Kept 0", "Split · 0 categories", a certificate named twice, Reserves dropdowns (A16: type and pick).
5. *Upcoming projects* (Project Overview): 17 ideas, each naming its source app. Financial health (#3) and the entry helpers (#9: sums, Ctrl-K, privacy mode, #tags) are built. New from you: multi-currency and FX revaluation (#15), US stocks (#16), reading PDF and Excel files (#17). Which enter *Next*, and where do US stock prices come from?
6. *Restore, from Claude's review of 03a:* unlock re-verifies every retained copy (2.7 s for three 23.5 MB restores). Keep that, or drop it?
7. *Ratios (2026-10-05):* when should a ratio turn strong rose (needs you)? Suggested: loan payments over 35% of income, fixed costs over 50% of it. Until then the four ratio cards on Loans and Recurring stay soft rose (Project Overview › Upcoming projects #3).
8. *Not in the brand guideline (2026-10-05):* the sidebar's Search well and privacy eye (styled as the dropdown's soft search well, pressed in Nile), and privacy mode's 6px blur on amounts. Keep them, or give the rule?
9. *Restore release risk:* after the ordinary Windows dummy-data reboot drill passes, accept real-data restore with abrupt power-loss durability still unverified, or defer it until a controlled power-cut drill passes? The precise failure and fail-closed behavior are in Architecture › Promotion durability risk and release gate. No process-kill or normal-reboot result should be described as power-cut evidence.
10. *Import link window (2026-10-05, [proposal 1.4](docs/proposals/temp-better-features.md#14-finding-the-same-transaction-on-import)):* keep 3 days either side, or widen to 7 like Actual? 7 catches slow card postings; 3 avoids offering last week's equal payment (a café, a class) as this week's. Default: keep 3.
11. *Phone layout (2026-10-06):* the brand guideline has no phone rules yet. Give a phone part for it, or let Claude write a proposal first (`docs/proposals/phone_layout.md`: navigation, the Overview, transaction lists, forms and the profile pages at phone width) for you to approve?
