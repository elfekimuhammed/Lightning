# Market data: one price file, collected in the cloud

Status: proposal, 2026-10-05 (Claude, owner's request). Phase 1 is being built; see *Phases*. When a phase is built, what holds moves into Architecture and this file shrinks.

| Section | Read it when |
|---|---|
| The problem | You want to know why prices change |
| The design in one picture | You need the whole idea in a minute |
| The market file | You read or write the file, or match instruments |
| Sources, the whitelist | You add, fix or replace a source |
| Checks before anything is published | A price looks wrong, or a source fails |
| Financial assets in the app | You change how an asset is named, classed or edited |
| How the app gets prices | You work on Update prices, first run or a statement import |
| Five months of statements: the history story | You work on back-filling prices |
| Keeping it alive | Something broke, or you plan maintenance |
| Rights and limits | Before publishing the file, or adding a source |
| Phases | You pick up the next piece |

## The problem

Today each copy of Lightning asks Yahoo's undocumented chart feed for each Egyptian stock, one request per stock, at start-up (`lightning/assets/market_data.py`). That means:

- **One source, no fallback.** When Yahoo changes or blocks, every user's prices stop at once, and each user has to wait for a new app version.
- **No funds, no exchange rates, no US stocks.** Fund NAVs, CBE rates and gold are typed by hand.
- **History is fetched live, month by month.** A user who imports five months of statements waits on dozens of requests, and a missed one leaves a hole.
- **Privacy.** Asking Yahoo for exactly the tickers you hold tells Yahoo what you hold.

## The design in one picture

```
 sources (whitelist)          the cloud, once a day                Lightning-downloads          each user's app
 ───────────────────          ─────────────────────                ───────────────────          ───────────────
 TradingView, Mubasher,  ─▶  collector: adapters, fallbacks,  ─▶  market/ folder:          ─▶  bundled copy in the ZIP,
 CBE, banks, Yahoo, ...      checks, cross-checks, health          manifest + instruments       then "Update prices"
                             report; never overwrites good         + monthly and daily          downloads only the files
                             data with bad                         price files                  that changed
```

1. **The app never scrapes.** A collector runs once a day in GitHub Actions, after the Cairo close. When a source breaks, it breaks once, in one place; we fix one adapter and every user gets the fix with the next file, no new app version.
2. **One file for everything.** Every EGX stock, Egyptian fund, CBE currency, gold karat and US stock or ETF, each with its category and ISO identifiers, in one versioned set of files.
3. **History comes with the app.** Each release ships the latest file, so first run and back-filling work offline and at once.
4. **Updating is one button and a few kilobytes.** The app compares checksums and downloads only what changed, usually today's closes.
5. **Nothing depends on the network.** Without it, the app keeps the last file; a user can import a file by hand; typing a price always works and always wins.

## The market file

A folder, published as files in `Lightning-downloads/market/` and zipped into each release as `market.zip`:

```
market/
  manifest.json          schema, version, created_at, one entry per file: path, sha256, rows, first and last date
  instruments.csv        every instrument, its category and its aliases
  monthly/2015.csv ...   one closing price per instrument per month-end, every year we have
  daily/2026-09.csv ...  every daily close, one file per month; the app keeps the last 13 months
  health.json            per source: last good run, failures in a row, rows read, last error
```

**Names follow ISO standards** wherever one exists (owner's request): currencies ISO 4217 (`USD`, `EGP`, and `XAU` for gold), securities ISO 6166 (ISIN), venues ISO 10383 (MIC: `XCAI` for the Egyptian Exchange, `XNAS`, `XNYS`), countries ISO 3166 (`EG`, `US`), dates ISO 8601.

**instruments.csv** — `key,isin,mic,ticker,name,name_ar,category,country,currency,unit,aliases,sources,status,first_date,last_date`

- `key` never changes once published, so it is built from parts that do not move: a listed security is its ISO 3166 country and ticker (`EG:COMI`, `US:AAPL`) because a company can change venue; a fund without a ticker is `EG:FUND:4104` (its Mubasher id); a currency is its ISO 4217 pair, the price of one unit in pounds (`USD/EGP`); gold is `XAU:21K`, EGP per gram of 21K; an index is `EG:EGX30`.
- `isin` (ISO 6166) is filled whenever a source gives it, and it is the first thing the app matches a holding on; `mic` (ISO 10383) is the venue today; `currency` (ISO 4217) is what `close` is in; `country` is ISO 3166 alpha-2.
- `category` is a Lightning asset class: `STOCK`, `FUND.EQUITY`, `FUND.FIXED_INCOME`, `FUND.MONEY_MARKET`, `FUND.GOLD`, `FUND.OTHER`, `CURRENCY`, `GOLD`, `INDEX`. The pickers group by it. (ISO 10962 CFI codes are assigned per instrument by numbering agencies; we add them only when a source publishes them, never by guessing.)
- `aliases` lists old tickers and other names (`STK:COMI`, a fund's Thndr ticker and name), so a renamed or re-listed instrument still matches a user's holding. `sources` lists each source's own id (`mubasher=4104`).
- `status` is `active`, `inactive` (no new price for 30 days) or `delisted`.

**Price files** — `date,key,close`, with `close` in the instrument's currency, six decimals at most, sorted by key and date. Month-end closes are the last close on or before the month's last day. A fund that publishes weekly simply has fewer rows.

**Size.** About 300 EGX stocks, 200 funds, 20 currencies, 4 gold karats and, to start, the S&P 500, Nasdaq-100 and 100 largest ETFs (about 700). Month-end history since 2015 is about 160,000 rows; 13 months of daily closes about 330,000. Zipped, a few megabytes in the release and about 25 KB for a day's update.

**Why plain CSV in a folder:** git keeps every version, so our history survives even if a source drops its own; a day's change is a small diff; the app needs no new library; a person can open it.

## Sources, the whitelist

Every source has an adapter in `tools/market/sources/`, a priority per market, a polite pace (one request every few seconds, a User-Agent that names Lightning), and a recorded sample of its answer for tests. **Verified** means the format is confirmed by working public code or by our own run; the rest are to confirm on the first collector run (this container's network blocks these hosts).

| Market | First | Fallback | Cross-check | History | Notes |
|---|---|---|---|---|---|
| EGX stocks, latest close | TradingView screener: one POST returns every EGX stock (verified, open-source trackers use it) | Mubasher stock list | Yahoo `.CA` chart | Yahoo chart `range=max`, per stock, once; then our own daily files | EGX moves are limited per day, so a jump past the limit needs a second source |
| Egyptian funds, NAV | Mubasher `api/1/funds?country=eg` (verified) | each manager's own page (Banque Misr, CI, AZ, ...) | Starta, EGX Bot fund pages | Mubasher `priceChartFund_{id}.csv`, the whole history in one file per fund (verified) | Mubasher's robots.txt asks bots to keep off `/api/` (see *Rights*); funds split units, so a 1.9× move is a split, not a price |
| Exchange rates | CBE's official rates page | NBE and Banque Misr rate pages | a market-rate feed, labelled "not official" | CBE historical rates page; then our own daily files | We publish the CBE mid (buy and sell averaged); devaluation days are real, so CBE wins when it is the source |
| US stocks and ETFs | TradingView screener, `america` (verified) | Yahoo chart | Stooq (free key, kept as a GitHub secret) | Yahoo chart `range=max`, once | Prices in USD; valuing them in EGP needs multi-currency (Upcoming projects #15, #16) |
| Gold, EGP per gram | an Egyptian gold-price feed (for example DahabPulse's JSON) | a second gold site | world gold price × CBE USD × karat ÷ 24, labelled "estimate" | the gold site's history | Local retail prices differ from the world price; we say which one we show |
| Indices | TradingView screener | Yahoo | — | Yahoo | For comparisons only (Upcoming projects #1) |

Adding a source is one adapter, one sample, one line of priority, and a test. Removing one is a line.

## Checks before anything is published

A run never publishes a price that fails these; it keeps the last good one and says so in `health.json`.

- **Shape and size:** the answer parses, and has at least as many rows as expected (150 EGX stocks, 100 funds, USD and EUR from CBE). A page that returns HTML instead of data fails.
- **Sense:** closes above zero, dates not in the future, a "latest" price not older than its market's last trading day by more than a week.
- **Jumps:** a move past the market's limit (EGX stocks 20%, funds 15% unless it is a clean split, currencies 15%) needs a second source that agrees, except a CBE rate, which is the official number.
- **Agreement:** when two sources give the same instrument and day, they must agree within 1% (stocks), 0.5% (funds, currencies). If not, the higher-priority source is used only if it also passes the jump check; the disagreement is reported.
- **History is append-only.** A published price is corrected only by a reviewed line in `corrections.csv`, never by a run.

## Financial assets in the app

- **The exchange is a property of the asset, not a new class** (owner's request to show the stock exchange). Each asset gets `mic` (ISO 10383) and `country` (ISO 3166); screens show the exchange's common name: `XCAI` is **EGX**, `XNAS` Nasdaq, `XNYS` NYSE, `ARCX` NYSE Arca. A stock reads "COMI · EGX". Classes stay what the asset is (Stocks, Equity fund, Gold, ...), so allocation and every report keep working, and Investments can split Stocks by exchange later.
- **Edit financial assets** (owner's request): a Financial assets page lists every asset you can hold, with its class, exchange, ISIN and price source, and each opens a form to edit name, ticker, ISIN, exchange, class and whether it is still active. It is linked from Investments and the command bar, and from Settings once Settings is free (Codex holds it today).
- **Matching to the market file:** ISIN first, then country and ticker, then an alias; a match is stored on the asset, and a change of ticker in the file never renames the user's asset without asking.
- **Built (2026-10-05):** migration 0041 adds `mic`, `country` and `market_key` to `financial_assets` (stocks recorded so far became EGX, `XCAI`, `EG:<ticker>`; funds `EG`). `AssetService.create_investment` and `update_investment` check the ISIN's ISO 6166 check digit and the MIC's form, default a stock to EGX, and rename the code when the ticker changes (the asset keeps its id and history). `/investments/assets` lists every holdable asset (not currencies, physical items or price references); Investments' Holdings header and the command bar link it; the holding page names the exchange and ISIN. Settings links it once Codex's Settings claim ends (`NOW.md`).

## How the app gets prices

- **The bundled file.** Each release carries `market.zip`. On first run, after an import, and every month-end, the app fills prices from it for the instruments the profile holds. Manual prices still win.
- **Update prices.** One button (and an opt-in check at start-up) downloads `manifest.json` from a fixed address, compares checksums with the local copy in `Documents/Lightning/market/` (shared by all profiles, as it holds nothing personal), downloads only the changed files, verifies each checksum, and imports. A day's update is one daily file and the manifest.
- **Import a file.** Settings › Prices takes a `market.zip` by hand, for an offline PC or when the address moves.
- **Say how old it is.** Every price shown from the file carries its date; Needs you says "Prices are from 2026-10-01" when they are a week old, as today.
- **Same file for everyone.** Downloading the whole file tells no one what you hold.

## Five months of statements: the history story

Mohab imports THNDR statements from May to September. For each holding and month-end he needs a price:

1. The importer lists the (instrument, month-end) pairs it needs.
2. It fills them from the local market file at once: monthly closes reach back to 2015, daily closes 13 months.
3. What the file lacks (a fund we do not cover, a stock listed after the file was made) goes to Needs you: "2 prices missing: Misr Takaful Fund, July and August · Enter prices". Never a zero, never a guess.
4. Update prices can fill the rest later; a typed price stays.

This is why history ships in the file: it turns a minute of live requests that may fail into an instant, offline lookup.

## Keeping it alive

- **Small adapters with samples.** When a site changes, one adapter's test fails against the new sample, and the fix is local.
- **Fallbacks and cross-checks** per market, so one broken source lowers confidence instead of stopping prices.
- **Health and alarms.** Two failed runs in a row open a GitHub issue naming the source and its error; recovery closes it. The app shows the file's age, so a stale file is visible.
- **Our own history.** Because every day is kept in git, losing a source loses future prices from it, never past ones.
- **The address can move.** The app reads the manifest address from a setting with a built-in default, and Import a file always works.
- **Schedules keep running.** GitHub disables scheduled workflows after 60 days without activity; the daily data commit counts as activity.

## Rights and limits

These need the owner's decision before the file is published (`OWNER.md`):

- **Mubasher** asks automated clients not to use `/api/` in its robots.txt (as the open-source funds tracker reports). Use it at most once a day, or ask Mubasher for permission or a feed.
- **TradingView and Yahoo** terms forbid automated collection and republishing. They are fine as cross-checks a user's own app performs, but publishing their data in our file is a risk, more so in a paid app.
- **EGX** licenses its market data; republishing end-of-day prices in a commercial product may need a licence or a licensed vendor (EGX data vendors, or paid APIs with redistribution terms).
- **CBE rates** are official public data; republishing with attribution is the safest part.
- **Fund NAVs** are public disclosures by each manager; the manager's own page is the cleanest source.

Recommendation: start with CBE and managers' NAVs as published sources, get a licensed end-of-day feed for EGX and US prices before the file goes public, and keep the free sources as fallbacks and cross-checks.

## Phases

1. **Now:** this proposal; the file format with ISO names (`lightning/market/`); the collector with adapters, checks and health (`tools/market/`); exchange and ISIN on financial assets, with a Financial assets page to edit them; importing a market file into a profile from the Update prices page; the scheduled workflow, publishing only after the owner's go-ahead.
2. The release ZIP carries `market.zip`; Update prices downloads changed files; a statement import fills month-ends; Needs you lists what is missing; the Yahoo-per-user code is removed.
3. Funds, currencies and gold matched to profile holdings; reviewed Thndr-to-Mubasher fund mapping.
4. US stocks and FX revaluation, with multi-currency (Upcoming projects #15, #16).
