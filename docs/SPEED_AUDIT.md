# Speed audit: the PC app (2026-10-03 · Claude)

**Question:** the PC app feels slow because it recalculates after every press. Would a caching system fix it?

**Short answer:** yes, but the kind of cache matters. Most of the time goes on recalculating **the same figures several times within one page**: the Overview builds the full position 14 times, and the Budget's All-time view runs the same month's spending query thousands of times. A cache that lives **for one request only** removes that waste with no risk of stale numbers, and it is the first step. A cache that keeps figures **between** clicks comes second, invalidated on every database write. Two non-cache problems add to this: an encryption setting that makes ledger reads about 3× slower, and pages that load a whole account history to show 50 rows.

Nothing here was packaged; every figure comes from the source on `main` (`42d64b4`).

## How it was measured

- **Data:** Omar's 2026 sample (`load_omar_2026`, 319 transactions), plus two larger copies with 2 and 5 extra years of ordinary activity (salary, 20 card payments and 10 cash payments a month): 1,087 and 2,239 transactions. A real user with a few years of history is closer to the larger copies.
- **Server time:** each page requested three times through the FastAPI app, median kept, with an SQL statement count. Plain SQLite, and SQLCipher keyed exactly as `Database.conn` keys it (the PC profile path).
- **Window time:** headless Chromium (the engine inside WebView2), with the page CPU throttled 4× to stand in for an ordinary PC.
- **Machine:** a 4-vCPU 2.1 GHz cloud container. Python was not throttled, so treat these server times as a floor. An ordinary laptop is likely to be the same or slower, and Windows adds Defender and OneDrive file overhead on top.
- **Check:** the request-cache prototype (finding 1) produced byte-identical HTML on every page tested.

## Results

Server time per page (ms). "Enc." is the encrypted profile as the PC app opens it.

| Page | 319 txns | 1,087 txns | 2,239 txns | 2,239 txns, enc. |
|---|---:|---:|---:|---:|
| Overview | 204 | 363 | 571 | **913** |
| Budget, month | 61 | 85 | 166 | 187 |
| Budget, All time | 446 | 1,514 | **4,488** | **6,337** |
| Account register | 62 | 81 | 170 | 476 |
| All transactions | 58 | 110 | 304 | 700 |
| Investments | 87 | 202 | 394 | 442 |
| Expense analysis, All time | 107 | 221 | 539 | 942 |
| Cash planning | 71 | 111 | 167 | 354 |

Run-to-run variation is about ±15%.

On top of the server time, the window spends about 250–400 ms on each page (at 4× CPU throttle), so the encrypted Overview takes about 1.2–1.3 s from click to ready. **The Budget remembers the period you chose:** once you pick All time, every later visit to Budget costs about 6 seconds. That matches the 4–5 second tab delay in user feedback batch 001 (ticket theme 1).

Time grows in step with the size of the ledger on every page except Settings, so the app slows down month after month of normal use.

## Findings, biggest first

### 1. The same figures are recalculated many times on one page

- **Overview:** `PositionService.at()` runs 14 times per page: the cards, change in net worth, the 12-month Net worth trend (`visuals.net_worth_trend`), the forecast and the period stats. `ReportingService.holdings()`, a full ledger scan, runs 94 times per page because `owned_liquid_cash` → `owned_account_value` → `account_value` re-scans the whole ledger once per account, and `custody_value_by_account` repeats that again per account. About 5,200 SQL statements per Overview.
- **Budget, All time:** `BudgetService._rolling_average` is called about 630 times per page, each time with a new `{}` cache. Each call re-runs `_owned_spending` six times (two loops over the same 3 months), and every `_owned_spending` rebuilds the whole category tree (`_investment_ids`). That makes 3,860 month-spending queries and 4,076 category-tree builds for one page, about 9,950 SQL statements.
- **Investments:** `build_investment_report` runs 14 times per page, mostly for the six-month sparkline (`_portfolio_value_spark`), and each run reads every investment line again.
- **Expense analysis:** `CategoryService.get` runs about 14,000 times per All-time page, one point query per ledger row.

**Prototype result.** A per-request memo on about a dozen read functions (`holdings`, `net_worth`, `custody_value_by_account`, `money_out_by_category`, `PositionService.at`/`class_values`/`owned_holdings`, `CategoryService.tree`, asset and account lists), cleared at the start of each request, gave these results with identical HTML:

| Page (2,239 txns, plain) | Before | With request memo |
|---|---:|---:|
| Overview | 523 ms | 194 ms |
| Budget, All time | 4,546 ms | **258 ms** |
| Budget, month | 126 ms | 47 ms |
| Cash planning | 156 ms | 66 ms |
| Investments / Expense analysis | unchanged | needs `build_investment_report` and `CategoryService.get` memoized as well |

### 2. Encryption setting: `cipher_memory_security = ON`

`Database.conn` turns on SQLCipher's memory security, which wipes every freed allocation. Once it is on, it stays on for the whole process. With nothing else changed, a full-ledger `GROUP BY` takes **555 µs instead of 173 µs** (3.2×), and the encrypted Overview takes about 915 ms instead of 480 ms. Keying and decryption themselves cost almost nothing here: a SQLCipher database without this setting ran as fast as plain SQLite.

It is a security hardening option, so whether to switch it off is the owner's decision. The architecture already says key wiping is best effort and that nothing protects an unlocked PC from malware. Fixing finding 1 also shrinks this cost, because far fewer queries are run.

### 3. Pages load all history to show one page of rows

The account register and All transactions load and summarise **every** matching transaction (1,501 for one account in the large copy), then show 50. `TransactionService.summarize` looks up the account, category and asset for each row one at a time: about 6,800 SQL statements for one register page. That page also reloads after every save in the register. The save itself takes 15 ms (1 commit); the reload takes 160 ms plain and about 540 ms encrypted.

### 4. Smaller items

- **Static files are never cached in the PC app.** `runtime/http.py` sets `Cache-Control: no-store` on every response, including `/static/`, so each click re-fetches about 0.9 MB: `style.css` (274 KB), `app.js` (103 KB), fonts, and a **513 KB `lightning-logo.png`** drawn at 22 px. Measured gain from caching them: only 20–40 ms per page, because Chromium's parse time dominates, not transfer. Worth doing (versioned URLs already exist), but it is not the fix.
- **Legacy browser mode loads Google Fonts in a way that blocks the page.** The stylesheet in `base.html` delays every page by about 240 ms online and stalls much longer offline. `style.css` names Bricolage Grotesque and Manrope only as fallbacks. The PC profile mode already skips it.
- **One slow page blocks everything.** Routes are `async def` but do synchronous database work, so a 6-second Budget holds up the 15-second health check and any other tab. This matters less once pages are fast.
- **Saves are not the problem.** One commit per save; GET pages open only empty write transactions (from `match_payments`), which do not touch disk. The live database uses the rollback journal (`DELETE`, synchronous `FULL`). Each commit creates and deletes a journal file in Documents\Lightning, which Defender and OneDrive both watch. WAL mode would avoid that, but it needs a check against the backup and staging code first.

## Recommended plan

1. **Request-scoped cache (no stale-data risk).** One small context-local memo per request in `lightning/core`, cleared by middleware at the start of every request, applied to the pure read functions above plus `build_investment_report` and `CategoryService.get`. Inside a write (`db.transaction()` depth > 0) the memo is bypassed, so a save never reads its own stale figures. Expected: Overview about 2.5×, Budget All time about 17×.
2. **Fix the two worst algorithms directly.** In `_rolling_average`, compute each month's spending once and share one cache across the page, and build the category tree once per call instead of per month. In `owned_liquid_cash` and `custody_value_by_account`, compute holdings once and group them by account instead of re-scanning per account.
3. **Owner decision:** turn `cipher_memory_security` off (expect about 2× on encrypted pages), or keep it and rely on 1–2.
4. **Register and All transactions:** batch the account, category and asset lookups for the page (one query each), and summarise only the 50 rows shown, with the running balance taken from SQL.
5. **Cross-click cache (only if still needed after 1–4).** Key cached figures by a database-wide write counter. `Database` can bump it on every `COMMIT` (the app has one connection per profile), so any save, import, price update or profile switch drops everything at once; also key by `today()`, because figures change at midnight. This is the "caching system" that was suggested, made safe; with 1–4 done it should rarely be needed.
6. **Static and small items:** a long `Cache-Control` for versioned `/static/` files, a 64 px logo, and drop the render-blocking Google Fonts link in browser mode.
7. **Guard it:** a speed test that builds the 2,239-transaction ledger and fails if a main tab exceeds a server-time budget (the existing goal is 500 ms per tab), so the slowdown does not return as the ledger grows.

Steps 1, 2 and 4 change no figures and keep every calculation in the Python services, so Omar's test and the full suite should stay green as they are.
