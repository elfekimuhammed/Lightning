# Changelog

Every change to Lightning is recorded here — newest first. Dates are `yyyy-mm-dd`.

**How to log a change**

- Add it under `## [Unreleased]`.

## [0.5.0b1] — 2026-10-03 — Next Windows desktop beta (package build pending)

- 2026-10-04 · Claude: Packaging review fixes. The shipped-ZIP checks now run on files marked as downloaded from the internet, as users' copies are. Licence notices also cover every package PyInstaller actually bundled, read from its build tables. Test tools (pytest, rich, pygments, httpx and others) are excluded from the app. The docs-only skip no longer misses a file moved out of the app (`--no-renames`). The release job only removes drafts it left itself (marker name), so a published release that lost its tag is never deleted. It also reports API errors as errors, not as "release already exists".
- 2026-10-03 · Claude: Dependable Windows packaging and releases (`.github/workflows/desktop-probe.yml`, now "Windows app"). The Windows build waits for the full Linux suite and is skipped only when nothing but documentation changed since the last successful Windows build (`packaging/ci_scope.py`). The ZIP that is uploaded is the one that was tested: checksum-verified, extracted to a fresh folder, and that `Lightning.exe` must pass the self-check and the WebView2 window check (`packaging/run_check.ps1`: time limit, exit code and report). The frozen self-check now renders the main finance pages and every app file they link on an encrypted synthetic profile, and a failed start records its stage and code locations. `packaging/package_app.py --strict` lists licences only for what ships, plus CPython's, PyInstaller's and the vendored notices in `packaging/notices/` (SQLCipher, OpenSSL, WebView2 SDK, .NET facades, proxy-tools); it writes `BUILD_INFO.txt` and names test builds `-dev-r<run>-<commit>` so they cannot pass for a release. A `v<version>` tag on `main` publishes the tested ZIP to `Lightning-downloads` through `packaging/publish_release.sh`: never replacing a version, draft first, read back byte for byte, then published. The bundled README gives the 5 MiB CSV limit. Owner setup and release steps: Architecture › Build and release.
- 2026-10-03 · Claude: Omar is now **Mohab** everywhere, at the owner's request: Mohab's test (`tests/test_mohab_year.py`), the sample household (`lightning/samples/mohab_2026/`, `generate_mohab_2026.py`, `load_mohab_2026`, the `/sample/mohab-2026` routes), the demo, the welcome page, the docs and older changelog entries. The website and its sample pack follow.
- 2026-10-03 · Claude: Budget group detail (owner request): "Tracked · N categories" and "Not tracked · N categories · X expected" are collapsible lists, each with "Select all" that ticks its rows for the bulk rules (% of income, 3m or 6m average) and updates the "N selected" count. Tracked opens by default; Not tracked starts closed.
- 2026-10-03 · Codex: Set the source version to 0.5.0b1 (display 0.5.0-beta.1) for the next beta. The Windows package workflow now runs from `main` and names the ZIP `Lightning-v0.5.0-beta.1-Windows-x64.zip`. This records the packaging setup only; Windows build verification and distribution are still pending.

## [Unreleased]
- 2026-10-03 · Codex: Owner release policy: permanently retain at least the three newest app versions as separate immutable downloads; append each version to the website archive without replacing older entries, and do not delete versions without the owner's decision. Current seven-day private Actions artifacts do not satisfy permanent hosting.
- 2026-10-03 · Codex: Add **Export for AI** under Settings › Your data. It prepares one local `.xlsx` workbook for All time, YTD, Monthly or Custom, with Lightning-calculated totals, all owned period ledger lines, investment checkpoints and category hierarchy. The period and record counts update immediately; the editable companion prompt is copied when possible, with a visible copy fallback. User text is stored as spreadsheet text, exports are not capped at 1,000 lines or silently truncated, and Lightning does not upload the workbook. Mohab's screen-driven acceptance flow covers the download.
- 2026-10-03 · Claude: Architecture › Page speed opens with why pages were slow and which fix answered each cause (the speed audit now lives only there), and notes the bundled fonts.
- 2026-10-03 · Claude: The Investment planner button uses guideline 3.8's vivid gradient (`--vivid`: #00995C to #0066FF at 135°).
- 2026-10-03 · Claude: Out-of-date prices are flagged (UX plan item 7, guideline A01 honest numbers). `ReportingService.stale_prices` lists holdings valued from a price more than about two months old (cash, at-cost holdings and certificates are left out). The Overview's Needs you shows "Prices are out of date" with the oldest ones and "Update prices"; a holding page says "out of date, update it" beside its price. Mohab sees it a year on, not on his first evening.
- 2026-10-03 · Claude: Brand guideline 3.8, the owner's file, the same as the website's `brand-guidelines.html`. The vivid gradient is two stops, green #00995C to blue #0066FF (dark #3FE0A3 to #5AA9FF), no teal middle; on the website a breakdown shows EGP once on the big figure with bare numbers in its rows, a count in a money list carries ×, and a section about a count shows every item it counts. The website's Version D follows it (UX-2026.10.03.03). The app's Investment planner button still uses the old gradient (see Now and next).
- 2026-10-03 · Claude: Bulk edit (UX plan item 4, user feedback ticket 20). With rows selected in a register, the selection bar offers "Set a category…" and "Set category" beside Export and Delete. `TransactionService.set_category` changes every selected money-in or money-out row in one save, keeping each row's date, amount, counterparty, notes and owner, and leaves transfers, investment and opening rows, split expenses and rows going the other way as they were (the message says how many). Money held for others and system categories are never set in bulk. Mohab searches CIB Payroll for Talabat and moves every order to Food & Groceries at once (10 known gaps left).
- 2026-10-03 · Claude: Import review asks once per name (UX plan item 2). Rows with the same imported name are one block with one Counterparty, Save as, Category, Moved to or from and Held for choice; each row keeps its date, amount, note and skip as a compact 30px line, and its own category only when the statement gave it a different one. Mohab answers 17 names instead of 43 rows; Mohab's 300-row Vodafone statement renders 287 KB and 1,036 options instead of 2.2 MB and 34,800. "Discard this import" (the app's own dialog) removes a statement still in review; Import CSV shows a waiting review first ("… is waiting for you · Continue the review · Discard it"); "Cancel" is "Finish later". The duplicate error message is gone. Mohab's two import gaps are now checks (11 known gaps left).
- 2026-10-03 · Claude: The account register and All transactions read only the 50 rows shown. SQL counts the rows and sums the older movement for the running balance, so a page deep in five years of history costs the same as the first. On a 2,239-transaction encrypted profile the register takes 37 ms instead of 80 ms and All transactions 39 ms instead of 73 ms. Rows now break ties by account, so the two rows of a transfer keep one order across pages. A test checks every page and running balance against the full register.
- 2026-10-03 · Claude: The app uses the guideline's own fonts and logo (A02, A06). Bricolage Grotesque and Manrope are bundled in `lightning/ui/static/fonts/` (latin and latin-ext, SIL OFL), so the PC app no longer falls back to Inter and Plus Jakarta Sans, and browser mode no longer waits on Google Fonts. The two-leaf mark (`lightning/ui/static/lightning-mark.svg`, from the website's `assets/brand/`) replaces the ribbon in the sidebar, the favicon and the profile screen; `lightning.ico` is rebuilt from the two-leaf app icon (16–256px). The old `lightning-logo.png` is removed.
- 2026-10-03 · Claude: First run (UX plan item 1). The Overview shows a "Get set up" card until five steps are done (accounts, history, salary and bills, an emergency fund, a budget); each step is read from the data, ticks itself and links to its page, and the card disappears when all are done. The welcome lists Bank account, Cash, Certificates, Brokerage and Gold and other things with Lucide icons instead of text symbols. A new bank account's next step is "Import a statement" (primary) or "Add a transaction". With no income planned, Cash planning shows "Add your salary and bills to see where your cash is heading" instead of a forecast built from nothing, and the Lowest point card waits for it. Mohab now checks the setup card halfway through his first evening (2 of 5 done) and that it is gone by October.
- 2026-10-03 · Claude: Owner decision: SQLCipher no longer wipes freed memory (`cipher_memory_security = OFF`). Encrypted ledger reads are about 3× faster: on a 2,239-transaction encrypted profile the account register takes 80 ms instead of 239 ms, All transactions 73 ms instead of 305 ms, and the Overview 139 ms instead of 237 ms. The key is still wiped; Architecture's threat model records what freed memory may hold. `tests/test_encrypted_database.py` checks it stays off.
- 2026-10-03 · Claude: Category pickers follow guideline 3.6 (A10.3, A11). The import review starts each unanswered row on an empty "Choose a category" (Uncategorized stays a choice; posting is unchanged). Clicking a picker lists every choice under its L1 as a bold header, never "L1 › L2", and selects the current text so typing replaces it; typing filters by group and name ("transp" shows Transportation under Personal and Work). The register's picker no longer filters by the row's own category. Mohab's two picker gaps are now checks (13 known gaps left). The Planned and Left in plan definitions moved into the figure registry (`lightning/core/figures.py`), which generates the Glossary; the previous hand edit had failed `tests/test_figures.py`.
- 2026-10-03 · Claude: Faster pages. Each request now computes a repeated figure once (`lightning/core/memo.py`, wired in `ui/web.py`): holdings, net worth, custody, money out by category, the position, the investment report and the category, asset and account look-ups. Any write, and any open transaction, bypasses or empties it, and nothing outlasts the request, so no figure can be stale. On a 2,239-transaction ledger, Budget › All time drops from 4.6 s to 0.33 s (7.0 s to 0.41 s encrypted), the Overview from 0.51 s to 0.16 s (0.96 s to 0.24 s encrypted) and Expense analysis › All time from 0.46 s to 0.30 s, with identical pages. The PC window now keeps `/static/` files for the session instead of re-fetching them on every click, and the logo is 5.8 KB instead of 513 KB. `tests/test_reporting_performance.py` caps SELECT statements per main tab and checks the pages match with the cache off.
- 2026-10-03 · Claude: Brand guideline 3.7, Part B (website) only, at the owner's request: hero and section headers centred, a short label above each section, and the hero's punch line in the gradient. Part A is unchanged. On lightningeg.com the two-leaf mark replaces the old ribbon mark everywhere, and Version D (`version-d.html`) is the landing page built from the guideline; the audit is in the website repository under `audit/`.
- 2026-10-03 · Claude: Owner decisions. (1) Budget's background estimates count in Left in plan, and a small "!" says when one is low confidence and why ("Includes 14,200 for Travel: an estimate from one month of spending…"). The month's plan comes from one service method, `BudgetService.plan_summary`, so the Overview and Budget now show the same figure (Mohab's September: 11,853 left of 38,898, where the Overview said −2,317 of 24,698). (2) The Overview's Investments section is one row (Portfolio value, Holdings value, Money added, Net gain or loss) with "See investments"; its donut, class bars and movers are gone, and the page no longer computes them.
- 2026-10-03 · Claude: `AGENTS.md` makes the brand guideline strict for every visual: check A16 before pushing, the guideline wins over CSS, and nothing outside it is invented.
- 2026-10-03 · Claude: `AGENTS.md` rewritten as the one set of instructions for every AI: which files carry the project and when to update each, the six steps of every task (pull, claim, small pushes, test with Mohab, write it down, hand off), what to do when a push is rejected, product rules and the git rule. `CLAUDE.md` points to it. The owner's decisions on budget estimates and the Overview's Investments section are recorded in the Project Overview.
- 2026-10-03 · Claude: UX batch 1 against Brand guideline 3.6 (ranked plan for the rest in Project Overview › UX plan). KPI cards are coloured by meaning (`surface-in|hold|out|over`) with an icon tile, and the label sits under the icon and chip; Needs you says "Personal over plan" and "Sahel trip is past its date"; the plan card reads "Over plan · 2,317" instead of "Left in plan −2,317"; a savings rate below −100% shows "—" with the gap in words; rates use a true minus and separators; Safe to spend gives a per-day figure only for a week or more. Four, then Other in donuts, the Sankey ("Other", "Kept" in green), treemaps, bars, small multiples and the loans list. Section headers carry only the title and dates. Trend month labels thin out and no longer overlap. Registers show money out in ink and transfers without a sign, and no longer clip the balance at 1,366px. Fields are soft wells, Cash planning sub-tabs are Nile, no all caps, budget spent is soft rose. Transaction, holding, planner and prices pages get a Back route from the page that opened them; the bank check's review link returns to the check. Accounts calls its total What you own. Mohab's expectations follow the new words.
- 2026-10-03 · Claude: Speed audit of the PC app from source (nothing packaged), recorded under **Page speed** in `docs/ARCHITECTURE.md`. On a 2,239-transaction encrypted profile the Overview takes about 0.9 s on the server and Budget › All time about 6.3 s (remembered, so every later Budget visit). Main causes: the same figures recalculated many times per page (14 positions and 94 ledger scans per Overview; 3,860 month-spending queries per All-time Budget), SQLCipher `cipher_memory_security = ON` (ledger scans about 3× slower), and registers that summarise every row to show 50. A request-scoped cache prototype gave identical pages, with the Overview about 2.7× and the All-time Budget about 17× faster. No code changed yet; the plan is in Architecture and the two owner decisions are under **Now and next**.
- 2026-10-03 · Claude: The brand guideline is now one file, `docs/BRAND_GUIDELINE.html` (3.6: Part A the app, Part B the website), the same file as the website's `brand-guidelines.html`. Removed `docs/APPLICATION_BRAND_GUIDE.md`, `docs/APPLICATION_BRAND_GUIDE.html` and the 2.10 generator in `tools/brand_guide/`. `AGENTS.md` gains the two-AI working rules (pull first, small pushes, dated and signed changelog entries, a **Now and next** hand-off at the top of the Project Overview).
- Fixed two tests that failed on `main`: the profile-gate test now awaits Starlette's `request.form()` wrapper, and the picker test allows set-up calls between inserting popup content and enhancing its pickers. With the hash-locked Linux dependencies (including `sqlcipher3`), the full suite passes.
- Add account-level **Change ownership**: move cash between the user's share and a saved person while keeping the account's gross balance unchanged. The posting goes through `TransactionService`, validates each owner's dated cash position, and appears as a readable ownership event.
- Add **Someone paid an expense for you**: record the owned expense against its category and attribute the matching in-account cash share to the payer. It counts in spending and budgets, preserves gross account cash, and can be linked to a reserve or planned payment.
- Keep new cash ownership history in the ledger. Legacy unlinked custody records remain readable for compatibility; edits, voids and restores validate resulting owner balances.
- Extend Mohab's screen-driven year to assign cash to a saved person and record an expense they paid, confirming that the account's gross cash does not change.
- Replaced line-by-line bank reconciliation with **Check against bank**: type the balance the bank shows on a date. A difference up to 1% of that balance or 100 (whichever is larger) is settled with one "Balance adjustment" row, counted as Other Personal spending or Other Income; a bigger one cannot be adjusted and links to that month's register or Import CSV. Mohab's October check is now one typed balance instead of 62 Clear clicks.
- Mohab's test and the Project Overview now state what the test focuses on: right answers, usability, efficiency, speed, simplicity, clarity and UI, in the Windows WebView2 app.
- Mohab's year now walks through user feedback batch 001: 11 fixed points are checked and 13 open pain points are strict expected failures in `tests/test_mohab_year.py`.
- Removed `tests/test_mohab_matching.py`; `tests/test_mohab_year.py` remains the single Mohab acceptance test.
- Added the owner's git workflow rule to `AGENTS.md` and a `CLAUDE.md` that loads it: work on `main`, push every branch, and merge finished branch work into `main`.
- Improve protected-profile CSV imports: accept source CSVs up to 5 MiB, with separately bounded mapping and review requests; keep unrelated forms at 512 KiB and uploaded bytes in memory (no plaintext temp-file spill). The importer remains CSV-only; PDFs are not supported.
- Make success/status messages accessible and temporary (five seconds); keep errors visible with ink-on-rose styling. Register balance clipping was not reproduced; the existing horizontally scrollable layout remains unchanged.
- Batch-load account/asset/class metadata in holdings and investment reports. In the 319-transfer synthetic report, SQL stayed at 6 reads instead of 641 per-row asset lookups; this service-level improvement does not yet establish the <500 ms full-tab goal.
- Corrected Batch 001 feedback traceability: App Feedback now attributes the 27 existing tickets to El Feki, records unavailable sender emails explicitly, and uses unique sequential Ticket # values 1–27.
- Added `user feedback/user-feedback-batch-001.md`, a polished and grouped compilation of the 27 current App Feedback submissions, with source-ticket traceability and prioritisation.
- Replace the app's former bolt mark with the supplied blue-and-teal ribbon logo in the main and profile headers and favicon; use its ICO conversion for the Windows executable. Package workflow artifacts now contain the named distributable ZIP and its SHA-256 file rather than only the loose app folder.
- Update Mohab's demo CD to use a real portfolio purchase rather than a cash opening balance, keeping the sample aligned with the no-cash CD rule.

### Export selected records · 2026-10-02
- Transaction registers, Categories, and the reevaluation ledger now offer **Export selected** after checking rows.
- Downloads are CSV files containing only the chosen records. Transactions include their ledger lines; categories include hierarchy and flags; reevaluations include checkpoint detail and the main-journal link.
- CSV text is protected from spreadsheet formulas, amounts keep their stored precision, and exports are capped at 1,000 selected records.

### CD purchase, maturity term and account navigation · 2026-10-02
- CD purchases now validate available user-owned cash in the selected bank/cash account on the recorded purchase date, then replay later posted cash movements so the CD cannot make a later balance negative. Unrelated negative history before the purchase date no longer blocks the purchase; a real shortage reports its date and amount.
- Maturity can be entered as a date or as a term in years (three-month increments). The two fields stay in sync, and a term calculates a calendar maturity date from the purchase date.
- **View CDs** sits in the account page's right-side actions, alongside other account actions.

### Settings: start fresh · 2026-10-02
- Settings › Your data has a **Start fresh** card.
- **Desktop app:** **Start a new profile** locks the current profile and opens the new-profile setup, with its own password and recovery key. The old profile stays exactly as it is and can be opened again from Profiles.
- **Browser mode:** **Start a fresh database** asks first, then:
  - backs up the current database;
  - sets it aside next to itself as `<name>_before-fresh_<date-time>.db`;
  - opens an empty database at the usual path.

  Nothing is deleted. If the file can't be moved (another program has it open), nothing changes.

### Budget: saved and invested, for the period · 2026-10-02
- The Budget's Savings rate card becomes **Saved and invested**, the same card as on Investments:
  - money in as 100 squares: invested in blue, kept in green, spent in rose;
  - the savings rate and the investing rate, which is part of it.

  It always covers the period chosen in the header.
- The split is worked out once in `investments.report.saved_and_invested()`, so Budget and Investments always agree. Before, it was calculated in the Investments page code.

### CD portfolios grouped by bank · 2026-10-02
- A `DEPOSIT` account is a bank-specific CD portfolio identified by its Institution field; it cannot hold cash.
- Each certificate is a separate non-cash `DEPOSIT.CD` asset with its own name and terms. Buying it creates a `BUY` ledger transaction funded from a bank/cash account the user selects.
- Interest and maturity proceeds remain forecast estimates. Interest is never posted automatically; users record it manually from bank statements. Actual redemption records the principal proceeds entered by the user.
- Migration `0039_cd_portfolios.sql` preserves old account-level `cd_terms` as legacy without destroying or automatically converting them. Cash left in old `DEPOSIT` accounts must be moved out; legacy terms remain until a history-safe conversion workflow exists.

### Our own calendar on every date field · 2026-10-02
- The calendar button on every date field (register rows, forms, popups) now opens Lightning's calendar instead of the browser's:
  - weeks run Monday to Sunday;
  - today is ringed and the chosen day filled;
  - Today and Clear sit at the bottom.

  It works from the keyboard and opens inside popups.
- The button shows a calendar icon instead of ▦.

### Calendar heatmaps, even range bars, every stat card fuller, the planner restyled · 2026-10-02
- Expense analysis ends with **Day by day**: the period as a calendar, total expenses on the left and net
  cash flow on the right (green kept, rose short). One month shows each day's date and amount; a longer
  period shows a small month per month, the last twelve at most. Weeks start on Saturday, the biggest day is
  darkest, and every day opens its transactions. It replaces the category-by-month table and the money in /
  money out / net table, and the outlined month is gone.
- The Overview ends with **Month by month**: the same calendar by month, a row per year since the first
  record, total expenses beside net cash flow; each month opens Expense analysis for that month.
- Inside its usual range?: every bar is now the same size. The pill runs from the lowest month (its value on
  the left) to the highest (on the right), and the status and now sit on the right.
- New `flows_by_date` in reporting: money in, money out and net per day or month, counted exactly like
  `cash_flow`, from one grouped query.
- Every stat card's number now grows with its card (smaller past seven characters), the sparkline sits
  above the number instead of behind it, and chips such as "until 2026-11-01" no longer clip.
- Investment planner: "How to split it" is the app's pill segment, the suggested split uses asset class
  colours instead of a rotating palette, and the labels match the guideline.
- Cash planning's tab bar scrolls on one line on phones instead of widening the page.
- App guideline 2.10 · Juniper.

### Dropdowns open inside popups again · 2026-10-02
- Select boxes in a popup, such as Account type when adding an account, opened their list behind the popup, where it couldn't be seen or clicked. The list now opens inside the popup.

### CD terms, interest projections and Mohab workflow fixes · 2026-10-02
- `0038_cd_terms.sql` — store certificate terms separately from ledger balances and preserve the estimated schedule across restarts.
- Add terms for each funded certificate account: principal, start, separate earliest-withdrawal and maturity dates, annual percentage rate, simple or compound interest, simple payout and compound capitalization frequency, and a bank/cash destination. Terms never create ledger entries; actual interest and principal transfers are recorded separately.
- Project simple-interest payouts and compounded maturity proceeds into Cash planning using actual days/365. Show CD proceeds separately from income, and do not add future proceeds to today's Free cash or Safe to spend. Suppress projections for unfunded CDs and replace a maturity projection when a future transfer is already recorded.
- Treat a CD as unavailable in *If you sold today* before its earliest withdrawal date. Use the CD class sale factor as an early-redemption estimate until maturity, then full remaining principal; Net worth and Free cash do not change. Bank fees and payout figures remain estimates, not bank quotes.
- Suggest early or changed recurring payments for explicit confirmation, store the transaction's actual paid amount, attribute linked recurring salary to its scheduled month in the income average, and prompt a later-plan and reserve review after a changed amount. No plan or reserve amount changes automatically.
- Bring Investments holdings down to five table columns with secondary details in an expandable row, and add progressively enhanced type-and-pick controls for reviewed own-data fields, retaining native form fallback.

### Release-readiness and finance audit · 2026-10-01
- Verified UI fixes: Budget overlap near 941px; Cash planning's tab strip and the shared period pill at 390px; Settings data-card overflow; account and all-transactions registers scrolling inside their cards.
- Updated Project Overview for the live net-worth history and income audit: Bonus is excluded from the average by default; early January salary booked in December drives the step 17 inflation. Four finance xfails remain open, and no-pay-month averaging has no dedicated assertion. Investments' nine holdings columns versus the guide's five and the own-data dropdown mismatch await owner choices.
- The profile selfcheck passed all six checks on synthetic data, and the full suite passed with four xfails and two skips. Ordinary Windows PC acceptance is still outstanding; no ZIP has been released. These results do not establish every finance case or an interactive click-through of every control.

### Shared Codex project context · 2026-10-01
- Add a short root `AGENTS.md` that routes repository tasks to the current
  product, architecture, visual, glossary and changelog sources without
  copying full documents into every task.

### Investments: calmer holdings, the waffle back, fuller cards; the month stepper · 2026-10-01
- Holdings: the total and class rows lose their bands; a thin hairline separates each class instead. Names are
  ink, only the gain percentage carries a colour, and the horizon is a quiet word (Short, Medium, Long, or Set)
  that opens its choice when clicked, in place of the coloured letters. Units read on one line with more room.
- Saved and invested is a waffle again: 100 squares of this period's money in, invested first, then kept, then
  spent, with the savings and investing rates beside it.
- The top cards' numbers grow with the card, so no card looks empty; the six-month line sits above the value,
  and Net gain or loss shows Growth and XIRR as two small figures at the bottom.
- The month stepper is one pill like the period buttons beside it: round chevrons and the month in a white
  pill. The month picker's year arrows match.
- App guideline 2.9 · Yarrow: grouped tables, the split waffle, numbers that fill their card, the month stepper.

### The period you pick stays picked · 2026-10-01
- The period chosen in a page header (All time, YTD, a month, or a custom range) now carries over to Overview, Budget, Expense analysis and Investments as you move between them.
- It stays until you pick another. A pick that shows an error is not remembered.

### Cash planning, tab headers and the Ask dialog · 2026-10-01
- Cash planning's Plan tab opens with four stat cards: Safe to spend (with about how much a day until your next
  income), Free cash, Due before your next income and Lowest point ahead. Then three questions: How is safe to
  spend worked out? (a waterfall from free cash, beside a 30-day timeline and its payment list), Where is my cash
  heading? (five month-ends of free cash, then the forecast dashed, beside money in and out per forecast month)
  and What is promised? (what you owe, beside the five biggest loans still to pay, then Others). The forecast
  table moved under Show the numbers. Add bill and Add loan left the page header; adding stays on Recurring and
  Loans.
- Every Cash planning tab (Plan, Recurring, Loans, Reserves) sits in a pill bar with icons and opens with its
  own header: an icon tile, the tab's name and one line on what it answers, in the tab's own accent.
- The browser's confirm and alert boxes are gone. Discarding unsaved changes in a popup, deleting a
  transaction, category or counterparty, applying budgets in bulk and the "select a category first" notice
  all use the app's own dialog: a white card with an icon in its tone, the question, one line on what happens,
  and buttons that say what they do. Escape and Cancel answer no; focus starts on Cancel before a delete.
- The App guideline is 2.8 · Clover: the timeline, forecast trend and flow columns are now in the app, with
  rules for tab headers and the Ask dialog. Its visual page is also written to
  `docs/APPLICATION_BRAND_GUIDE.html` by `tools/brand_guide/build.py`.

### Investment planner: biggest gaps first · 2026-10-01
- The planner has two ways to split new money: **Spread across gaps** (as before: every class below target
  gets the same share of its gap) and **Biggest gaps first** (the class furthest below its target, in
  percentage points, is filled until it is level with the next, then both together, and so on). When the
  money covers every gap both give the same split. The choice is remembered.
- Rounding cents now go to the largest suggestion, so a split always adds up and never shows a negative amount.
- One split function (`suggest_contributions`) serves the planner; the unused copy on the Investments page is gone.

### Investments and report pages, lighter · 2026-10-01
- Saved and invested is one light bar of money in: invested inside saved, then kept, then spent. Investing rate
  now counts only what came out of this period's savings, so it is never more than the savings rate; money
  moved in from earlier savings is noted.
- Report tabs carry no add buttons: Add holding, Target allocation and More actions are gone from Investments
  (holdings are recorded from their account; prices, the reevaluation ledger, new investments and targets are
  linked from Settings › Valuations). The Investment planner stays, now in the Meadow green gradient.
- Holdings open with an All holdings total row; class rows are soft bands and rows have no hairlines.
- The Reconcile portfolio value card is gone from the middle of the page.
- In the net cash flow heatmap only Net flow is coloured (green kept, rose short); money in and out are grey.
- Unit prices round to the unit too, except prices under 10.

### Expense analysis: five then Others · 2026-10-01
- Every item chart shows the five biggest categories, then everything else as one "Others".
- Small multiples sit beside the treemap. Month by month is two heatmaps side by side: money out by category,
  and net cash flow (money in, money out, what was left); the second needs no category filter.
- Each visual keeps a "Show the numbers" table.

### Whole units on reporting pages · 2026-10-01
- Overview, Budget, Expense analysis, Investments (with each holding and Target allocation), Cash planning's
  Plan and the Settings tables show money rounded to the nearest unit, key notes included. Values are still
  stored with their decimals, and registers, entry fields and their messages keep cents.
- Clustered columns put each value on top of its bar, the name right under the bars and the change against
  usual under the name.

### Counterparties learn their category and their spellings · 2026-10-01
- **Usual category:** each counterparty is filed under the category picked most often in its last 20 transactions, or the most recent one on a tie. Aliases count with their counterparty.
  - It fills in as soon as you pick the counterparty in the register, and when you save with no category.
  - It also applies in bank imports.
  - A default set on the Counterparties page still wins. That page shows the learned one as "Learned: Groceries", with "7 of the last 9" under it.
- **Learned aliases:**
  - The register's counterparty list now also offers close spellings under "Did you mean".
  - If you type "Talabaat", then press Enter or pick "Talabat", the typed spelling is saved as Talabat's alias, so it matches straight away next time.
  - Only close spellings that match nothing yet are learned. Picking a different name ("Uber" → Careem) is not.
  - A full alias list never stops the save.
- A counterparty can now hold **20 aliases** (was 10).

### Expense analysis cards · 2026-10-01
- Money out and the comparisons are one wider card: the amount and a six-month sparkline, then against the
  period before and against your usual month underneath.
- New card: Average payment, with how many payments and how many in the period before.
- Largest payment says how many times the average it is. Stat cards get depth: a top light, a lift on hover.
- Where did it go is half treemap, half ranked list of the big categories with each one's change against
  its usual month.

### Our dropdowns, percent steppers and table rows · 2026-10-01
- Every select box opens our own list: group headers, details indented, the current choice marked and a search
  on long lists (phones keep their native picker).
- Every % field has our own up and down chevrons, one whole percent a step; sale factors step by 1.
- Sale factors drop the "a factor here applies…" line under each class.
- Counterparties is a table of rows: inline row fields, the name takes the room, Delete is an icon.
- Cards stacked on a page keep a 20px gap.
- Target allocation can set a target on every class it lists, deposits included.

### Target allocation adds up to 100% · 2026-10-01
- A target that would take the total past 100% is refused, and the message says how much is left.
- Value to adjust is how much to buy (or sell) of that one class to reach its share with every other class
  left as it is: (target × total − value) ÷ (1 − target), because buying grows the total too.

### Categories, two by two · 2026-10-01
- Two categories side by side, each always editable: name, + / − / ±, Recurring and One-off as on/off pills,
  and add detail, archive and delete always visible. Changes save as you make them.
- An empty top-level group other than Personal, Work, Investment and System no longer shows.
- The "?" tips on Target allocation open to the right of the "?" and are no longer cut off.

### Docs: back to four files · 2026-10-01
- `docs/` holds only Project Overview (the story), Architecture (the technical side), the App brand guideline (the visual side) and the Glossary.
- The desktop build spec, review and plan, build status, work log and profile preview are folded into Architecture › Desktop app and encrypted profiles, describing what is built today. The milestone is now on the Overview roadmap.
- The research prototypes in `docs/desktop/reference/` (`encryption_prototype.patch`, `keyvault_sketch.py`) are removed: `lightning/security` and `lightning/database` now implement them. They remain in Git history.
- The brand guide's visual page and its generator moved to `tools/brand_guide/` (`python tools/brand_guide/build.py`).

### Expense analysis · 2026-10-01
- Four KPI cards give the gist of the period: money out against the period before, against your usual
  month, the biggest category with its share, and the largest payment.
- Then five questions, big categories only (anything under 1% of money out folds into "Smaller
  categories"): a treemap of where it went; now against your usual month as clustered columns beside each
  category's usual range; small multiples on one scale; and a category-by-month heatmap that ends with
  every month of the period you chose.

### Investments · 2026-10-01
- The page opens with three tiles: a waffle of what you kept and invested in the period, the period's
  Net gain or loss with Growth and XIRR, and Portfolio value with a sparkline that always covers the last
  six months.
- Allocation by class beside the biggest holdings; holdings grouped by class, both sorted by weight, with
  Units, Average cost, Cost, Current price, Current value, Unrealized gain %, XIRR (after a full year) and
  Horizon. An assigned horizon shows a letter badge (S, M, L); click it to change.
- Year-to-date dividends per holding beside the period's money in and out and each class's change in value.
  The horizon bar is always open, at the end.
- Each holding opens a page that answers: is it making money (price against average cost, where the return
  came from), how bumpy has it been (monthly moves, best and worst month, typical move, fall from its high)
  and its journey (value against cost, every trade and payout).
- New figures: Average cost and Growth.

### Category lists without breadcrumbs · 2026-10-01
- Every category picker (counterparties, bills and loans, bank imports, reserves, splits, the transaction
  form and the register's type-to-pick list) groups categories under their L1 as a header, each by its
  own name; an L2 with L3 detail reads as a header with its details indented under it. "Personal › Food"
  no longer appears anywhere, including tooltips and messages ("Added Groceries under Food & Groceries").

### Budget · 2026-10-01
- The top is a savings-rate waffle beside one plan bar: spent in azure, what is left in green, over plan in
  strong rose past the plan. The three cards are gone; their figures sit under the bar.
- Spent of plan is a bullet per category: the plan as a soft band ending in a tick, spent inside it,
  anything over carried past the tick in rose, with what is left or over on the right.
- Investment categories are never budget spending (fees and moves into investments stay in cash flow).
  One-off categories are left out of the budget's totals.
- The first-plan form groups categories under their L1 with compact row fields; the bulk-rules toolbar and
  rule fields match the row style; select boxes use the app's own style everywhere.

### Page width · 2026-10-01
- Every screen uses 90% of the space beside the sidebar, centred, and never less than the 1,120px content
  width (or the whole space on smaller screens).

### Valuations and target allocation · 2026-10-01
- Sale factors are grouped by asset class and compact. A factor on a class (Funds) applies to every
  kind left empty (Equity Fund, Gold Fund…); a kind's own factor overrides it, and clearing it goes back
  to the class's. Migration `0037_sale_factor_inheritance.sql` clears factors that only repeated their
  parent's, so every estimate stays the same.
- Target allocation lists every class, heaviest first; the Add a class chooser is gone. Difference reads
  in %, not pts. Each class has a "?" with a one-line definition. An empty field clears the target.
- Fields inside table rows use one inline style: a light green shade of the row, no border until you
  are in it.

### Categories overhaul · 2026-10-01
- Categories go one level deeper: an L2 can hold L3 detail (Food & Groceries › Groceries). L3 can be chosen
  on a transaction and rolls up into its L2 everywhere.
- A fourth top-level group, **System**, holds Money Held for Others and Loan payments (migration
  `0036_category_direction_and_system.sql`). Both keep their ids, so every transaction keeps its category.
- Every category shows **+** (income), **−** (expense) or **±** (both). You can change it; inside each group
  categories are soft-grouped by it, then sorted by name.
- Income categories are **Recurring** (counted in the income average and the forecast) or **Irregular**
  (bonuses). Bonus starts irregular, which fixes Mohab steps 26 and 27: an end-of-service payment and a
  month between jobs no longer lift Average monthly income. Expense categories can be **One-off**: they stay in cash flow and analysis but leave the
  budget's totals and estimates. Both flags are the same lists as Settings › Budget.
- The Categories page is one table: L1 as a header, an L2 with detail as a sub-header, L3 indented. Click a
  row to edit it in place. Archived categories are hidden behind an Archived link.
- Settings › Budget is compact: fields side by side in groups, choices as chips grouped under their L1.

### Overview 2.5 · 2026-10-01
- Net worth, Free cash and Net flow are wide split cards: numbers and toggle list left, the visual right.
- Where money in went is a Sankey; Cash flow has a column waterfall; Investments is its own section.
- No chart sits behind a toggle; Month by month is stashed (App guideline § 16).
- Four stat cards: Change in net worth, Savings rate, Investing rate and Left in plan. New figures
  Change in net worth and Investing rate.

### Mohab's workflow covers a salaried year · 2026-10-01
- **Steps 11–28 of the reference workflow** now carry Mohab from October 2026 to September 2027. They are dated, and each step has the figures it must show. The year includes an ATM fee, a refund, a repair paid from the emergency fund, a dividend, a reimbursed work expense, a bonus, an early payday, a raise, Eid, phone installments, a share sale, a rent rise, a holiday goal, and a job change with a month between jobs.
  - Each step says what is true today.
  - What Lightning cannot record yet (a gam'eya, a maturing certificate, dollar savings, early loan payoff) is listed separately.
- **`tests/test_mohab_year.py`** runs those steps on the demo household, one test per step. The steps that are wrong today are strict expected failures, so a fix shows up as an unexpected pass.
- **The questions** gain the follow-ups a salaried user asks, and a new question 8, "What changes when my pay changes?".
- **Wrong today** (recorded, not fixed):
  - A salary paid early, or a raise over 10%, is not matched, so the forecast counts it twice.
  - A rent rise matched within 10% leaves the plan at the old rent.

## [0.4.0b1] — 2026-10-01 — First Windows desktop beta

### Desktop beta v0.4.0-beta.1 packaging · 2026-10-01
- Show the version in the Windows title and Settings. Align package metadata with it.
- Download one readable GitHub ZIP containing only the Lightning app, not a ZIP
  inside another ZIP with engineering-probe reports. Use one extraction.

### Key notes: the number first · 2026-10-01
- Every key note and the small cards on Expense analysis now read like a stat card:
  - a short label with a small tone icon;
  - **one big figure**, green when good, rose when it needs you;
  - one line of context;
  - one pill button.

  Examples: "Saved · 2026-09 → 32.4%", "Safe to spend until … → 49,520.84", "Bills · share of income → 30%".
- `keynotes.note()` gains `label` and `figure`. The full sentence stays as the title and the screen-reader label.
- App guideline 2.4 · Meadowlark documents the structure.

### Key notes that stand out, softer register fields, row actions on right-click · 2026-10-01
- **Key notes and the small cards on Expense analysis:**
  - Each card is a full tint of its tone with a matching border.
  - A solid colour tile holds a white icon that matches what the note says: trend up or down, wallet, share, alert, calendar, shield, people or tag.
  - Links take the tone's dark shade.
- **Register editing:**
  - The fields of the row you edit are a soft shade of the row, not white.
  - The field you are in turns a deeper shade with the green edge forms use.
  - The add row behaves the same way.
- **The bar under an edited row is gone.** Right-click the row for Save, Details and history, Cancel edit and Delete. Enter saves and Esc cancels. Other rows' right-click menu gains Details and history.
- **App guideline 2.3 · Glade** documents all three. Both halves are updated, and the azure-versus-green focus gap is closed.

### Desktop profiles and encrypted storage foundations · 2026-10-01
- Add Documents/Lightning profile paths, explicit alternate locations, read-only discovery, human-readable date/sequence/ID names and OS-backed profile locks. This is the upcoming launcher's storage contract; existing user files are not moved.
- Add an opt-in SQLCipher database driver, verified encrypted snapshots and explicit staged legacy import/recovery candidates that preserve their sources. Password screens and live restore are not yet connected.
- Commit migration SQL and its bookkeeping atomically, validate schema/resources before writes, and require protected verified pre-upgrade backups before upgrading existing data.
- Keep backup names identifiable by profile; pruning never touches another profile or protected upgrade backups. Update the existing Settings backup list for the new names.

### Windows desktop feasibility build · 2026-09-30
- Start the amended desktop plan with an isolated Windows one-folder build, protected loopback host, WebView2 navigation guard and synthetic encryption/resource checks.
- The first build is an engineering check, not a finance beta. It does not open or convert existing financial data; Linux browser operation is unchanged.
- Add password/recovery primitives shared across platforms, bounded tamper tests and a Windows build workflow. Password unlock is the chosen design on both operating systems; DPAPI is deferred.
- Remove the tracked `nul` artifact so Git for Windows can check out the repository. It remains recoverable from Git history.

### App guideline 2.2 · Grove: one guideline, with a visual page · 2026-09-30
- `docs/APPLICATION_BRAND_GUIDE.md` is rewritten as one unified guideline in 16 numbered sections. Its visual half, `docs/APPLICATION_BRAND_GUIDE.html`, uses the same numbering and shows every rule as a live sample. Rebuild the page with `python docs/build_brand_guide.py`.
- New in the guideline:
  - **Soft register fields:** 30px tall, `#F2F8F6` fill with no border, white with an azure border on focus. The row being edited takes the held tint.
  - **Stat cards:** three in a row, the first on the lead gradient.
  - **Key notes:** a tone tint fading to white, a 4px edge and a 32px icon tile.
  - **Cards:** the lead (gradient), wide, white and entry cards side by side, all with the app's 20px radius.
- **Charts:** a full catalogue of 40 chart types, each drawn with sample data and its use, rules and page:
  - 13 are in the app;
  - 25 are ready to use when a page needs them (forecast with range, Sankey, treemap, dumbbell, bullet, calendar heatmap and more);
  - 2 are marked to avoid.

  A "Never" list covers dual axes, 3D, gauges, radar and pies.
- **Where the old guideline and the app disagreed, the guideline now follows the app:** one type scale, the waterfall colours, the vivid gradient on the Investment planner button, and "Net gain or loss".
- No app behaviour changed. Two code comments now point at guideline 2.2.

### Desktop build spec (draft) · 2026-09-30
- New `docs/desktop/BUILD_SPEC.md` describes the Windows desktop app: one `Lightning.exe` window (pywebview, WebView2, PyInstaller) and data in `%LOCALAPPDATA%\Lightning`.
  - The database and backups are encrypted with SQLCipher. The key comes from a recovery key, and the app opens automatically through Windows DPAPI or asks for a password.
  - The local server needs a per-launch secret on every request.
  - It ends with ordered milestones, each with acceptance tests.
- It is a draft: nothing in it has run on Windows, and it has had no verification pass.
- `docs/desktop/WORK_LOG.md` records this session's work and the research behind the spec. `docs/desktop/reference/` holds the encryption prototype patch and the key-management sketch. Neither is production code.
- No application code changed.

### A chart with its numbers: net worth trend, free cash steps, richer Expense analysis · 2026-09-30
- **Overview:**
  - A net worth trend (the end of each month) sits at the top of Your position, with the breakdown cards under it.
  - Free cash shows its steps as a small waterfall: cash you own, less reserves and bills due, down to free cash.
- **Expense analysis** gains:
  - Compared with your usual month: each category this month against the average of the three months before, with a mini trend and the difference.
  - Who you paid, and Paid from (which account).
  - The largest payments.
  - These breakdowns add up to Money out.
- **Register:** the add row's fields are line-height and softly tinted instead of white.

### No browser history under fields · 2026-09-30
- Fields no longer show what you typed before, such as old names, amounts or "Gold 24k". The only suggestions left are the app's own: counterparties, categories and accounts. This applies to every form, popups included.

### Target allocation page, three-card summaries, key notes with colour · 2026-09-30
- **Target allocation:** it has moved from the bottom of Investments to its own page, opened from a button in the Investments header and from a new Settings tab.
  - Columns: Current %, Required %, Difference, and Value to adjust (how much to invest in a class, or take out, to reach the required share).
  - A Total row shows the required shares' sum and the portfolio total.
  - Each Required % saves on Enter or when you leave the field. The table redraws in place, so the page doesn't reload or scroll away.
- **Expense analysis:** Money out and its two notes sit side by side as three small cards.
- **Key notes:** each note's card is tinted by its tone (green good, blue info, rose needs you), with an accent edge.

### Asset class colours, grouped categories, popups to full pages · 2026-09-30
- **Asset class colours:** each class has its own colour in a family (cash azure; deposits, money market and fixed income in teal to light green; gold and gold fund; stocks and equity fund in greens; other in greys). The colours are in the app guideline, and a Total line under each donut says what share of the whole it covers.
- **Categories are grouped:** "Where it went" and Expense analysis show each L1 category as a header with its L2 categories under it.
- **Overview:**
  - The net flow number has its own label.
  - Investments is a header you can open, showing the portfolio value and the net gain or loss while closed.
  - Free cash has a "Plan to invest" button.
- **Investment planner:** its own button in the Investments header, in the Meadow gradient.
- **Popups:** every popup has a full-page button. A page opened that way, or from any other page, has a Back button to where you were.
- **Transaction editing:** a soft blue tint, and fields the size of the row, so it no longer jumps.
- **Holdings:** set the horizon straight from the table.
- **XIRR:** the yearly return shows on the Portfolio value card, with a "?" that explains it.
- **Fixed:** Money added listed every transaction in the period, including groceries and rent. It now lists only money that moved into or out of investment accounts, and the list adds up to the figure.

### Docs: four files · 2026-09-30
- `docs/` now holds four files. Project Overview tells the story, Architecture holds the technical side, the App brand guideline holds the visual side, and the Glossary defines terms.
- Merged into those files and then removed: `PRODUCT_UX_ARCHITECTURE.md`, `UX_REVIEW.md`, `BUDGET_APP_GAPS.md`, `UI_AUDIT.md`, the Mohab persona reports in `docs/personas/`, and `application-brand-guide.html`, which is now written out in `APPLICATION_BRAND_GUIDE.md`. All of them remain in Git history.
- The docs describe the Overview with Birdview folded in, and use the new figure names (Net gain or loss, Gain from sales, Money added and the others).

### Birdview folded into the Overview; budget rows; clearer names · 2026-09-30
- **Birdview is gone.** The Overview is the quick glance, and the reports under it (Budget, Investments, Expense analysis, Cash planning) carry the depth.
  - The Overview gains "What it is made of" (everything you own by kind) and "If you sold today" (each class with its sale factor), side by side in one wide card with a divider.
  - Month by month sits at the bottom of the Overview as a closed row.
  - Old `/birdview` links open the Overview with the same period. Expense analysis keeps its address.
- **Budget:**
  - The summary reads Planned, Spent, then Left in plan.
  - Tracked categories show the field names once, in a header row, instead of on every line.
  - One **Amount or %** field per category: type `1,500` for a fixed amount or `12%` for a share of average monthly income. The rule in use shows as a small note under the category name.
  - "Reset carryover" appears only when there is carryover to reset.
- **Clearer names** (applied everywhere from the figures registry, with the old names kept as aliases):
  - Realized gain → **Gain from sales**
  - Change in unrealized gain → **Price change on what you hold**
  - New money in → **Money added**
  - Left in plan after bills → **Budget left to spend**
  - Deposits and holdings after sale (estimate) → **Investments if sold (estimate)**
- The Safe to spend parts take their names from the registry, so they can't drift.
- **Tests:** all 294 pass.
  - Nine older tests described screens, names and rules that have since changed; they now check the current design.
  - Migration `0032_suppressed_reevaluations.sql` is now in the changelog.
  - The Overview keeps the months you picked when a custom range is refused, as Birdview did.

### Month picker, no explainers, clearer investment gains · 2026-09-30
- **Picking a month:** every month box opens a small picker instead of being typed. Pick the year with ‹ › and then the month; months after this one are greyed out. This covers the period controls on every page (Monthly and Custom), the Transactions month filter and the carryover month.
- **No explanation toggles:** "How is this worked out?" is gone from every page. A figure's name has to explain itself; one that doesn't gets renamed.
- **Result is now "Net gain or loss"**, everywhere, including "Net gain or loss by asset class". It adds sales, price changes, and dividends and interest, so it isn't only unrealized gains.
- **Overview:**
  - A closed **Needs you** row sits at the top: it shows the count and the first item, and opens to the full list. When nothing is due it reads "Nothing needs you today".
  - The key note under it is what is safe to spend.
  - Net flow shows the savings rate on the right, behind a divider.
  - Month by month moves to Birdview.
- **Wide cards** (the ones that span the page) get a third gradient: the lead card's soft green on the left, fading to white on the right.

### Crisp pass: one look on every page, less text · 2026-09-30
- **One type scale:**
  - Text: 12 (labels), 13 (notes), 14 (body), 15 (key-note titles), 17 (card titles), 20 (sections) and 28 (page titles).
  - Numbers: 40 (lead card), 30 (other cards) and 24 (tiles).
  - Pages use 5–10 sizes instead of 10–14, and nothing is smaller than 12 px.
- **Currency once:** "EGP" appears small beside a card's main number. Row amounts show only the number.
- **One look for shared parts:**
  - Card shape, lead-card style and tile style.
  - One expander with a chevron on the right.
  - The same button sizes, and one primary action per header.
  - A settings icon in place of the ⚙ emoji.
  - "Back" sits with the actions on Settings.
- **Fixes:**
  - The Cash planning tabs show which one is open.
  - Transactions amounts are no longer cut off.
  - Dates and numbers no longer break across lines.
  - Tabs don't wrap on a phone.
- **Less text, nothing said twice:**
  - Formulas move inside "How is this worked out?".
  - Key notes only say what the page doesn't already show.
  - Repeated dates and "As of" labels are removed where the page header gives the period.
  - "Upcoming" labels are removed; only due payments are marked.
  - Empty tables show one line instead of headers.
  - Birdview, Expense analysis and Investments lose the sub-tabs that repeated the sidebar.
  - Birdview is two cards: What you own (or Net worth) with what it is made of, and If you sold today.
  - The Plan forecast table has 5 columns.
  - Investments hides the Horizon column until a horizon is set, and shows units without trailing zeros.
  - Transactions show the category name without its group (the full path shows on hover), trade descriptions without internal codes, and notes on one line.
- Word counts fell 20–64% per page (Birdview 403 → 145, Overview 383 → 269, Plan 319 → 201).

### Demo pass: visuals, key notes and a sample household · 2026-09-30
- **Key notes:** each main tab opens with up to three one-sentence notes: the answer, what changed, and what needs you. Each note has its number and one link.
  - Overview: safe to spend until payday, or what needs you; the change in what you own; how much of money in you kept.
  - Budget: the categories over plan, and what is left per remaining day.
  - Loans: the payoff date and the next payment.
  - The other tabs follow the same pattern.
- **Charts follow the app guideline** on every tab, with colours by meaning and bars from zero. Every trend has a "Show the numbers" table.
  - Overview: a month-by-month money in and out trend, "Where it went" spending bars, and a "What you hold" donut.
  - Birdview: a donut of what you own.
  - Expense analysis: category bars and a spending trend against the plan.
  - Budget: spent-of-plan meters, over plan first.
  - Investments: a portfolio trend that starts at the first holding, and an allocation donut.
  - Cash planning: the forecast line, the bills bars, a payment meter on each loan, and the emergency-fund meter.
- **Simpler screens:**
  - Lead cards use the soft gradient with dark text, so formulas on them can be read.
  - "Needs my attention" is now **Needs you** and appears only when something does.
  - The holdings table has 5 columns instead of 8, and "Update prices" is under More actions.
  - Recurring shows one bar card instead of three tiles.
  - Budget's summary cards fill one row.
- **Sample household:**
  - `python -m lightning --demo` opens Mohab's last three months (accounts, spending, investments, gold, money kept for Mom, a budget, the emergency fund, bills and a car loan) in a separate `data/demo.db` on port 8766.
  - It is rebuilt on every start and dated up to today.
  - An empty Lightning offers the same household from its welcome page.
- The tab-by-tab audit and what this pass changed are in `docs/UI_AUDIT.md`.

### Open findings fixed (Mohab runs) · 2026-09-30
- **#111:** a holding with no price yet is valued at what you paid (no gain yet) and flagged "valued at cost". The investment Result is no longer "Unavailable", and it now matches Result by asset class.
- **#129:** each derived figure shows its number, one formula line and one closed "How is this worked out?" toggle with the meanings and notes, the same on every tab. The Plan tab shows about 20% fewer words.
- **#130:** adding a recurring item whose date has passed asks once: "I paid it — start from the next one" (the default) or "Not paid yet — show it as due".
- **#131:** recurring amounts under 50 are no longer suggested.
- **#132:** closing a popup asks to discard only when something was changed.
- **#133:** paying a different amount says so, and Recurring offers "Use … from now on".
- **Import review:** answering one row fills the other rows with the same imported name (16 decisions instead of 40 for Mohab's statement).
- **Fees:** the fee field can always be typed: inside the amount by default, on top of it when "Fees are extra" is ticked.
- **Buying by amount:** leave Units blank to buy or sell a fund by amount; units come from the price per unit or the latest price.
- **New names:** a new name with no similar existing name is saved without an extra confirmation. Similar spellings still ask.

### Project overview: workflow, questions and gaps · 2026-09-30
- The Project Overview describes the three layers and the hurried-user principle. It adds Mohab's month as the reference workflow, the seven main questions each with follow-up questions (where each is answered, or the gap), and what is still missing compared with the best budgeting apps.
- Outdated decisions are corrected: loans and What you owe now count, and the emergency fund uses Average monthly income.
- The Mohab persona reports are kept in `docs/personas/`.

### Glossary by layer: ledger, plan, report · 2026-09-30
- The Glossary and Architecture describe three layers: the **ledger** (real money that actually moved), the **plan** (what-if: budgets, reserves, scheduled bills and loans, sale factors, the forecast; it moves no money) and the **report** (reads both, stores nothing).
- Every reported figure lists its layer (Ledger, Plan, or Ledger + Plan), how it is calculated, and the one function that computes it. The tables are generated from `lightning/core/figures.py` (`python -m lightning.core.figures`), and a test fails if the Glossary drifts or a listed function doesn't exist.
- The basic terms and entry-form fields are marked by layer too.
- Calculations moved out of screens into one function each: Savings rate (`CashFlow.savings_rate`), Change in what you own (`PositionService.change_in_what_you_own`), and Result with Change in unrealized gain (`investment_period`, `results_by_asset`). The Overview and Investments no longer compute Result separately.

### Fixes from the Mohab v7.1 re-run · 2026-09-30
- Skipping a loan payment no longer forgives it: the payment moves to the end of the loan ("Move to the end of the loan"), and skipped payments show on Loans and Recurring with an undo.
- Amounts and dates accept Arabic-Indic digits (٦٠٠, ٥/١٠) and the Arabic decimal and thousands marks.
- Opening a budget month that hasn't started returns to this month with an explanation instead of an error.
- Popup actions (mark paid, skip, stop, undo) always show a confirmation.
- Plan items with paid history show **Stop** instead of Delete, with matching confirmation text. Editing a loan says First due date and Number of payments.
- The Budget summary shows the loan payments included in Planned. The Plan tab's loans link reads "See your loans".

### Cash planning fixes from the Mohab re-run · 2026-09-30
- A loan adds its payments to the budget: while Personal › Loan payments (or the loan's category) has no budget rule, it is planned at the payments scheduled that month. It ends when the loan ends; setting an amount replaces it.
- Safe to spend and the cash forecast no longer count a due bill twice (once as a bill due, again as budget still to spend). Income that is due but not received stays in this month's forecast.
- "Left in plan this month" on the Plan tab is now **Left in plan after bills** (Left in plan − Bills inside the plan), so it no longer shares a name with the Budget's Left in plan.
- "Already in your transactions?" only suggests the same counterparty, the same category, or an amount within 10%.
- The pay and item forms list banks and wallets first, then brokerage, and no longer offer deposits.
- Account pages say **In this account · What you own · Held for others** instead of Total · Yours.

### One name and one calculation per figure · 2026-09-30
- Every reported figure now has one name, one meaning and one formula (`lightning/core/figures.py`, mirrored in the Glossary). Derived figures show their formula under them, e.g. "Free cash = Cash you own − Reserves − Bills due".
- One position calculation (`lightning/planning/position.py`) feeds the Overview, Birdview, Investments, Settings, Reserves and the cash forecast. The tabs no longer re-add balances their own way.
- One **Average monthly income** (`BudgetService.income_average`): the budget, emergency-fund coverage and the cash forecast use the same categories, months and manual override. Before, Reserves averaged salary over six months and the forecast averaged all income over three.
- Investments' after-sale estimate now applies the same sale factors as Birdview (95% when unset). It is now **Holdings after sale (estimate)**; before, it added holdings at full value. "Liquidation factor" is now **sale factor**.
- What you own adds up the same way everywhere: Cash you own + Deposits + Holdings value + Other you own. Birdview no longer groups deposits with investments.
- Renamed on screens (full list in the Glossary):
  - All accounts / Gross balances → In your accounts
  - Money from others → Held for others
  - Liquid cash / Owned liquid cash → Cash you own
  - Investment cash → Brokerage cash
  - Assigned reserves → Reserves
  - Estimated liquid investments → Deposits and holdings after sale (estimate)
  - Cashflow → Net flow
  - Invested capital → Cost
  - Period result / Investment result → Result
  - Cash added and withdrawn / New money added → New money in (net on every tab)
  - Budgeted / Current budget → Planned
  - Left → Left in plan
- Entry forms use the same field names:
  - Held for (was Whom, Owned by, Owner)
  - Amount (was Total paid, Each payment)
  - Units (was Pieces, Quantity, Units you hold)
  - Cost (was What you paid in total)
  - Account and Cash account (was Held in, Paid from, Paid into)
  - Counterparty (was Paid to, From)
  - As of (was Price date, Statement date)
  - Due date (was Next date)
  - Type (was Kind, Action)
  - Notes (was Details)
  - Fees (the checkbox is now "Fees are extra")

### Cash planning · 2026-09-30
- Reserves became **Cash planning** with four sub-tabs: **Plan** (safe to spend until the next income, what you owe, the next 30 days, a three-month cash forecast), **Recurring** (bills, subscriptions and income, with suggestions from payments that repeat in your history), **Loans** (loans and installment plans with progress and payoff date) and **Reserves** (the previous page). `/reserves` now opens `/plan/reserves`.
- Scheduled payments are marked paid automatically when exactly one posted transaction matches; otherwise pick the transaction, record the payment, or skip it. Voiding the transaction makes the payment due again.
- **What you owe** (bills due + loans still to pay) is shown as its own item: bills due come off free cash, and the Overview and Birdview show **Net worth** = what you own − what you owe. Forecasts never change either figure. The free-cash integrity check now includes bills due.
- Loan payments count as spending: a new loan defaults to **Personal › Loan payments** (migration `0035_loan_payments_category.sql`), so its payments show in the budget and cash flow; paying one also lowers loans still to pay, so net worth is unchanged.
- Migration `0034_cash_planning.sql` adds `planned_items` and `planned_payments`. Also recorded: `0033_reserve_account_matching.sql` links reserves to a payment account.

### Guideline 2.1 controls, month reports and report fixes · 2026-09-30
- Buttons follow the guideline: 48 px pills on pages and 36 px inside cards and rows; the date button and month arrows are 48 px circles. Textareas keep a 96 px minimum.
- Every date reads `yyyy-mm-dd` (hints, placeholders, period labels, the investments chart and Reserves use `yyyy-mm`). The period control is one `‹ yyyy-mm ›` stepper, and custom reports take a from/to month; Enter keeps the selected period.
- Screens use a true minus (−5,000.00); big figures shrink to their tile instead of breaking mid-number; the cash-flow figure no longer runs into the savings ring; the register's date and notes fields fit.
- CSV import: a merchant typed as new on several rows is created once; a row error no longer crashes the review (500), and the error view lists only the rows to fix.
- Emergency-fund coverage averages salary over the months that received it, instead of always dividing by six.
- "Returns by asset class" and "Biggest movers" include holdings sold out during the period.
- Revaluations replaced by the engine no longer appear in Deleted transactions and can't be restored into duplicates.
- "Add existing holding" on a physical item no longer asks for a cash account; the XIRR row waits for a year of holdings; a yearless date like 30/9 no longer jumps to last year; Birdview names deposits with investments ("Investments and deposits"); wording and favicon fixes.

### Uniform controls and date fields · 2026-09-29
- Buttons, text and number fields, dropdowns, month boxes and segmented toggles share one font, a 40 px height (30 px for small buttons), one border and an 8 px radius; checkboxes keep their natural 16 px size.
- Every date field is the same component: a typeable ISO box (`31/1`, `31/1/2026` or `2026-01-31`) with the same calendar button, including the register, CSV review, reconcile, data checks, custom periods, prices and physical items. Dates are normalised on submit as well as on blur.
- The register date column fits a full date; the settings carryover month uses the `yyyy-mm` box; the Birdview class popup keeps only the dialog's close button.

### Overview information flow · 2026-09-29
- Replaced the mixed card grid with six ordered, divided sections: wealth, available cash, period cash flow, attention, expenses and investments.
- Expanded cash and reserve amounts now reveal contributing balances inline; expense category links preserve dates, and investment results use the selected period.
- Removed the three-item attention limit and included spending above zero-value plans.

### Product workflow pass · 2026-09-28
- Reworked the main pages around focused questions, quiet number-led cards, consistent expandable category rows, and shared comparison/progress/time-series visuals. Added the application brand specification and live-styled component reference.
- Replaced Management navigation with a Settings hierarchy for counterparties, categories and data checks; added distinct sidebar icons and clearer account grouping.
- Corrected monthly Budget scope and exposed spending outside listed groups; preserved category scope in expense totals and trends; repaired saved CSV mapping, custody import and counterparty deletion workflows. Moved UI SQL behind services.
- Defined task ownership, follow-up paths, shared components, and visualization rules in `docs/PRODUCT_UX_ARCHITECTURE.md`.
- Recorded previously added migrations: `0032_suppressed_reevaluations.sql` records accounts whose monthly valuation checkpoint was skipped; `0029_birdview_class_factors.sql` stores liquidation factors by asset class; `0030_investment_targets_by_class.sql` links allocation targets to asset classes; `0031_dividend_asset_reference.sql` records the investment asset associated with dividends.
- Completed the prior migration log: `0024_reevaluation_ownership.sql` adds ownership-aware reevaluation entries; `0025_reserve_category_matching.sql` links reserves to categories; `0026_reserve_allocation_history.sql` records dated allocations; `0027_investment_planning.sql` adds allocation targets and asset planning metadata; `0028_budget_rules_and_resets.sql` adds income-percentage rules and carryover resets.

### UX review pass · 2026-09-28
- Main tabs share summary-first layouts and expandable calculation details; secondary account actions are grouped for review.
- Account CSV import includes a copyable AI preparation prompt, CSV template, and downloadable counterparty/category matching reference. Copy works in import popups with a manual fallback.
- Registers export their filtered posted cash activity for external analysis, with account, currency, type, linked-account and ownership context. Text fields are protected from spreadsheet formula interpretation.
- Added tab review notes and a prioritized comparison with YNAB, Monarch and Simplifi in `docs/UX_REVIEW.md` and `docs/BUDGET_APP_GAPS.md`.

### Changed
- Ledger lines can carry an optional owner. Linked legacy cash and investment custody entries migrate to owner-tagged lines, owner balances are checked across dated postings and edits, and brokerage buys must use cash from the brokerage account and the selected owner's balance.
- `0022_physical_items.sql` adds named physical items and dated item valuations; `0023_ledger_ownership.sql` adds ledger-line ownership.

### Fixed
- Counterparty management is now linked in the sidebar; canonical names and aliases can be edited, and delete removes unused records or archives records referenced by transaction history.
- Re-uploading a previously imported CSV creates a new review attempt; duplicate matches are warnings users may skip or explicitly approve, and voided/deleted transactions no longer count as active duplicates.
- Cross-account transfer matching now compares signs from the imported account's point of view, flagging the opposite statement leg as a likely duplicate.
- CSV uploads now pause at a prefilled field-mapping step before row review; review submissions scale Starlette's form-field limit to the staged rows, and Post rows is available above and below the list.
- Revaluation checkpoints are revisited after investment trades are voided, preserving fee details during trade edits, and record-level money values retain cents. Static asset versions are bumped with UI changes.
- Database migrations `0012_custody_transaction_links.sql`, `0013_reevaluation_ledger.sql`, `0014_preserve_category_codes.sql`, `0015_reevaluation_source_hash.sql`, `0016_reconciliation.sql`, `0017_cash_reserves.sql`, `0018_reserve_spending.sql`, `0019_recurring_reserves.sql`, `0020_reserve_counterparty.sql`, and `0021_budget_carryover.sql` are tracked here.
- Date fields now accept day/month input such as `31/1`, infer the current year, and normalize to ISO; CSV rows accept the same format.
- Account setup now records an optional starting balance as an opening entry on an explicit date, so it is not reported as income; the welcome steps explain this flow.
- The all-accounts register has a deleted-transactions page with direct restore actions, and changing a transaction's kind explains that the original reference remains in history.
- Investment quick entry now asks for Buy, Sell, or Dividend and takes positive units for both buys and sells.
- CSV review counts uncategorized rows before posting, and register labels clarify that the field is for who money went to or came from.

- Monthly investment checkpoints now detect changed historical trades and prices, void superseded system journals, and rebuild linked return entries; sale-day checkpoints value remaining units at the forced sale price.
- Counterparty default categories now resolve regardless of capitalization, and the all-accounts register reserves a separate, labeled action column for Add.
- Money entry rejects ambiguous decimal commas, exponent/underscore notation, and amounts too large for safe storage. New ledger money/base totals are limited to cents; app money displays round to whole currency units while entry fields retain cents.
- Invalid month, investment-price date, and category-parent URL values now receive safe validation instead of overflowing or raising a server error.
- Investment fee details stay hidden unless the user ticks “Fees are excluded from the total”; the select menu is removed.
- Account management is now directly reachable from the sidebar, including inactive accounts.

### Added
- Defined a consistent, typo-tolerant search workflow and identity-safety contract across Lightning in the three canonical docs, using an existing open-source matcher for candidate ranking.
- CSV imports are no longer capped by row count (the 5 MB file-size limit remains).
- Documented the native Windows readiness milestone and current launcher, time-zone, and data-location gaps in the three canonical docs; Windows support remains unverified.
- CSV import now supports either one signed amount column or separate inflow/outflow columns; mapped statement rows merge into a single signed Amount before review.
- Categories can be selected individually or in bulk for activate/archive/delete actions; deleting a category with history or references archives it instead.
- Consolidated the budget workflow, UI audit/tasks, user-question map, and milestone roadmap into the three canonical docs; added last-updated, document-revision, and app-version metadata to each.
- Split the UI workflow audit into ordered, bounded implementation tasks for Luna, with acceptance criteria and a separate check for the conflicting asset breakdowns.
- Budget now starts with a history-based plan preview or one broad limit, then opens on monthly status with attention items, free-cash context, transaction feedback, and optional spending-limit carryover.
- Added read-only integrity checks for gross versus owned/custody balances, account-level ownership splits, expense and budget totals, reserves, and the net-worth bridge; missing valuations are shown as incomplete.
- Corrected budget actuals so income categories no longer reduce reported money-out totals.
- Audited the customer workflow and UI hierarchy across Overview, Birdview, Accounts, Budget, Reserves, and import; documented which controls to remove, relocate, or keep and a phased UI redesign.
- Defined the budget customer-flow milestone: one-action plan setup, everyday status and transaction feedback, optional spending-limit carryover, and a month review; cash reserves remain separate from budget limits.
- Documented the user questions Lightning should answer, the follow-up drilldowns for each, and the next Birdview history/performance milestone, including the role and limits of XIRR.
- Birdview replaces Investments in the main navigation with current owned assets, a configurable investment liquidation factor, cash reserves/free cash, income and spending timelines, and capital/return breakdowns by investment type and holding.
- Cash reserves for emergency funds and planned projects, with recurring due dates, optional Counterparty matching, payment links, and free-cash calculations; custody transactions never auto-link.
- Statement reconciliation lets users mark cash transactions cleared and compare the cleared balance with a statement amount.
- Expense transactions can be split across categories, and refunds reduce spending in the original expense category instead of inflating income.
- Confirmed Counterparty aliases are manageable from the Counterparties page, capped at 10 per Counterparty, and offered in register and CSV search.
- CSV review can remember a confirmed category for future transactions from that Counterparty.
- Activity-ledger categories organized as Personal, Work, or Investment, with up to one user-defined detail level below each broad activity category; money direction no longer determines the category tree.
- Transaction multi-select and right-click delete actions, with audit-preserving deletion and restore.
- "Money from others" custody entries tied to an account and owner; outstanding balances are excluded from net worth and reconciled in the net-worth bridge.
- CSV import is available for all account types. Statement rows can be edited inline, and valid incomplete rows can post with safe uncategorized/optional-counterparty handling.
- Database migration `0011_money_from_others.sql` adds custody tracking and converts existing legacy receivable accounts to Other Assets.
- Database migration `0010_category_families.sql` stores category families and migrates income activities into the Personal/Work/Investment tree.
- Canonical Counterparty records with normalized names, confirmed aliases, reusable default categories, and ranked approximate suggestions that never auto-merge. Bank import staging retains original source rows for review.
- Database migration `0008_counterparties.sql` adds canonical counterparties, aliases, transaction links, and bank-import batch/row staging.
- Database migration `0009_import_column_maps.sql` remembers a confirmed CSV header/sign mapping per bank account.
- Best-effort investment quote refresh runs when Lightning starts, saving supported Yahoo Finance quotes to
  price history so portfolio values and unrealized gains recalculate from the newest quote. Stocks and funds
  use their ticker with Yahoo's CA suffix; unsupported symbols keep their prior saved valuation.
- Budget planning can use a rolling average of the previous 3 or 6 complete months of spending for a category
  or group. The method repeats until changed; this-month-only overrides still work. Existing manual budgets remain.
- Database migration `0007_budget_averages.sql` stores the selected calculation method.

### Changed
- Account opening dates no longer restrict historical transaction entry, editing, or restoration; valid past-dated activity can be added at any time.
- Removed "Money owed to me"/receivable accounts from the active account model and choices; the app has no receivables workflow.
- CSV import review no longer requires a separate Counterparties resolution screen; corrections are made on the transaction rows.
- Investment-account names now appear in the left sidebar without internal account codes.
- Account codes no longer appear beneath account names in the sidebar or account register heading, or beside
  account names in the account list and account edit heading. Account names are sufficient in these views.
- Roadmap places searchable Egyptian investment catalogue before daily wealth history and return breakdowns.

---

## [0.3.0] — 2026-09-25 — M3 Investments, new register

### Added — M3 Investments (manual)
- **Investments** you can hold: stocks, funds (equity, money market, gold, other), gold and other — created with a
  kind and symbol; codes `STK:COMI`, `FND:AZ-GOLD`, `GLD:21K`. Units follow the kind (shares whole, fund units
  4 decimals, gold grams 3 decimals, gold karat → purity).
- **Buy, Sell, Dividend** and **"Holding I already own"** (units + what you paid in total, for existing positions).
  Buy/sell use the broker's own cash (THNDR) or another account (e.g. wallet pays for gold at home).
- **Positions** from the ledger, average cost (as THNDR shows): cost basis incl. buy fees, realized gain on sells
  (after sell fees), unrealized gain, dividends per holding, total return; allocation by asset class and by
  exposure (a gold fund counts as gold).
- **Prices**: "Update prices" page (one date, a box per investment). Valuation uses the newest of a typed price
  and the last buy/sell price (a typed price wins on the same day); holdings entered as already owned are
  valued at cost until priced, marked "at cost". Price changes flow into the net-worth bridge as revaluation.
- **Investments page** (`/investments`): value, invested, unrealized, total return, holdings table, allocation,
  sold-out positions. Account pages of brokerage / gold-at-home accounts show a Holdings strip and
  Cash · Holdings · Total, with Buy / Sell / Dividend buttons.
- "Physical asset (e.g. gold at home)" account type is now offered.
- New `investments` module (builds lines, calls `TransactionService.post()`); `AssetService.create_investment`,
  `set_price(s)`; `TransactionService.post()/repost()` for documents built by other modules.
- Docs: `PROJECT_OVERVIEW.md` rewritten for 0.3.0; glossary and architecture notes updated.

### Changed — the register (owner feedback)
- Its own design (not Actual's): a quick-add row, coloured edge per kind (in, out, transfer, investment, opening),
  a date shown once per day.
- **One Amount column**: positive = money in, negative = money out (replaces Payment / Deposit).
- **"To"** replaces "Payee". Typing or picking one of your accounts in To makes the row a **transfer** automatically
  (the Category box is not needed and is disabled).
- **Category is a type-and-pick box** (a list of matches while you type), not a dropdown. It accepts the full name
  ("Personal › Food & Groceries"), the short name, a unique part of it, or the code; ambiguous names ask "Which one?".
- The account register lists **cash only**; investment lines appear in holdings. Buys show as money out with
  "Buy 150 × STK:COMI @ 92.4 + fee 45.00".
- Sidebar groups accounts by kind: Cash & bank · Deposits · Investments · Other (values include holdings).

### Fixed / rules
- A holding can never go below zero units at any date — enforced on sell, edit, void and restore.
- An account's cash opening balance and each holding's starting amount are separate (`OPN` per cash or per holding).
- Holding values are kept at full precision (rounded only on screen), so net worth = cash + Σ units × price exactly.

### Decisions
- 2026-09-25 — Average cost; buy fees go into cost; sell fees reduce what you receive (owner, THNDR style).
- 2026-09-25 — Buys and sells are conversions: their lines net to zero at cost/proceeds, so gains appear as
  revaluation in the net-worth bridge and as realized/unrealized in the portfolio view.
- 2026-09-25 — Register: one signed amount, "To" (an account there = transfer), typed categories (owner).
- Dividends link to their investment through the cash line's memo (the investment's code).

---

## [0.2.0] — 2026-09-25 — Register, budgeting, simplification

### Added
- GitHub-ready: `.gitattributes` (keeps `run.bat` in Windows line endings), README section on cloning to
  another computer; `data/` stays out of Git so finances are never uploaded.
- `docs/PROJECT_OVERVIEW.md` — detailed hand-off brief: purpose, terminology, architecture, data model,
  ledger rules, service APIs, UI routes, roadmap, decisions log and rules for future changes.
- **Account register (Actual-style):** each account page is now a register with an entry row on top —
  Date · Payee · Category · Notes · Payment · Deposit — press Enter to save and the row is ready for the next one.
  Transfers are picked from the same list ("Transfer ↔ another account"). Clicking a row opens it.
- Payee memory: typing a payee used before fills in the category used with it last time.
- `TransactionService.record_in_account()` turns one register row into money out, money in or a transfer.
- **Actual-style layout:** the sidebar lists every account with its balance, grouped like the dashboard
  (Liquid Cash, Deposits…), with an "All accounts" total and "+ Add account".
- **All accounts register** (`/transactions`): every account in one register, one row per account touched,
  with an Account column; new rows pick their account in the entry row.
- **Edit in place:** click a row and it becomes editable — Save, Cancel (Esc), Void, Details & history.
  If an edit changes the kind (e.g. a transfer becomes money out) the old one is voided and a new one recorded,
  so a ref's prefix always tells the truth. `TransactionService.update_in_account()`.
- Register toolbar: "+ Add New", search (payee, notes, category, amount, ref) and a month filter.
- **Budgeting** (new `budgeting` module, `/budget` page, "Budget" in the sidebar):
  - budget vs actual per month for money-out categories, in two sections: **Personal** and **Work**;
  - budgets on a group (Personal 20,000 — the ceiling) or on categories (Food 6,000 — part of it);
    a group without its own amount shows the total of its categories; a warning when categories exceed their group;
  - **repeat until changed**: an amount applies from its month onward; "Apply to this month only" for one-offs;
  - Budgeted · Spent · Remaining · Money in tiles, per-line progress bars, over-budget in red,
    "spent without a budget", and Spent links straight to those transactions;
  - Overview shows a Budget card (Personal / Work progress).

### Changed
- **Savings = bank account.** One type "Bank account (current or savings)". "Deposit" now means a
  certificate / time deposit (CD), reported under Deposits › CDs / Time Deposits.
- **Where an account appears on the dashboard now follows its type.** The "Report cash in this account as"
  picker is gone; the form shows the result in words (e.g. "Liquid Cash › Bank Balance").
- **Screens show plain names instead of codes** for categories and asset classes
  ("Personal › Food & Groceries", "Liquid Cash › Physical Cash"). Account codes still appear with names.
  Codes remain in search, the ledger detail and the database views.
- **Categories page redesigned:** one block per group, categories as clickable chips, one "+ Add" per group;
  codes moved into an optional field on the edit form; system categories hidden.
- Dashboard renamed **Overview**; tiles: Net worth · Money in · Money out · Left over.
- Register columns follow Actual: Date · Payee · Notes · Category · Payment · Deposit · Balance.
- Generated codes keep whole words ("Cash at hand" → `CASH-AT-HAND-CSH-EGP`, not `CASH-AT-HA-…`).
  Existing codes are not changed — rename them from the account's edit page if you like.
- Opening balances cannot be negative.

### Fixed
- An account's start date can no longer be moved after its first transaction (the review's gap #1).
- **No more future dates:** transactions and account start dates cannot be after today, so every balance has
  one meaning ("today"); the "including entries dated after today" note is gone. Scheduled payments will come
  as recurring transactions (M7).

### Removed (architecture simplification)
- **Stored search text and the full-text index.** Search now reads transactions, accounts and categories
  directly (ref, date, payee, description, notes, account, category, amount), so nothing derived is stored and
  nothing can go stale. This also removes the search rebuild on renames and the whole category workflow.
- `ledger_entries.claim_id` and `transactions.import_batch_id` (their milestones, M5 and M7, will add them),
  the unused `DRAFT` status, and the empty `integrations/` placeholders.

### Removed
- The separate Money out / Money in / Move money form pages and the old transactions list — the register replaces them.
- **Liabilities.** Credit card, loan / installments and "money held for others" account types, the
  Liabilities asset classes, and all "amount owed" logic. Lightning tracks what you own.
- The "Savings / Interest-bearing" asset class (savings accounts are bank accounts).

### Decisions
- 2026-09-25 — No liabilities (owner). Card or loan payments are recorded as money out from the paying account.
- 2026-09-25 — Savings and current accounts are the same type (owner).
- 2026-09-25 — Codes are for data; screens use names, except account codes which always travel with the name (owner).
- 2026-09-25 — Account pages work like Actual Budget: one ledger underneath, filtered per account (owner).
- 2026-09-25 — Screen structure follows Actual: accounts sidebar + register (owner). Schedules, import and the
  cleared tick come with their milestones (M7 recurring, M7 import, M2 reconciliation), not as placeholders.
- 2026-09-25 — Budgeting (owner): budget vs actual (no rollover), budgets at either level, repeat until changed,
  Personal and Work as separate sections. Actuals always come from the ledger; only budget amounts are stored.
- 2026-09-25 — Architecture review simplifications applied (owner). Kept on purpose: price and asset fields
  (M3 investments is next) and `sort_order` (keeps asset classes in a meaningful order, e.g. Liquid Cash first).

### Schema
- `0006_simplify.sql` — drops the full-text index, its triggers and `transactions.search_text`,
  `transactions.import_batch_id`, `ledger_entries.claim_id`. No financial data changes.
- `0005_budgets.sql` — `budgets` (category × month × amount, repeating or this-month-only) and a readable `v_budgets` view.
- `0004_bank_and_no_liabilities.sql` — savings accounts become BANK; every account's reporting group is reset
  from its type; unused Liabilities and Savings asset classes removed. Stops without changing anything if a
  credit-card, loan or held-for-others account exists.

---

## [0.1.0] — 2026-09-25 — M0 Foundation + M1 Cash & bank basics

### Added — M0 Foundation
- Project skeleton as a modular monolith: `core`, `database`, `assets`, `categories`, `accounts`,
  `transactions`, `reporting`, `workflows`, `integrations`, `ui`.
- Exact money handling: `Decimal` everywhere; stored as integers ×1,000,000 (`_e6` columns).
- ISO dates (`yyyy-mm-dd`) enforced on input, storage and display.
- Readable identities: account codes (`CIB-CUR-EGP`), asset codes (`CASH:EGP`), dotted category and
  asset-class codes (`EXP.WORK.SOFTWARE`), and fixed document refs (`OUT-2026-09-25-003`, lines `/1`).
- Posting engine (`core/ledger.py`): internal lines must net to zero; money in/out needs a category.
- Plain-SQL migrations with a `schema_migrations` table; optional FTS5 search migration with LIKE fallback.
- Seed data: asset-class tree, cash assets (EGP, USD, EUR, GBP, SAR, AED), category tree.
- Audit log for every edit, void and restore.
- Automatic backup on start (`data/backups/lightning_yyyy-mm-dd_HHMM.db`, newest 30 kept) and a
  "Back up now" button.
- Architecture rules enforced by `import-linter` (4 contracts) and tests.
- `CHANGELOG.md` (this file) — every change is logged here; a test checks each version and migration is listed.

### Added — M1 Cash & bank basics
- Accounts: cash wallet, bank, savings/deposit, brokerage, money owed to me, credit card, loan,
  money held for others. Codes suggested automatically; last 4 digits only.
- Opening balances recorded as `OPN` transactions; liabilities entered as "amount owed".
- Money in, money out and transfers, with edit (ref never changes), void and restore.
- Credit cards and loans work as balances: spending on a card is money out; paying it is a transfer.
- Search across ref, date, accounts, categories, amount, payee, description and notes (Arabic works).
- Reports: net worth (total, by account, by asset class), net-worth bridge, cash flow
  (household vs investment income, personal vs work spending), spending by category, 6-month trend,
  account statement with running balance.
- HTML app (FastAPI + Jinja2, no build step, works offline): dashboard, accounts, transactions,
  categories, settings. Light and dark mode, phone-friendly.
- Windows launcher `run.bat` (macOS/Linux `run.sh`).
- 100+ automated tests, including a randomized 300-step ledger test for the net-worth equation.

### Decisions
- Accounts (where) and financial assets (what) are separate; cash is classified by the account
  holding it (`cash_class`), investments by the asset.
- One ledger: transactions (documents) → ledger entries (lines). Every balance and report is derived.
- Net-worth equation: closing = opening + money in − money out + revaluation + new balances added.
- No `opening_balance` field on accounts and no `include_in_net_worth` flag (it would break the equation;
  pass-through money belongs in a "Money held for others" account instead).
- Edits happen in place with an audit trail, not by reversal entries.
- Plain `sqlite3` + SQL files instead of SQLAlchemy/Alembic.
- M1 is EGP-only; other currencies wait for FX rates in M4.
- Balances on screen are "as of today"; future-dated entries are shown separately.
- Edit and void moved from M2 into M1 (the app is not usable without them).

### Schema
- `0001_initial.sql` — settings, asset_classes, financial_assets, accounts, categories, transactions,
  ledger_entries, price_history, fx_rates, audit_log.
- `0002_search.sql` — FTS5 full-text index on transactions (optional).
- `0003_readable_views.sql` — `v_ledger`, `v_balances` for browsing the file.
