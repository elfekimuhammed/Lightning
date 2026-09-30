# Work log: this session (2026-09-30)

What was done in this session, in order, and how the [desktop build spec](BUILD_SPEC.md) was produced. The owner asked for this log together with the spec.

## 1. UI and reporting work (committed to `main`)

Each round is listed in the [CHANGELOG](../../CHANGELOG.md) under the same date. All of it was tested with the full suite (about 300 tests), `lint-imports` and `git diff --check` before each push.

| Commit | What |
|---|---|
| `04030ac` | One name and one calculation per reported figure (`lightning/core/figures.py`); one position calculation; one average monthly income. |
| `5f8cea9`, `63fa5c2` | Cash planning fixes from the Omar re-run; loan payments planned in the budget. |
| `24e5dd0` | Fixes from the Omar v7.1 re-run (skipped loan payments, Arabic-Indic digits, confirmations). |
| `b2d66c7`, `90a7093` | Three-layer glossary (ledger, plan, report) generated from the figure registry. |
| `cc0febb` | Project overview: workflow, main questions and gaps. |
| `0b93b24` | Open findings from the Omar runs (#111, #129–#133, import review, fees, buying by amount, new names). |
| `f766bc1` | Demo pass: chart components (trend, bars, meters, donut, share bar, sparkline), key notes and a one-click sample household. |
| `68f2c9c` | Crisp pass: one type scale, one look on every page, less text. |
| `48e9d36` | Round 3: month picker, no explanation toggles, "Net gain or loss", a gradient for wide cards, Needs you on top. |
| `3f92b9b` | Round 4: Birdview folded into the Overview, budget rows, clearer names, the 9 old tests fixed. |
| `113ec35` | Asset class colour palette, categories grouped by L1/L2, full-page popups with Back, horizon picker, XIRR tip, Money added fix. |
| `45ac58f` | Target allocation page (Current %, Required %, Difference, Value to adjust; saves in place); three-card expense summary; tinted key notes. |
| `900f367` | Browser autocomplete off on every field. |
| `d05c1fd` | Net worth trend, free cash waterfall, richer Expense analysis (usual month, who you paid, paid from, largest payments), softer add row. |

`bc622d9` (docs consolidated into four files) came from a **different session** and was merged in. `6146294`, `e506a3b`, `a4e7e35` and `41a985f` are the owner's pull-request merges.

## 2. The desktop question

- The owner asked whether the HTML UI work was wasted if Lightning moves to a Windows app. **Answer:** no. The recommended shell (pywebview + WebView2) shows the same pages, so every screen carries over.
- Three options were compared: pywebview + WebView2 + PyInstaller, Electron/Tauri, and a native rewrite. The owner chose the first ("open from an application like Actual Budget"), confirmed its trade-offs, and accepted the startup speed.
- Reviewing the Luna task `LIGHTNING-2026-09-30-05`, I flagged three changes the current code needs regardless of the shell: the data folder moves out of the program folder, a per-launch token protects the local server, and there are no requests to Google.
- The owner then asked for the full architecture to hand to another AI, with security in mind and with the database unreadable to anyone who copies it.

## 3. Research run 1: desktop build (8 agents)

Five agents read the codebase and three researched upstream sources. The codebase agents made no changes to the repo; probes ran against local servers or scratch copies.

| Agent | Area | Hands-on checks |
|---|---|---|
| 1 | Startup, data location, lifecycle | `PRAGMA journal_mode` = delete; uvicorn crash with `sys.stdout=None` reproduced; missing-migrations behaviour reproduced (a new DB fails, an existing DB starts silently with no new migrations) |
| 2 | Web attack surface | `Host: evil.com` → 400; cross-origin POSTs → 403; POST with no Origin → 303 (a backup was made); `/\evil.com` open redirect through the Back link; stored-XSS payloads escaped on 13 pages; 865 KB CSV → 400 (1 MB field limit) |
| 3 | Outbound network, background work, logging | What Yahoo receives; the narrow `except` in price workers (a connection reset escapes); tzdata missing on Windows |
| 4 | Frontend inside WebView2 | pywebview 6.2.1 defaults: downloads cancelled, Ctrl/middle-click opens the system browser, bridge injected on any page, file drop navigates the window |
| 5 | Launchers, dependencies, packaging readiness | The `nul` file blocks Windows checkout; no pins or hashes; version 0.3.0 vs 0.1.0; which resources need bundling |
| 6 | pywebview 6.x + WebView2 | Read from pywebview source at tag 6.2.1 and master; found the storage_path rmtree bug, the silent MSHTML fallback, and settings defaults that differ from the docs |
| 7 | Packaging, signing, installer, updates, CI | PyInstaller, Inno Setup, SignTool, Smart App Control, Artifact Signing, GitHub Actions hardening, TUF |
| 8 | Security threat model | Launch-code cookie, Fetch Metadata, the `Referrer-Policy: no-referrer` trap, the same-site-across-ports trap, CSP inventory, logging policy |

## 4. Research run 2: encryption at rest (3 agents)

| Agent | Area | Hands-on checks |
|---|---|---|
| 1 | Encryption on this codebase | Prototype with sqlcipher3 0.6.2 on a scratch clone: 298 tests passed and all 4 import contracts held after about 170 changed lines. Found the `sqlite3.Row` and exception-class traps (the emergency-fund conflict leaks a raw error). Converted a plaintext DB and backup and verified them. A wrong key is rejected. KDF cost: 143 ms per connection with a passphrase vs about 0.1 ms with a raw key. The patch is in `reference/encryption_prototype.patch`. |
| 2 | Engine comparison | Inspected the Windows wheel binaries (sqlcipher3 0.6.2 bundles SQLCipher 4.12.0, SQLite 3.51.1 and OpenSSL 3.6.0). Ran the suite on sqlcipher3 and on stock `sqlite3` + SQLite3 Multiple Ciphers: 298 passed on both, and all 250 DB files were encrypted. Tested WAL, backup(), VACUUM INTO, performance (`cache_size`), cross-reading between the two engines, and a Linux PyInstaller freeze. |
| 3 | Key management | Designed C' (recovery-key root, DPAPI or password slot). Prototype: `sqlcipher_export` of the demo schema (37 tables, counts equal), rekey in WAL mode (8 ms), Argon2id 256 MiB/t=3/p=4 in 0.43 s. The sketch is in `reference/keyvault_sketch.py` (DPAPI part never run). |

## 5. Sources the sandbox could not reach

The egress proxy blocked these sites:

- pywebview.flowrl.com
- learn.microsoft.com and developer.microsoft.com
- pyinstaller.org and pyinstaller.readthedocs.io
- jrsoftware.org
- docs.github.com
- peps.python.org and python.org
- sqlite.org
- zetetic.net
- utelle.github.io
- rogerbinns.github.io
- nuget.org

Where possible, the agents read the same documentation from its source repositories on GitHub (pywebview, MicrosoftDocs, pyinstaller, issrc, github/docs, python/peps), from PyPI metadata, and from the packages' own source code. The rendered pages may differ slightly. Claims that rest only on search snippets are marked as such in the spec.

## 6. What was not done

- **Nothing ran on Windows.** No Windows machine or VM was available. Every Windows behaviour is either read from source or marked unverified in the spec (section 15 there).
- **The spec was not verified.** A verification workflow (a completeness review plus adversarial checks of the draft) was started, then stopped at the owner's request ("Don't test it, give me the draft") before it wrote anything. This draft has had no second review.
- **No application code changed** for the desktop build. The spec, the log and the two reference files are the only additions.
- The scratchpad also holds about 130 plaintext `.db` files made by test runs and probes. They contain fictional demo data only (the real database was never in this sandbox) and disappear with the session container. They are not in the repo.

## 7. Files added

| File | What it is |
|---|---|
| `docs/desktop/BUILD_SPEC.md` | The architecture and build spec (draft) |
| `docs/desktop/WORK_LOG.md` | This log |
| `docs/desktop/reference/encryption_prototype.patch` | Research prototype: the sqlcipher3 driver swap, keyed backups, plaintext conversion. It is not production code and was not re-checked against current `main`. |
| `docs/desktop/reference/keyvault_sketch.py` | Research sketch: recovery key, HKDF, password slot, ctypes DPAPI. It is not production code. |
