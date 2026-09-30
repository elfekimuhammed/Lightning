# Lightning for Windows: architecture and build spec

**Status: DRAFT, not verified.** Written 2026-09-30 from two research runs (11 agents) over this repo and the upstream sources. The owner asked for the draft without a verification pass. Nothing here has run on Windows. Each claim has an evidence level (see [Evidence levels](#15-evidence-levels)). Treat every `[unverified]` item as a test you must pass before you rely on it.

**Task:** Luna `LIGHTNING-2026-09-30-05`, plus the owner's two additions: *keep security in mind* and *nobody can take the database and open it*.

**Who this is for:** the AI or developer who builds it. Read sections 1 to 3 first, then work through the milestones in section 12 in order. Each milestone ends with acceptance tests. Sections 4 to 11 are the reference for those milestones.

Related: [Architecture](../ARCHITECTURE.md) (module layers, contracts), [Project Overview](../PROJECT_OVERVIEW.md), [App brand guideline](../APPLICATION_BRAND_GUIDE.md) (any new screen follows it), [Work log](WORK_LOG.md) (how this spec was produced), `reference/` (prototype code, not production).

---

## Contents

1. [Goal, scope and definition of done](#1-goal-scope-and-definition-of-done)
2. [Decisions (defaults taken, owner can change)](#2-decisions-defaults-taken-owner-can-change)
3. [Target architecture](#3-target-architecture)
4. [Startup, shutdown and repeat launches](#4-startup-shutdown-and-repeat-launches)
5. [Data location and lifecycle](#5-data-location-and-lifecycle)
6. [Encryption at rest](#6-encryption-at-rest)
7. [Local server security](#7-local-server-security)
8. [The window (pywebview + WebView2)](#8-the-window-pywebview--webview2)
9. [Outbound network and privacy](#9-outbound-network-and-privacy)
10. [Packaging (PyInstaller)](#10-packaging-pyinstaller)
11. [Supply chain, signing, release and CI](#11-supply-chain-signing-release-and-ci)
12. [Milestones with acceptance tests](#12-milestones-with-acceptance-tests)
13. [Never do this](#13-never-do-this)
14. [Risks and open questions](#14-risks-and-open-questions)
15. [Evidence levels](#15-evidence-levels)
16. [Appendix: code sketches](#16-appendix-code-sketches-untested)

---

## 1. Goal, scope and definition of done

**Goal.** Lightning opens like an ordinary Windows application, the way Actual Budget does: double-click `Lightning.exe`, one window, no terminal and no browser tab. It keeps every screen and every financial service it has today. The database and backups are encrypted, so a copied file cannot be opened without the owner's key.

**In scope**

- A desktop shell: pywebview 6.2.1 hosting the existing FastAPI/Jinja UI in a WebView2 window. uvicorn runs in-process on a random loopback port.
- A per-user data folder outside the program. It holds the encrypted database, encrypted backups, logs and the key file.
- SQLCipher encryption for the database and every backup. The key is rooted in a recovery key; the app unlocks automatically through Windows DPAPI, or with a password if the owner chooses.
- Protection for the local server: a per-launch secret on every request, exact Host and Origin checks, security headers, and fixes for the open-redirect paths.
- A PyInstaller build: first a one-folder build, then a one-file `Lightning.exe`, validated on a clean Windows PC.
- A Windows CI job that builds the exe from locked, hash-checked dependencies.

**Out of scope for v1**

- Auto-update. At most, "Check for updates" opens the releases page in the system browser.
- Microsoft Store/MSIX.
- macOS and Linux packages. Source runs through `run.sh` keep working (section 6.9).
- Syncing a live database between PCs.
- Protection against malware or a person already signed in as the owner's Windows user (section 6.10).

**Definition of done** (from the Luna task, extended)

1. A single `Lightning.exe` opens one window with the Overview. No console appears and no browser tab opens.
2. Every existing screen and workflow works in that window, including both import downloads and the CSV upload.
3. The database, backups, logs and `keys.json` live in `%LOCALAPPDATA%\Lightning`, never next to the exe or in `%TEMP%`.
4. A copied `lightning.db` or backup does not open in DB Browser for SQLite or the Python `sqlite3` module. Its first 16 bytes are not `SQLite format 3\0`.
5. On a new PC, the recovery key alone opens a copied backup.
6. A missing WebView2 Runtime produces a clear message and a way to install it. The app never falls back to the IE engine.
7. A second double-click brings the running window to the front. It never starts a second server or opens the database twice.
8. Closing the window stops the server and closes every database connection. No `Lightning.exe` is left running in Task Manager.
9. A request without the per-launch secret gets 403, including GETs and `/static`.
10. Any startup failure shows a message box that names the log file. The log holds no amounts, names or query strings.
11. The clean-PC checklist in milestone M9 passes on Windows 10 22H2 and Windows 11.
12. The full test suite, `lint-imports` and `git diff --check` pass. New tests cover the new code, as listed per milestone.

---

## 2. Decisions (defaults taken, owner can change)

The owner asked for a draft without questions, so each open choice has a default. Build with the default unless the owner says otherwise.

| # | Decision | Default in this spec | Alternative | Why the default |
|---|---|---|---|---|
| D1 | Shell | pywebview 6.2.1 + WebView2 + uvicorn on `127.0.0.1:<random>` | Electron/Tauri rewrite; in-process ASGI bridge with no socket | Agreed with owner. A socketless bridge is not possible with pywebview today (section 7.9). |
| D2 | Final artefact | One-file `Lightning.exe` (Luna task). Build and validate one-folder first. | One-folder inside a per-user Inno Setup installer | The Luna task asks for a single exe. The installer is better for signing, speed and antivirus, so keep it ready as plan B (section 10.5). |
| D3 | Data folder | `%LOCALAPPDATA%\Lightning` for frozen **and** source runs | `%APPDATA%` (roams), Documents, next to exe | Per-user ACL, not roamed, not in OneDrive Known Folder Move. A single location removes the "data next to code" bug. |
| D4 | Existing data | Detect it, **copy** and convert it only after the user confirms, and never delete it silently | Auto-move | Rule already in ARCHITECTURE.md ("never move an existing database silently"). |
| D5 | Encryption engine | `sqlcipher3==0.6.2` (SQLCipher 4 format) behind one `lightning/database/driver.py` | stock `sqlite3` + SQLite3 Multiple Ciphers DLL swap | The same engine runs in dev, tests and the exe. Both engines read the same files, so switching later needs no data migration. |
| D6 | Key model | **C'**: recovery key is the root; DPAPI slot auto-unlocks by default; optional password slot replaces it | Passphrase only; DPAPI only | DPAPI alone loses data on a Windows reinstall. A passphrase alone loses data if forgotten, and a weak one makes backups crackable offline. |
| D7 | Recovery key size | 128 bits, 28 characters in 7 groups of 4 | 256 bits (about 52 characters) | 128 bits is as strong as 1Password's Secret Key and BitLocker's recovery key, and it can be typed. |
| D8 | Local auth | A one-time launch code swapped for an HttpOnly SameSite=Strict cookie, required on **every** request | Header injection via pywebview `request_sent` | The `request_sent` hook is racy in 6.2.1. The cookie needs no JavaScript changes. |
| D9 | Market prices | Stay on, but run in the background after the window opens. First-run screen and Settings say exactly what is sent, and there is a switch to turn it off. | Opt-in (off by default) | Keeps today's behaviour while making it visible. The owner may prefer off (section 9). |
| D10 | Fonts | Bundle Manrope and Bricolage Grotesque (OFL) locally and drop Google Fonts | Keep Google | Needed for offline use, for privacy, and for a `'self'`-only CSP. |
| D11 | Build Python | CPython **3.13** x64 for the frozen exe; source floor stays 3.11 | 3.11 | The last python.org Windows binary for 3.11 is 3.11.9 (April 2024), so a 3.11 exe would miss 7 security releases. |
| D12 | Code signing | v1 unsigned, for personal use, with SHA256SUMS published. Signing is planned in M10. | OV certificate on a cloud HSM; Azure Artifact Signing | Artifact Signing for individuals is limited to the US and Canada. An unsigned exe triggers SmartScreen and may be blocked by Smart App Control (section 14). |
| D13 | Demo | `--demo` stays a hidden flag. It uses its own `demo\demo.db` with a random throwaway key per start. The in-app "Add sample household" button stays as it is. | Remove from the exe | One code path; the demo data is fictional anyway. |
| D14 | Plain-browser dev mode | `python -m lightning` stays. It uses the same security middleware and opens the browser on the one-time launch URL. | Drop browser mode | Developers need it. The same code path means the same protection. |
| D15 | Idle lock | Only in password mode: 15 minutes plus "Lock now". In auto-unlock mode, Windows lock (Win+L) is the lock. | Always | An idle lock means nothing when DPAPI reopens the data without asking. |
| D16 | Version | Bump to **0.4.0**. `lightning/__init__.py` is the single source, and pyproject reads it. | Keep 0.3.0 | The first desktop release. It also fixes the 0.3.0/0.1.0 mismatch. |

---

## 3. Target architecture

### 3.1 Process model

```
Lightning.exe  (one process, standard user, never elevated)
│
├── main thread ─────────── pywebview GUI loop (webview.start blocks here)
│                            └── WinForms STA thread (pywebview-owned) → WebView2 control
│                                  │  loads http://127.0.0.1:<port>/__launch?code=<one-time>
│                                  │  private_mode=True (in-memory cookie, temp profile)
│                                  ▼
├── server thread (daemon) ─ uvicorn.Server(config).run(sockets=[pre-bound socket])
│                            └── asyncio loop = the ONLY thread that touches the database
│                                  FastAPI app
│                                  ├─ HostGuard → SessionGuard → FetchMetadata → LockGate
│                                  ├─ SecurityHeaders (response)
│                                  └─ existing routers (unchanged apart from sections 7.6–7.8)
│
└── price worker (daemon, optional) ── HTTPS to Yahoo only; hands results to the loop
                                         thread, which does all the DB writes

Disk: %LOCALAPPDATA%\Lightning\
      lightning.db (SQLCipher)   lightning.db-journal (transient, encrypted)
      backups\lightning_YYYY-MM-DD_HHMM_k-XXXX.db (SQLCipher, same key)
      keys.json (DPAPI- or password-wrapped data key; never the recovery key)
      logs\lightning.log (rotating, no financial data)
      lightning.lock (single-instance lock)
      demo\demo.db (only with --demo; throwaway key)
```

Keep the rule that exactly one thread writes to the database. All 125 route handlers are `async def`, so today every request already runs on the event-loop thread with one connection. The price worker does network I/O only.

### 3.2 Module layout (new and changed)

```
desktop_main.py                    NEW  repo-root PyInstaller entry: from lightning.desktop.app import run; run()
lightning/
  desktop/                         NEW  top layer (sibling of lightning.main)
    app.py                         run(): the startup order of section 4.1
    server.py                      pre-bound socket, uvicorn thread, readiness, stop
    window.py                      pywebview settings, create_window, navigation guard, events
    instance.py                    single-instance lock, focus the running window
    winapi.py                      ctypes: MessageBoxW, FindWindowW/SetForegroundWindow, WebView2 registry check
  security/                        NEW  layer beside lightning.database (neither imports the other)
    recovery.py                    recovery key: generate, encode, parse, checksum; HKDF data key; key_id
    slots.py                       keys.json: atomic read/write; dpapi slot; password slot (Argon2id + AES-GCM)
    dpapi.py                       ctypes CryptProtectData / CryptUnprotectData (Windows only)
    secret.py                      KeyHolder: bytearray key, hex literal, wipe()
  core/paths.py                    NEW  data_dir(), logs_dir(), resource checks, legacy_candidates(); frozen-aware
  core/logs.py                     NEW  logging setup, None-stdout safety, no-financial-data formatter
  database/driver.py               NEW  the only module that imports sqlcipher3 (Row, exceptions, key helpers)
  database/encrypt.py              NEW  plaintext → encrypted conversion with verification
  database/connection.py           CHANGED  key per connection, guards, connection registry, close_all()
  database/backup.py               CHANGED  keyed and verified backups, key tag in the name, tiered retention
  database/migrator.py             CHANGED  driver exceptions; "migrations found" and downgrade guards
  reserves.py                      CHANGED  driver.IntegrityError
  */repository.py (4 files)        CHANGED  Row from the driver
  assets/market_data.py            CHANGED  split fetch (thread) from apply (loop); catch-all in workers
  bootstrap.py                     CHANGED  Session (setup/locked/recover/ready); build(db_path, key=...)
  main.py                          CHANGED  dev/browser mode on the same Session and security code
  ui/security.py                   NEW  middleware of section 7; safe_local_path()
  ui/routes/unlock.py              NEW  /setup/*, /unlock, /recover, /lock, /__launch
  ui/routes/settings.py            CHANGED  Security and Backups tabs
  ui/templates/unlock/*.html       NEW  first-run, unlock, recover screens (brand guide)
  ui/static/app.js                 CHANGED  inline scripts moved in; modified-click and file-drop guards
  ui/static/fonts/                 CHANGED  add Manrope and Bricolage Grotesque woff2 + @font-face
packaging/
  lightning-onedir.spec            NEW
  lightning-onefile.spec           NEW
  version_info.txt                 GENERATED in CI from lightning.__version__
  lightning.ico                    NEW
  MicrosoftEdgeWebview2Setup.exe   NOT COMMITTED  fetched and signature-checked in CI (section 8.5)
requirements/                      NEW  *.in sources and hash-locked *.lock files (section 11.1)
.github/workflows/windows-build.yml NEW
```

**Import-linter contract change** (`pyproject.toml`), top of the layers list and the database layer:

```toml
layers = [
    "lightning.desktop | lightning.main",
    "lightning.ui",
    "lightning.bootstrap",
    # ... unchanged ...
    "lightning.assets | lightning.categories",
    "lightning.database | lightning.security",
    "lightning.core",
]
```

Also add a forbidden contract: nothing outside `lightning.database.driver` and `lightning.database.encrypt` may import `sqlite3` or `sqlcipher3`. `encrypt.py` needs stdlib `sqlite3` only to replay a hot journal on the old plaintext file. The UI keeps its rule of never touching `lightning.database`. It reaches keys through `lightning.security` and `bootstrap.Session`.

### 3.3 The Session object (locked or ready)

Today `create_app(container)` receives a ready container. After this work it receives a `Session`, because the server must be able to run before the database can be opened (first run, password mode, recovery).

```python
class Session:                       # lightning/bootstrap.py
    state: Literal["setup", "locked", "recover", "ready"]
    data_dir: Path
    container: Container | None      # set only in "ready"
    def unlock(self, key: KeyHolder) -> None   # build(db_path, key=key); then state = "ready"
    def lock(self) -> None                     # container.db.close_all(); key.wipe(); container = None
```

`web.py`'s container accessor keeps returning `request.app.state.session.container`. `LockGate` (section 7.4) makes sure no normal route runs unless the state is `"ready"`.

---

## 4. Startup, shutdown and repeat launches

### 4.1 Desktop startup order (`lightning/desktop/app.py`)

Each step either succeeds or ends in a message box that names the log file. None of them fails silently.

1. **Logging first.** `core.logs.install()`: if `sys.stdout` or `sys.stderr` is `None` (PyInstaller windowed mode), point them at the log file. Set up a `RotatingFileHandler` at `logs\lightning.log` (1 MB × 5 files, WARNING level). Install `sys.excepthook` and `threading.excepthook` so they log and show a message box.
2. `multiprocessing.freeze_support()` (cheap guard).
3. **Paths.** `paths.data_dir()` returns `%LOCALAPPDATA%\Lightning` and creates it. Resolve every path to absolute. When `sys.frozen` is set, ignore `LIGHTNING_TODAY`.
4. **Single instance.** `instance.acquire(data_dir)` takes an exclusive lock on `lightning.lock`. If another process holds it, call `winapi.focus_window("Lightning")` and exit 0. This runs *before* any backup, migration or network work, which closes the double-click race described in section 4.3.
5. **Preflight.**
   - A WebView2 Runtime version of at least 86 is found in the registry (section 8.5).
   - `driver.cipher_version()` is not empty. Otherwise refuse to run: "This build cannot encrypt data".
   - Resources exist: the migrations list is not empty, the templates and static folders are present, the EGX catalogue is present, and `ZoneInfo("Africa/Cairo")` resolves.
   - `--self-check` runs only this step plus a temporary encrypted create → migrate → backup → reopen, then exits with code 0 or 1. CI uses it (section 11.3).
6. **Session state** (section 6.6):
   - no `keys.json` and no DB → `setup`
   - DPAPI slot → unwrap → `unlock()` → `ready`; if the unwrap fails → `recover`
   - password slot → `locked`
   - DB present but no `keys.json` → `recover`
   - DB header is plaintext → `setup`, with the import step pre-filled

   Unlocking builds the container: backup, then migrate, then seed. This is local work and takes well under a second on the owner's data size (estimate). No network work runs here.
7. **Server** (sketch in section 16.2):
   - Create a socket with `SO_EXCLUSIVEADDRUSE` and bind it to `('127.0.0.1', 0)`.
   - `create_app(session, SecurityConfig(port, token, launch_code))`.
   - `uvicorn.Config(app, log_config=None, access_log=False, http="h11", loop="asyncio", ws="none", lifespan="on", server_header=False, date_header=False)`.
   - Run `Server.run(sockets=[sock])` in a daemon thread.
   - Wait for `server.started` for up to 10 s. If the thread dies or the wait times out, show a message box.
8. **Window.** Set every `webview.settings` value explicitly (section 8.1), then call `create_window(url=launch_url, ...)`. Attach the navigation guard in `before_show`. The `initialized` handler requires `edgechromium`. Start a watchdog: if `loaded` has not fired within 20 s, show an error.
9. `webview.start(gui="edgechromium", debug=False, private_mode=True)`. This blocks the main thread.
10. **After the window is ready**, if the state is `ready` and market prices are on, start the price worker (section 9.2). The same happens after a later `unlock()`.
11. **Shutdown**, after `start()` returns:
    1. `session.lock()`: close every connection and wipe the key.
    2. Set `server.should_exit = True` and join the server thread for up to 5 s.
    3. Release the instance lock, flush the logs and exit.
    4. Price workers are daemon threads with an overall deadline, so they never keep the process alive. If anything still hangs after step 3, `os._exit(0)` is the last resort. The database is already closed by then.

Do **not** shut down inside the `closing` event. It runs on the WebView2 UI thread, and blocking it can deadlock.

### 4.2 Dev/browser mode (`python -m lightning`, `run.bat`, `run.sh`)

This mode uses the same paths, logging, instance lock, Session and security middleware. The differences:

- The port stays fixed at 8765 (`--port` still works).
- There is no pywebview.
- The browser opens `http://127.0.0.1:8765/__launch?code=…`, and the URL is also printed for `--no-browser`.
- On a repeat launch, the second process prints "Lightning is already running; use its window/tab" and exits.

The unauthenticated `/__health` probe goes away, because the lock file replaces it.

### 4.3 Why the current order has to change

Today's order is: health probe on the fixed port 8765, then a raw TCP probe, then backup, migrate, and up to about 20 s of Yahoo fetches, then `uvicorn.run` on the main thread. Its problems:

- A windowed exe shows nothing for up to 20 s when offline.
- Two quick double-clicks both pass the probes, and both back up and migrate the same file.
- Any local process can squat port 8765 and answer `lightning-ok`.
- `uvicorn.run` cannot own the main thread, because pywebview needs it.
- In windowed mode, uvicorn's default log config crashes on `sys.stdout.isatty()` because `sys.stdout` is `None`. This was reproduced.

---

## 5. Data location and lifecycle

### 5.1 Paths (`lightning/core/paths.py`)

| Item | Path | Notes |
|---|---|---|
| Data folder | `%LOCALAPPDATA%\Lightning` (`os.environ["LOCALAPPDATA"]`, with `SHGetKnownFolderPath` as fallback) | Linux: `$XDG_DATA_HOME/lightning` or `~/.local/share/lightning`. macOS: `~/Library/Application Support/Lightning`. |
| Database | `<data>\lightning.db` | `--db` still works for developers. Always `.resolve()` it. Warn if the folder grants Users, Authenticated Users or Everyone access. |
| Backups | `<data>\backups\` | Never in the install folder. |
| Logs | `<data>\logs\lightning.log` | Rotating. The content rules are in section 7.8. |
| Keys | `<data>\keys.json` | Section 6.4. |
| Lock | `<data>\lightning.lock` | Section 4.1, step 4. |
| Resources | Relative to `__file__` (unchanged) | This works inside `_MEIPASS` once PyInstaller collects the data files. |

Never place data under `sys._MEIPASS` (deleted on exit in one-file builds), under `Program Files` (not writable), or in `C:\ProgramData` (readable by all users).

### 5.2 Existing data (legacy import)

Candidates to look for: `PROJECT_ROOT\data\lightning.db` (source checkout, not frozen), `<exe folder>\data\lightning.db`, and any file the user picks.

1. The first-run screen offers **Start fresh** or **Bring in my existing data…** (the dialog is described in section 8.4). It shows any candidate it found.
2. Open the source with stdlib `sqlite3`, which replays a hot journal. Run `PRAGMA integrity_check` and record the row count of every table. Stop if the integrity check fails.
3. `sqlcipher_export` it into `<data>\lightning.db.encrypting` under the new key (section 6.7). Reopen that file with the key and run `integrity_check` and `cipher_integrity_check`. The row counts must be equal. Then `os.replace` it to `lightning.db`.
4. Offer to convert the old `data\backups\lightning_*.db` files into the new `backups\` folder the same way. Default: yes.
5. Only then ask whether to delete the original plaintext files. Warn plainly: "Copies may still exist in the Recycle Bin, OneDrive version history, File History or restore points, and on the SSD itself." Never delete without that confirmation.

### 5.3 Backups

- **When:**
  - at the first unlock of each calendar day (skipped if today's backup exists);
  - always before a migration that has something to apply;
  - on "Back up now".
- **Health first:** run `PRAGMA quick_check` on the live database before backing up. If it fails, do not back up and do not prune. Show a "Needs you" notice. This keeps a damaged database from pushing every good copy out.
- **How:**
  - Open the destination `…​.db.partial` with the driver and key it with the same data key.
  - Run `db.conn.backup(dest)`, then `PRAGMA quick_check` on the copy.
  - Refuse the copy if its header is plaintext.
  - `os.replace` it to the final name. Delete the partial file on any failure.
  - `VACUUM INTO` is an alternative; it also writes an encrypted copy with no free-page residue.
- **Name:** `lightning_YYYY-MM-DD_HHMM_k-XXXX.db`, where `XXXX` is the first 4 hex characters of `key_id`. This still matches `lightning_*.db`, so the Settings list and the `test_backup_button` assertion keep working.
- **Retention:** keep the newest 30, plus the last backup of each of the previous 12 months. Log a pruning error (for example `PermissionError` from antivirus or a sync tool) and carry on; it must never stop startup.
- **Optional mirror:** Settings → "Also copy backups to…" a folder such as a USB drive or OneDrive. This is safe because only the recovery key opens a backup.
- **Restore** (Settings → Backups → Restore):
  1. close all connections;
  2. back up the current database as `…_pre-restore`;
  3. copy the chosen backup over the live file;
  4. reopen and migrate.

  "Open a backup from another PC" asks for the recovery key when the backup's key tag differs from this PC's.

### 5.4 Database settings

Pragmas are set on every connection, in this order, right after `PRAGMA key`:

1. `cipher_log_level = NONE`
2. `cache_size = -65536` (64 MB; without it, full scans ran 7 to 11 times slower on SQLCipher)
3. `temp_store = MEMORY`
4. `secure_delete = ON`
5. `foreign_keys = ON`
6. `busy_timeout = 5000`

The journal mode stays `DELETE`. SQLCipher encrypts the rollback journal, and so it would the WAL, so WAL can be turned on later if needed. The demo cleanup must also delete `-journal`, not just `-wal` and `-shm`.

### 5.5 Schema guards

- If the bundled migrations list is empty, stop. Today a missing folder silently applies nothing to an existing database.
- If `schema_migrations` holds a version higher than the highest bundled migration, refuse to open: "This data was saved by a newer Lightning". This protects the database from an older exe.

---

## 6. Encryption at rest

### 6.1 Threat model: what this protects

| Threat | Protected? |
|---|---|
| Someone copies `lightning.db` or a backup (USB, cloud sync, email, stolen backup drive) | **Yes.** Without the recovery key it is a 128-bit problem. |
| Another Windows account on the same PC opens the file | **Yes.** The file is encrypted, and `%LOCALAPPDATA%` is user-only. |
| Another Windows account talks to the running server | **Yes, through section 7:** the per-launch secret. Encryption at rest cannot help while the app is unlocked. |
| Stolen laptop without BitLocker, auto-unlock mode | **Only as strong as the Windows password.** Recommend BitLocker/Device Encryption, or password mode. |
| Malware or a person signed in as the owner | **No.** This is out of scope for any in-app control; say so in Settings and the README. |
| Old plaintext copies (repo `data\`, OneDrive history, Recycle Bin, shadow copies) | **No, but the user is warned** during the migration (section 5.2). |

### 6.2 Engine: `sqlcipher3==0.6.2` behind `lightning/database/driver.py`

- It is coleifer's official package. Its self-contained Windows wheels (cp39 to cp314; win32, win_amd64 and arm64) statically link SQLCipher 4.12.0, SQLite 3.51.1 and OpenSSL 3.6.0. The build options include `HAS_CODEC`, `TEMP_STORE=2`, `THREADSAFE=1` and `ENABLE_FTS5`. SQLite 3.51 covers the app's needs: `DROP COLUMN` (migration 0006) and window functions.
- `driver.py` re-exports `connect`, `Row`, `Connection`, `Cursor`, `Error`, `DatabaseError`, `IntegrityError` and `OperationalError`. It also adds `WrongKeyError`, `key_literal(key)`, `apply_key(conn, key)`, `is_plaintext(path)` and `cipher_version()`. The prototype is in `reference/encryption_prototype.patch`.
- **Traps the prototype hit, all verified in the sandbox:**
  - Stdlib `sqlite3.Row` raises TypeError on a sqlcipher3 cursor.
  - sqlcipher3's exception classes are **not** subclasses of the stdlib ones. `migrator.py:48` (`except sqlite3.OperationalError`) and `reserves.py:140` (`except sqlite3.IntegrityError`) silently stop catching. The duplicate emergency-fund case then leaks a raw 500, and no test covers that path today.
  - `backup.py` with an unkeyed stdlib destination raises TypeError on every start.
  - `PRAGMA key = ?` is a syntax error. Use a raw key literal `"x'<64 hex>'"`, never string-built passphrases.
  - `ATTACH … KEY ''` writes **plaintext**. Never pass an empty key.
  - On a SQLite build without encryption, `PRAGMA key` silently does nothing. Hence the guard in 6.3.
- **Fallback engine** if sqlcipher3 stalls: the stock `sqlite3` module with SQLite3 Multiple Ciphers 2.5.1 (`sqlite3mc_x64.dll` renamed to `sqlite3.dll` in the spec), using `cipher=sqlcipher` and `legacy=4`. It reads and writes the same files (checked in both directions), so no data migration is needed. The cost: dev and test runs stop exercising encryption.

### 6.3 Guards (every open)

1. `PRAGMA cipher_version` must not be empty. Otherwise the app refuses to start.
2. If the file exists and its first 16 bytes are `SQLite format 3\0`, the app never opens it as the live database and sends the user to the import flow.
3. `PRAGMA key` must be the first statement. Immediately after it, `SELECT count(*) FROM sqlite_master`. A `DatabaseError` here becomes `WrongKeyError`, which the UI shows as "That key doesn't open this data."
4. Tests assert that every database and backup file the suite creates is not plaintext, and that stdlib `sqlite3` refuses to open it.

### 6.4 Keys (design C')

```
recovery secret   = 16 random bytes (os.urandom)                   ← shown once, never stored on the PC
recovery key text = Crockford Base32 of (secret ‖ 12-bit check), 28 chars, 7 groups of 4
                    check = first 12 bits of SHA-256("lightning-rk-v1" ‖ secret)
                    parsing ignores case, spaces and hyphens; O→0, I→1, L→1
data key (32 B)   = HKDF-SHA256(ikm=secret, salt="lightning/v1", info="lightning/db-key/v1")
                    → PRAGMA key = "x'<hex>'"   (raw key: no SQLCipher KDF, 0.1 ms per connection
                                                 instead of about 150 ms)
key_id            = HMAC-SHA256(data key, "lightning/key-id/v1")[:16 hex]   (not secret; shows
                    which recovery key opens which file; also stored in the settings table)
```

**`keys.json`** (written atomically: temp file, fsync, `os.replace`). It holds exactly one slot at a time:

```json
{
  "format": "lightning-keys/1",
  "key_id": "e5b91c07a3d24f88",
  "created": "2026-10-01T09:12:00+02:00",
  "recovery_confirmed": true,
  "slot": {"type": "dpapi", "entropy": "Lightning/dpapi/db-key/v1", "blob": "<base64>"}
}
```

```json
  "slot": {"type": "password", "kdf": "argon2id", "m_kib": 262144, "t": 3, "p": 4,
           "salt": "<b64 16 B>", "nonce": "<b64 12 B>", "ct": "<b64 AES-256-GCM(data key)>"}
```

- **DPAPI slot:**
  - `CryptProtectData(data key, entropy="Lightning/dpapi/db-key/v1", flags=CRYPTPROTECT_UI_FORBIDDEN)`, called through ctypes. The code is about 40 lines; see `reference/keyvault_sketch.py`.
  - Never use `CRYPTPROTECT_LOCAL_MACHINE`, which would let any user on the PC decrypt.
  - Zero and `LocalFree` the output buffers.
  - Do not use the `keyring` package on Windows. It is DPAPI underneath, roams with `CRED_PERSIST_ENTERPRISE`, and adds dependencies.
- **Password slot:**
  - Argon2id with m=256 MiB, t=3, p=4 and a 16-byte salt (measured 0.43 s on 4 vCPU). If memory allocation fails, fall back to 64 MiB.
  - AES-256-GCM, with associated data = the canonical JSON of `{format, key_id, slot minus ct}`.
  - Use `cryptography` (≥ 44; pin 50.0.2) for Argon2id, HKDF and AES-GCM.
  - Store the parameters in the slot, and re-wrap on unlock if they are below target.
- **Password mode replaces the DPAPI slot.** Otherwise malware running as the user could skip the prompt by calling `CryptUnprotectData`. The UI says so: "Lightning will no longer open automatically."
- If a slot fails (DPAPI error after a reinstall, or a missing or corrupt `keys.json`), **never delete anything**. Go to `recover`, and after a successful recovery create a fresh slot.

### 6.5 Changing keys

| Action | What happens |
|---|---|
| Turn password on, change it or remove it | The data key is re-wrapped. Nothing is re-encrypted. |
| New recovery key (lost or leaked) | Derive a new data key. Close the other connections, then `PRAGMA rekey = "x'…'"` on the live database (8 ms on a 464 KB demo database). Rekey every local backup and mirror while the old key is still in memory. Update `keys.json` and `key_id`. Tell the user that copies elsewhere still open with the old key. |
| Test recovery key | Parse the key, derive the data key, and compare its `key_id`. Nothing changes. Remind the user every 6 months. |

### 6.6 Screens (follow the brand guide: one card, few words)

**First run (`/setup`)**

1. "Your data is encrypted on this computer." Buttons: **Start fresh** / **Bring in my existing data…** (section 5.2).
2. The recovery key in 7 groups, with **Save as…** (a download of `Lightning recovery key.txt` holding the key, key_id, date and one line of instructions; the user picks the folder) and **Print** (`window.print()`) [unverified in WebView2 with debug off]. The warning text: "Keep this away from this PC. Anyone with it and a copy of your data can open it. Lightning can't show it again." **There is no Copy button in v1**, because clipboard history and cloud clipboard would keep the key.
3. Confirm by typing two randomly chosen groups.
4. "How should Lightning open?" (•) Automatically when I'm signed in to Windows (recommended). ( ) Ask for a password every time. Below that: the market-prices switch with its one-line disclosure (section 9.2).

**Unlock (`/unlock`, password mode):** a password field; "Wrong password."; a link to "Use recovery key instead".

**Recover (`/recover`):** "Enter your recovery key". Error messages: "That recovery key has a typo" (checksum) or "That key doesn't open this data" (`WrongKeyError`). On success, create a new DPAPI slot, or a password slot if the user asks for one.

**Settings → Security:**

- Status: "Encrypted · SQLCipher 4.12.0 · key k-e5b9"
- How it opens, with a change option
- Change or remove the password
- Test the recovery key
- Create a new recovery key
- Idle lock minutes and **Lock now** (password mode only)
- Backup mirror folder
- One honest line: "Protects copies of your data. It can't protect a PC someone is signed in to."

**Settings → Backups:** a list with dates and key tags, **Back up now**, **Restore…**, and **Open a backup from another PC…**

### 6.7 Plaintext → encrypted conversion (`lightning/database/encrypt.py`)

This is the prototype `encrypt_file()`, which ran on a copy of `demo.db` and on a plaintext backup: 37 tables with equal counts, and the account name was absent from the output.

1. Replay and check the plaintext: stdlib connect, row counts, `integrity_check`.
2. Open sqlcipher3 unkeyed on the plaintext file, then `ATTACH ? AS encrypted KEY "x'…'"` (never an empty key), `SELECT sqlcipher_export('encrypted')`, `DETACH`.
3. Verify: open the new file with the key, run `integrity_check` and `cipher_integrity_check`, and compare the counts.
4. `os.replace`, then remove the `-journal`, `-wal` and `-shm` files.

Note that `sqlcipher_export` does not copy `PRAGMA user_version`. Lightning uses `schema_migrations`, so this doesn't matter.

### 6.8 Locking (password mode)

- `Database` keeps a registry of every connection it opens on any thread, plus `close_all()`. Today `close()` only closes the calling thread's connection. SQLCipher holds the key in each open connection.
- The key lives in a `bytearray` inside `KeyHolder`. `wipe()` zeroes it with `ctypes.memset`. This is best effort, because Python makes copies (the hex literal string, OpenSSL internals).
- On idle timeout or **Lock now**:
  1. `session.lock()`, run on the loop thread;
  2. the shell calls `window.load_url(<origin>/unlock)`, so balances do not stay on screen;
  3. the price worker checks `session.generation` and drops its results.
- `cipher_memory_security` stays off in v1. It gives little on top of Python's own copies. Recommend BitLocker, which also covers the pagefile and hibernation file.

### 6.9 Source runs on macOS or Linux (`run.sh`)

DPAPI is Windows-only. In v1, source runs on other systems use the password slot. A `keyring` slot (Keychain or Secret Service) is a later option. Tests mock DPAPI on Linux.

### 6.10 What we tell the user (README and Settings)

- The data is encrypted, and a copied file is useless without the recovery key.
- Lose both the PC's automatic unlock (for example after a Windows reinstall) and the recovery key, and the data is gone. The same applies to a forgotten password without the recovery key.
- Encryption cannot protect a PC someone is already signed in to. Turn on BitLocker or Device Encryption.
- Remove from the README: "open the file with any SQLite browser" and "copy it to back it up". Replace them with: "DB Browser for SQLite in SQLCipher 4 mode, with a raw key derived from your recovery key (Settings shows how), or restore through Lightning."

---

## 7. Local server security

### 7.1 Why

`127.0.0.1` stops other machines, but loopback is shared by every process and every signed-in Windows account on the PC (fast user switching, RDP). Today:

- there is no authentication at all;
- the port is fixed and well known;
- the POST origin check fails open when both Origin and Referer are missing (true of `curl` or malware);
- `testserver` is an allowed Host in production;
- no security headers are sent.

Precedents: Jupyter requires a token on localhost, and Zoom's localhost server became CVE-2019-13450.

### 7.2 Launch code → session cookie

1. At startup the shell creates two secrets with `secrets.token_urlsafe(32)`: the session token, which stays in memory for the process lifetime, and a single-use launch code that expires after 30 s.
2. The window opens `http://127.0.0.1:<port>/__launch?code=<code>`.
3. `/__launch` (GET only) checks the code with `hmac.compare_digest`, confirms it is unused and not expired, and marks it used. It answers `303 /` with `Set-Cookie: lightning_session=<token>; HttpOnly; SameSite=Strict; Path=/`. There is no `Secure` flag and no `__Host-` prefix, because both need HTTPS; whether Chromium accepts Secure over `http://127.0.0.1` is [unverified]. Any other request to `/__launch` gets a 403 page: "Open Lightning from its icon."
4. `SessionGuard` checks every other request, including `/static`: the cookie must equal the token (`compare_digest`). If not, it returns a bare 403, with no redirect and no detail.
5. The token is never written to disk, logs or HTML. **Do not** use pywebview's `webview.token`. pywebview injects it into every page the window loads, whatever the origin.
6. With `private_mode=True` the cookie lives only in the in-memory WebView2 profile.

### 7.3 Host and Fetch Metadata

- **HostGuard:** in production, `Host` must equal `127.0.0.1:<port>` exactly. Starlette's `TrustedHostMiddleware` ignores the port, so write a small custom check. Use one canonical host, because `localhost` and `127.0.0.1` have separate cookie jars. Move `testserver` into the test configuration only (make `allowed_hosts` a `create_app` parameter).
- **FetchMetadata:**
  - Unsafe methods (POST today) are allowed only if `Sec-Fetch-Site == "same-origin"`. If that header is absent, `Origin` must equal `http://127.0.0.1:<port>` exactly. Anything else gets 403.
  - GET and HEAD are allowed if `Sec-Fetch-Site` is absent, `same-origin` or `none`.
  - **Never accept `same-site`.** Pages on other ports of `127.0.0.1` count as same-site.
- **No hidden CSRF form tokens are needed.** The cookie, SameSite=Strict and Fetch Metadata cover it.

### 7.4 LockGate

When `session.state != "ready"`, only these are allowed: `/__launch`, `/setup/*`, `/unlock`, `/recover`, `/static/*` and `/lock`. A GET for anything else gets `303` to the page for the current state; any other method gets 409. The gate also records the last activity for the idle lock.

### 7.5 Response headers (`SecurityHeaders`)

```
Content-Security-Policy: default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline';
                         img-src 'self' data:; font-src 'self'; connect-src 'self'; form-action 'self';
                         frame-ancestors 'none'; base-uri 'none'; object-src 'none'
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
Referrer-Policy: same-origin          ← NOT no-referrer: with no-referrer, browsers send "Origin: null"
                                        on same-origin POSTs and every save would be blocked
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Resource-Policy: same-origin
Cache-Control: no-store               ← on everything except /static
```

**CSP needs refactoring first.** The templates hold 19 inline `<script>` blocks, 7 inline `on*=` handlers (3 onclick, 2 onchange, 1 oninput, 1 onsubmit) and 69 `style=` attributes.

- Move every script and handler into `app.js`, keyed on `data-` attributes, and use `script-src 'self'`. This needs no nonces.
- Move the `{{ base }}` value that sits inside a JS string into a `data-` attribute.
- `'unsafe-inline'` for styles is an accepted v1 trade-off.
- A side benefit: popups insert HTML with `innerHTML`, so their inline scripts never run today. The plan-item kind switcher, for example, is inert in the popup. Moving the scripts fixes that.
- Roll out as `Content-Security-Policy-Report-Only` in dev first, check the browser console on every page, then enforce.

### 7.6 Redirects: one `safe_local_path()`

The open redirect is real: `?return_to=/%5Cevil.com` renders the Back link as `href="/\evil.com"`, which the browser resolves to `http://evil.com/`. In a window with no address bar, that is a strong phishing surface, and the foreign page would also receive `window.pywebview`.

```python
def safe_local_path(value: str | None, default: str) -> str:
    """A same-origin path, or the default. Rejects scheme/host, '\\', control chars, leading '//'."""
```

It must replace all the variants: `web._back_url` (web.py:79-80), `transactions._back` (:104-106, :283-284), `accounts._safe_return` (:96-98), the unvalidated planning `back` (planning.py:184, :272; this is a latent `javascript:` XSS, masked only because `base.html` overwrites the variable), and the settings and budget checks. Also rename the clashing `back` template variable.

Tests: `/\evil.com`, `/%5Cevil.com`, `/\t/evil.com`, `//evil.com`, `http://evil.com`, `javascript:alert(1)`, and an absolute URL on the app's own host with a backslash. Each must resolve (with `urljoin` as the browser would) to the app origin or the default.

### 7.7 Other fixes in this area

- **State-changing GETs** (`/plan/recurring`, `/plan/loans` call `match_payments`): the token plus Fetch Metadata now block cross-site triggering. Moving them to POST is optional later work.
- **Uploads:**
  - Reject a request whose `Content-Length` is over 6 MB before calling `request.form()`.
  - Raise Starlette's multipart `spool_max_size` above 5 MB so statements stay in memory and never reach `%TEMP%`.
  - Fix the map step's hidden base64 field, which hits Starlette's 1 MB per-part limit. Real statements over about 768 KB fail today with a 400. Either pass a larger `max_part_size` to `request.form()` or stage the upload server-side. [unverified: exact Starlette 1.7 parameter]
- **Errors:** add a generic `LightningError` handler that renders a proper error page. `debug=False` stays, and tracebacks never reach the page.
- **`?msg=` flash text:** low risk once navigation is locked. Carrying it in a short-lived server-side store is optional later work.

### 7.8 Logging policy

- Set `access_log=False` explicitly and keep uvicorn at WARNING.
- A log record may hold: time, level, logger, exception **type**, route **template** (for example `/accounts/{id}`), file:line frames, and counts.
- It must never hold: query strings, form values, amounts, names, tickers, file contents, the token, the launch code or key material.
- Enforce this with a formatter that drops exception messages and `args`. Replace the current `print(f"... {exc}")` calls.
- No telemetry or crash reporter.

### 7.9 Rejected: removing the socket

Named pipes and Unix sockets don't work with this stack. CPython has no AF_UNIX on Windows, and WebView2 can't load pages over a pipe. Serving the ASGI app through `CoreWebView2.WebResourceRequested` inside the process would remove the port entirely, but pywebview doesn't expose a way to supply responses. That makes it a possible later spike, not v1.

---

## 8. The window (pywebview + WebView2)

### 8.1 Settings (set explicitly before `webview.start`)

```python
webview.settings["ALLOW_DOWNLOADS"] = True                   # the two import helper downloads + recovery-key "Save as…"
webview.settings["ALLOW_FILE_URLS"] = False                  # code default is True (docs say otherwise)
webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = False   # else target=_blank URLs go to os.startfile unchecked
webview.settings["OPEN_DEVTOOLS_IN_DEBUG"] = False
webview.settings["REMOTE_DEBUGGING_PORT"] = None             # a CDP port gives any local process full control
webview.settings["IGNORE_SSL_ERRORS"] = False
window = webview.create_window("Lightning", url=launch_url, width=1280, height=820, min_size=(960, 640))
webview.start(gui="edgechromium", debug=False, private_mode=True, http_server=False, ssl=False)
```

- **No `js_api`.** The frontend needs no bridge, and whatever you expose can be called by any page that ends up in the window.
- **No `storage_path`.** In 6.2.1, `private_mode=True` together with `storage_path` makes pywebview **delete that folder with rmtree on exit**. Pointed at the data folder, that would be data loss. The bug is fixed on master but not released.
- **Window size:** the default 800×600 is narrower than the app's 900 px mobile breakpoint.
- `debug=True` exists only behind an explicit developer environment variable, never in a release build.

### 8.2 Navigation lock

pywebview does not restrict navigation. It injects its bridge into every page after navigation, with no origin check.

1. In `window.events.before_show`, attach `NavigationStarting` on the native WebView2 control:
   - allow `http://127.0.0.1:<port>/…` and `about:blank`;
   - set `args.Cancel = True` for everything else;
   - optionally open http(s) links in the system browser after checking the scheme. The app has no external links, so plain blocking is enough.

   The internal attribute path is [unverified]: `window.native.webview` vs `window.native.browser.webview`. Inspect it on 6.2.1.
2. Fallback: a `loaded` handler compares `window.get_current_url()` with the origin and reloads the app URL if they differ.
3. The same-origin CSP `form-action 'self'` and the redirect fix in 7.6 close the in-app paths.

### 8.3 Frontend changes (`app.js`, desktop mode only via `<html data-desktop>`)

- **Modified clicks:** add a capture-phase `click` and `auxclick` handler. Ctrl, Shift or middle-click on a same-origin link navigates in place; any other origin is blocked. Today these clicks send the local page to the system browser.
- **File drop:** call `preventDefault` on `dragover` and `drop` at document level unless the target is `input[type=file]`. Otherwise dropping a file replaces the app with a `file:///` page, and there is no Back button.
- **No context menu or browser shortcuts** when debug is off: no right-click copy/paste, F5, Ctrl+F or Ctrl+P. Ctrl+C and Ctrl+V still work. Add a small native menu later if the owner misses Reload, Find or Print.
- These already work unchanged: `confirm` and `alert` (the dialog title shows "127.0.0.1:port says"), `<dialog>`, `showPicker`, `history.pushState`, `sessionStorage`, `navigator.clipboard` (loopback is a secure context), and `<input type=file>` (native Open dialog).

### 8.4 Native dialogs

"Bring in my existing data…" needs a file path. Use `window.create_file_dialog(webview.OPEN_DIALOG, file_types=("Lightning database (*.db)",))` from a **sync `def`** route; Starlette runs those in its threadpool. Never call it from `async def`, which would block the loop. Whether a WinForms dialog opened from a threadpool thread works is [unverified]. The fallback is a text field for the path.

### 8.5 WebView2 Runtime

- **Detect** (`winapi.webview2_version()`): read `pv` under `{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}` at `HKLM\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\`, `HKLM\SOFTWARE\Microsoft\EdgeUpdate\Clients\` and `HKCU\Software\Microsoft\EdgeUpdate\Clients\`. The runtime is present if the value is set, not `0.0.0.0` and at least 86.
- **Also** add an `initialized` event handler that returns `renderer == "edgechromium"`. Returning False cancels the start. Without it, pywebview 6.2.1 silently falls back to MSHTML (IE11) even with `gui="edgechromium"`.
- **When missing:** a message box: "Lightning needs Microsoft Edge WebView2. Install it now?" **Yes** runs the bundled Evergreen bootstrapper `MicrosoftEdgeWebview2Setup.exe /silent /install` (about 2 MB; runs without elevation and installs per user), then asks the user to start Lightning again. **No** opens Microsoft's download page in the system browser. CI checks the bootstrapper's Microsoft Authenticode signature before bundling it.
- **.NET:** pywebview needs .NET Framework 4.6.2 or later, and 6.2 falls back to coreclr if it is missing. Every supported Windows 10/11 has 4.8.
- The Evergreen runtime updates itself but only takes effect on restart. That is fine for a first-party loopback UI.

### 8.6 Privilege

Always run as a standard user. WebView2 cannot run as SYSTEM and should not run elevated. Never use `--uac-admin`, and never tell users to run as administrator.

---

## 9. Outbound network and privacy

### 9.1 Fonts

Bundle the Manrope and Bricolage Grotesque woff2 files (OFL) into `static/fonts`, add `@font-face` rules to `fonts.css`, add their licences to `LICENSE-FONTS.txt`, and delete `base.html:9-11` (the Google preconnects and stylesheet). The window then makes no third-party requests.

### 9.2 Yahoo prices

- **What is sent:** each held ticker (`<code>.CA`), plus month-end date ranges for the historical backfill. No quantities, amounts, account names or ISINs.
- **Where:** `query1.finance.yahoo.com` over verified TLS.
- **Change from today:**
  - Nothing runs before the window opens. The **price worker** starts after unlock.
  - Split the work into `fetch_prices(tickers) → results`, which is HTTP only and runs in daemon threads under an overall deadline, and `apply_prices(container, results)` plus `process_due()`. The apply step runs on the loop thread through `asyncio.run_coroutine_threadsafe`. Capture the loop in the lifespan startup handler.
  - Catch `Exception` inside the workers. Today a mid-read `ConnectionResetError` escapes the narrow except list, skips `process_due()` and leaves queued requests running.
  - Move `process_due()` out of the shared try block.
  - Use a generic User-Agent.
  - Cache misses so the same missing months are not requested on every start.
  - Add a **Refresh prices** button (a POST route that runs the same worker).
- **tzdata:** add it as a dependency and collect its data. Without it, `ZoneInfo("Africa/Cairo")` raises a `KeyError` subclass on Windows. That error is swallowed, and every quote silently becomes `None`.
- **Setting:** "Fetch market prices online", explained on first-run screen 4 and in Settings: "Sends the tickers you hold to Yahoo Finance. Nothing else." The default is on (D9).
- Corporate PAC proxies: urllib ignores PAC, so fetches may fail there while the window works. Log it, and it's acceptable for v1. The `truststore` package (native Windows certificate checks) is an open question.

---

## 10. Packaging (PyInstaller)

### 10.1 Pins (see 11.1 for the lock)

| Package | Pin | Note |
|---|---|---|
| CPython | 3.13.x x64 | D11 |
| pywebview | 6.2.1 | Latest release, 2026-04-15. Only the latest release gets security fixes. |
| pythonnet | 3.1.0 | 3.2.0 came out on 2026-09-29 and is untested with pywebview. Fallback: 3.0.5. |
| pyinstaller / hooks-contrib | 6.22.3 / 2026.8 | 6.22.1 validates the environment inherited by one-file child processes (GHSA-9fxf-4qw3-ghmr). |
| sqlcipher3 | 0.6.2 | Do not also install `sqlcipher3-wheels`, which uses the same import name. |
| cryptography | 50.0.2 | Argon2id, HKDF, AES-GCM |
| fastapi / starlette / uvicorn | 0.141.1 / 1.7.0 / 0.54.0 | Versions tested here. The redirect encoding and form limits depend on Starlette. |
| jinja2 / markupsafe / python-multipart / h11 | 3.1.6 / 3.0.3 / 0.0.32 / 0.16.0 | Declare markupsafe and starlette directly, since they are imported directly. |
| tzdata | latest | Needed on Windows |

### 10.2 Spec essentials (sketch in section 16.6)

- **Entry:** `desktop_main.py` at the repo root. Not `lightning/__main__.py`.
- **Data files:** `collect_data_files("lightning")`. It collects templates, static files and fonts, `migrations/*.sql`, `egx_instruments.csv` and `LICENSE-FONTS.txt`, and skips `.py` and `.pyc`. Add `collect_data_files("tzdata")`. **Never** add the repo-root `data/` folder: on a developer PC it holds the real database.
- **Hidden imports** (a safety net, since hooks-contrib covers uvicorn): `uvicorn.logging`, `uvicorn.loops.asyncio`, `uvicorn.protocols.http.h11_impl`, `uvicorn.lifespan.on`, `python_multipart`, `tzdata`. Pass the app **object** to uvicorn, never a `"module:app"` string.
- **Excludes:** `tkinter`, `PyQt5/6`, `PySide2/6`, `qtpy`, `gi`, `cefpython3`, the `webview.platforms` gtk, qt, cocoa, android and cef backends, `pytest`, `importlinter`.
- **Options:** `console=False`, `upx=False` (UPX can corrupt CFG DLLs; pass `--noupx`), `disable_windowed_traceback=True` (our excepthook logs instead), the icon, and `version=version_info.txt`. The version file's CompanyName and ProductName must match the future signing subject.
- pywebview's own hook collects the WebView2 interop DLLs, and hooks-contrib collects `Python.Runtime.dll` and clr_loader. Check that they are in `_internal\`.
- **Reproducibility:** `PYTHONHASHSEED=1` and `SOURCE_DATE_EPOCH=<tag commit time>`.

### 10.3 One-folder first (M8)

`dist\Lightning\Lightning.exe` plus `_internal\`. It starts faster, extracts nothing to `%TEMP%`, and every DLL and `.pyd` can be signed.

### 10.4 One-file (M9, the Luna deliverable)

The same spec with `EXE(pyz, a.scripts, a.binaries, a.datas, …)` and no `COLLECT`. Known costs:

- Every launch extracts to `%TEMP%\_MEIxxxxxx`, so startup is slower (the owner accepted this). If the process is killed, the folder is left behind.
- The extracted `.pyd`/`.dll` files cannot be signed individually after the build.
- Self-extraction is a common antivirus heuristic.
- Never run it as administrator.

None of this touches user data, because the data lives in `%LOCALAPPDATA%\Lightning`.

### 10.5 Plan B: per-user installer (M10, optional)

Inno Setup around the one-folder build:

- `PrivilegesRequired=lowest`, which maps `{autopf}` to `%LOCALAPPDATA%\Programs` with no UAC prompt.
- `ArchitecturesAllowed=x64compatible` and a fixed `AppId`.
- A WebView2 check and bootstrapper in the `[Code]` section.
- `CloseApplications` during upgrades.
- The launch checkbox starts the app de-elevated (`runasoriginaluser`).
- User data sits outside `{app}`, so uninstalling never touches it.
- Inno's licence asks for a paid licence above $5k of commercial revenue.

---

## 11. Supply chain, signing, release and CI

### 11.1 Dependencies

- **One source of truth:**
  - `pyproject.toml` gets a `[build-system]` table, package-data, `dynamic = ["version"]` read from `lightning.__version__`, and runtime and dev dependency groups.
  - `requirements/*.in` generate hash-locked `requirements/*.lock` files (`uv pip compile --generate-hashes`, or `pip-compile --generate-hashes`): `dev-linux.lock`, `dev-win.lock` and `build-win.lock` (runtime plus pywebview, pythonnet, clr_loader, bottle, proxy_tools, pyinstaller and hooks-contrib).
- Install with `pip install --require-hashes --only-binary :all: -r …lock`.
- `run.bat`/`run.sh` install from the lock, only when it changes, and stop with a visible message on failure. Today they `pip install` unpinned packages on every launch.
- Run `pip-audit` in CI.
- Licence notices ship with the exe: SQLCipher (BSD), OpenSSL (Apache-2.0), pywebview (BSD), pythonnet (MIT), Python (PSF), and the fonts (OFL).

### 11.2 Signing (M10)

- **Unsigned** (v1 default): SmartScreen shows "Windows protected your PC". The user clicks **More info → Run anyway**. **Smart App Control** (on by default on clean Windows 11 installs) blocks unknown unsigned apps outright. Test both (M9).
- **When signing:**
  - Use an RSA certificate; Smart App Control does not accept ECC.
  - Sign `Lightning.exe` **and** every unsigned `.dll`/`.pyd` in the one-folder build, then `setup.exe` and the uninstaller.
  - `signtool sign /fd sha256 /tr <RFC3161> /td sha256`.
  - Fail the build if `signtool verify /pa /v` shows no timestamp.
  - Sign before hashing or packaging.
- **Options:**
  - Azure Artifact Signing: $9.99 a month. Individuals only in the US and Canada; organizations in the US, Canada, EU, UK and a few more, with 3+ years of history.
  - An OV certificate: about $150–300 a year, with the key on an HSM or cloud KMS (a PFX in GitHub secrets is no longer allowed).
  - EV: no SmartScreen advantage since 2024.
  - Whichever is chosen, reputation builds over weeks, so sign every release with the same identity.

### 11.3 CI (`.github/workflows/windows-build.yml`)

- Run tests on `ubuntu-latest` for every push, and the Windows build on tags and manual dispatch.
- Pin `runs-on: windows-2025`, not `windows-latest`, which migrates silently.
- Pin every action to a full commit SHA (`actions/checkout`, `actions/setup-python`, `actions/upload-artifact`).
- Top-level `permissions: contents: read`. Later, the signing job gets `id-token: write` inside a protected `release` environment.
- **Steps:**
  1. setup-python 3.13
  2. `pip install --require-hashes -r requirements/build-win.lock`
  3. the full pytest suite on Windows (this exercises the Windows sqlcipher3 wheel)
  4. `lint-imports`
  5. generate `version_info.txt`
  6. download the WebView2 bootstrapper and check its Authenticode signer is Microsoft
  7. `pyinstaller packaging/lightning-onedir.spec`
  8. `dist\Lightning\Lightning.exe --self-check`
  9. the one-file spec, then `Lightning.exe --self-check`
  10. `Get-FileHash -Algorithm SHA256` → `SHA256SUMS`
  11. upload the artifacts
- The repo is **private**. Release assets can't be downloaded anonymously, and artifact attestations need a public repo or Enterprise Cloud. For personal use, download while signed in. Publishing for others would need a public releases repo or site.

### 11.4 Updates

None in v1. Any future updater must verify signed metadata offline before replacing anything, with rollback, freeze and size protection (the TUF threat classes). tufup is the maintained option, since PyUpdater is archived. Never use `as_admin`. Never expose update functions through pywebview.

---

## 12. Milestones with acceptance tests

Milestones M0 to M6 can be built and tested on Linux, which is how this repo is developed. M7 is partly Linux. M8 and M9 need Windows. After each milestone, run the full suite, `lint-imports` and `git diff --check`, update the CHANGELOG, and push, as the repo rules require.

| M | What | Size |
|---|---|---|
| M0 | Repo hygiene, pins, version | S |
| M1 | Paths, logging, guards | M |
| M2 | Local server security | M |
| M3 | Offline fonts and CSP | M |
| M4 | Encryption engine | M |
| M5 | Keys, unlock, first run, backups, import | L |
| M6 | Startup reorder and background prices | M |
| M7 | Desktop shell | M |
| M8 | One-folder build on Windows | M |
| M9 | One-file build and clean-PC validation | M |
| M10 | Optional: installer, signing, release | M |

### M0 · Repo hygiene, pins, version

- `git rm nul`. It is a reserved device name, so Git for Windows cannot check out the repo. Add `nul` to `.gitignore`.
- Remove `Claude outputs/lightning-update.zip`, a stale 0.1.0 snapshot whose folder name contains a space.
- Add `build/` and `dist/` to `.gitignore`.
- Make `__version__` the single source and set it to 0.4.0. pyproject reads it dynamically.
- Add the `requirements/*.in` and `*.lock` files (section 11.1). Add `tzdata`, `sqlcipher3`, `cryptography`, and `pywebview` with `pythonnet` (win32 only).
- **Accept when:** a Windows `git clone` works; `pip install --require-hashes` succeeds on Linux and Windows; `python -c "import lightning; print(lightning.__version__)"` matches the package metadata.

### M1 · Paths, logging, guards

- Build `core/paths.py` and `core/logs.py` (sections 4.1 and 5.1).
- Resolve `--db`, and ignore `LIGHTNING_TODAY` when frozen.
- Add the migration-list and downgrade guards (5.5) and the resource self-check.
- Replace `print` diagnostics with logging (7.8).
- **Tests:**
  - `data_dir()` for frozen and source runs on each OS (monkeypatch `sys.frozen`, `sys._MEIPASS` and the environment). It is never under `_MEIPASS` or the code folder.
  - Startup with `sys.stdout = sys.stderr = None` builds the app and serves one request.
  - An empty migrations folder stops the app with a clear message.
  - A database whose version is higher than the bundled maximum is refused.
  - Every log line written during a scripted session is free of amounts, names and query strings.

### M2 · Local server security

- Build `ui/security.py`: HostGuard, SessionGuard with `/__launch`, FetchMetadata, LockGate (in pass-through mode until M5) and SecurityHeaders (with `Report-Only` CSP until M3).
- Apply `safe_local_path()` everywhere.
- Move `testserver` into the tests.
- Add the upload limits and the generic error handler.
- Remove the unauthenticated `/__health` probe.
- Test fixture: a `client` that runs the launch exchange once. The TestClient uses `base_url="http://127.0.0.1:8765"` and sends `sec-fetch-site: same-origin` by default. Tests that build their own TestClient (for example `test_product_shell.py`) move to the fixture.
- **Tests:**
  - No cookie → 403 on `/`, on a POST and on `/static/app.js`.
  - Wrong cookie → 403.
  - The launch code works once, a reused code fails, and a code older than 30 s fails.
  - `Host: evil.com`, `Host: localhost:<port>` and `Host: testserver` → 400.
  - POST with `Sec-Fetch-Site: cross-site` or `same-site` → 403.
  - POST with no Fetch Metadata and `Origin: null`, a foreign Origin or no Origin → 403.
  - Every header in 7.5 is present, and `Cache-Control` is `no-store` on HTML.
  - The redirect cases in 7.6.
  - An upload over 6 MB → 413 before parsing.
  - A 2 MB statement goes through upload → map → confirm.
  - A CSV import with `<img src=x onerror=alert(1)>` and `"><script>` in every column renders escaped on the register, preview and popup pages.

### M3 · Offline fonts and CSP

- Bundle the fonts and remove the Google link (9.1).
- Move the inline scripts and `on*` handlers into `app.js` (7.5) and enforce the CSP.
- **Tests:**
  - A grep test finds no `<script>` without `src`, no `on[a-z]+=` attribute and no `https://` URL in the templates.
  - A Playwright pass (Chromium is preinstalled) over every page with a populated demo shows no CSP violations and no console errors.
  - The popup form scripts now work: the plan-item kind switcher works inside the popup.

### M4 · Encryption engine

- Apply and extend `reference/encryption_prototype.patch`: `driver.py`, `connection.py` (key, the pragmas of 5.4, the registry and `close_all()`), `backup.py` (5.3), `migrator.py`, `reserves.py`, the four repositories and `encrypt.py`.
- For now, `build(db_path, key=…)` takes a `KeyHolder`, and tests use `TEST_KEY = bytes(range(32))`. A raw key keeps the suite at about 44 s instead of about 113 s.
- **Tests:**
  - After a full suite run, no `.db` or backup file under `tmp_path` starts with `SQLite format 3\0`, and stdlib `sqlite3` fails to read them.
  - A wrong key raises `WrongKeyError`.
  - A plaintext database with plaintext backups converts with equal row counts, and no plaintext sidecar is left.
  - A second active emergency fund still raises `ConflictError`. This path has no test today.
  - The demo uses a throwaway key.
  - A backup reopens with the key, and its name carries the key tag.
  - A failed backup leaves no `.partial` file.
  - `quick_check` failure → no backup and no pruning.
  - A pruning `PermissionError` does not stop the app from starting.

### M5 · Keys, unlock, first run, backups, import

- Build `security/` (recovery, slots, DPAPI, secret), `Session` and LockGate (now active), `ui/routes/unlock.py`, the screens in 6.6, the Settings Security and Backups tabs, restore, the legacy import in 5.2, and rekey. Use the brand guide for every screen.
- **Tests:**
  - Recovery key round trip. Case, space and hyphen tolerance. O/I/L mapping. A one-character typo is detected (one in 4096 slips through).
  - HKDF and key_id against fixed vectors.
  - Password slot: wrap and unwrap; a wrong password raises `InvalidTag`, shown as "Wrong password".
  - Password mode deletes the DPAPI slot.
  - DPAPI is mocked off Windows. On Windows CI, a real protect/unprotect round trip.
  - A DPAPI failure leads to `recover`, and nothing is deleted.
  - `keys.json` is written atomically: a crash simulated between the temp write and the replace leaves the old file intact.
  - Rekey re-encrypts the live database and every local backup, and the old key then fails on all of them.
  - Restore round trip.
  - Legacy import: equal counts, the original untouched until the user confirms, and the conversion refused when the integrity check fails.
  - Lock: all connections are closed (the registry is empty), the key bytes are zero, and every route redirects to `/unlock`.

### M6 · Startup reorder and background prices

- Split fetch from apply (9.2), add the worker, the setting, the **Refresh prices** button, the generic User-Agent, the miss cache and the catch-all in the workers.
- **Tests:**
  - With the network mocked to hang, the server answers within 1 s of start.
  - A mocked `ConnectionResetError` during a read still lets `process_due()` run.
  - With the setting off, no request leaves the process (a socket monkeypatch fails the test on any connect).
  - Results arriving after a lock are discarded.

### M7 · Desktop shell

- Build `lightning/desktop/*` (sections 4.1, 8 and 16). Add the frontend guards in 8.3.
- Linux-testable parts: the server thread starts on a pre-bound port and stops within 5 s of `should_exit`; the instance lock refuses a second holder; the startup order with pywebview mocked; `--self-check`.
- Windows manual checks (write a script in `packaging/SMOKE.md`):
  - the window opens on the Overview with no console;
  - Ctrl-click and middle-click stay in the window;
  - dropping a CSV outside the input does nothing;
  - `Ctrl+Shift+I` and F12 do nothing;
  - both downloads show a Save dialog;
  - a second launch focuses the first window;
  - closing the window leaves no `Lightning.exe` in Task Manager;
  - the navigation guard blocks `/\evil.com` if it is forced through `evaluate_js("location='/\\\\evil.com'")`.

### M8 · One-folder build on Windows

- Add the spec (10.2) and the CI job (11.3) up to the one-folder `--self-check`.
- **Accept when:**
  - CI is green;
  - `_internal` holds `Python.Runtime.dll`, the WebView2 interop DLLs, `sqlcipher3\_sqlite3*.pyd`, the tzdata zone files, the migrations, templates, static files, fonts and CSV;
  - there is no `data\` folder in the bundle;
  - the M7 manual checks pass on the one-folder build.

### M9 · One-file build and clean-PC validation

Build the one-file exe, then run this checklist on a **clean** Windows 11 VM (Smart App Control on and off) and a Windows 10 22H2 VM.

- [ ] First launch: SmartScreen behaviour noted (unsigned). With Smart App Control on, note whether it is blocked.
- [ ] WebView2 removed or blocked: the message box and the install path work, and the app never falls back to IE.
- [ ] First run: start fresh → recovery key → confirm → auto-unlock. Restart opens with no prompt.
- [ ] Bring in the existing data from a source checkout's `data\lightning.db` with backups. Counts match. The originals are untouched until the user confirms.
- [ ] Every workflow from ARCHITECTURE.md's smoke list: accounts, post, edit, restore, CSV import (a 2 MB statement), budget, reserve, investment, restart, restore a backup, second launch.
- [ ] Copy `lightning.db` and a backup to another PC or account: DB Browser for SQLite (plain) refuses them. Lightning with the recovery key opens the backup.
- [ ] Password mode: prompt at start, idle lock after the set minutes, Lock now, a wrong password, recovery-key fallback.
- [ ] Offline launch: the window appears at once, and the price refresh fails quietly and is logged.
- [ ] Kill `Lightning.exe` in Task Manager during a save, then relaunch: no corruption (`quick_check` ok). A stale `_MEI*` folder in `%TEMP%` is noted.
- [ ] From another Windows account on the same PC, `curl http://127.0.0.1:<port>/` gets 403. Read the port from `netstat -ano`.
- [ ] `%TEMP%` after a session: no leftover WebView2 profile folder. If there is one, delete it on close.
- [ ] Log file: no amounts, names or tickers.
- [ ] Startup time noted for one-file vs one-folder.

### M10 · Optional: installer, signing, release

Inno Setup per 10.5, signing per 11.2, `SHA256SUMS`, and a release page.

---

## 13. Never do this

- Pass `storage_path` to pywebview 6.2.1 while `private_mode=True`: the folder is rmtree'd on exit.
- Ship `debug=True`, set `REMOTE_DEBUGGING_PORT`, pass `ssl=True` or set `IGNORE_SSL_ERRORS` (which accepts every certificate for every site), or add a `js_api`.
- Use `webview.token` as the server credential, or put the session token in HTML, JS, logs or on disk.
- Send `Referrer-Policy: no-referrer` (it breaks every save), or accept `Sec-Fetch-Site: same-site`.
- Open a plaintext file as the live database, pass an empty key to `ATTACH … KEY`, build `PRAGMA key` from a user string, or set `temp_store=FILE`.
- Store the recovery key on the PC, keep a DPAPI slot next to a password slot, or use `CRYPTPROTECT_LOCAL_MACHINE`.
- Delete or move a user's plaintext database without an explicit confirmation.
- Bundle the repo-root `data/` folder, use UPX, set `--uac-admin`, or run the app elevated.
- Call `create_file_dialog` from an `async def` route, or do shutdown work inside the `closing` event.
- Log query strings, form values, amounts, names, tickers, file contents, tokens or key material.
- Keep the fixed-port `/__health` probe as the single-instance check.

---

## 14. Risks and open questions

| # | Risk or question | Default or mitigation |
|---|---|---|
| R1 | An unsigned one-file exe is blocked by Smart App Control on clean Windows 11, and SmartScreen warns everywhere. | Test in M9. If it is blocked on the owner's PC, either turn Smart App Control off (it can't be turned back on without a reinstall, so it is the owner's call) or move to signing (M10). |
| R2 | The pywebview navigation hook uses internal attributes. | Fallback `loaded` check plus the CSP and redirect fixes. Verify in M7. |
| R3 | `pythonnet` 3.1.0 and pywebview 6.2.1 on Python 3.13 are untested together. | Test in M8 CI. Fallback: pythonnet 3.0.5, or Python 3.12. |
| R4 | sqlcipher3 has one maintainer and bundles SQLCipher 4.12 while upstream is at 4.19. | Stay on the SQLCipher 4 format so a switch to SQLite3 Multiple Ciphers needs no data migration (6.2). |
| R5 | `create_file_dialog` from a threadpool thread on WinForms. | Path text field as fallback (8.4). |
| R6 | The WebView2 private-mode temp folder may be left in `%TEMP%`. | Check in M9 and delete it on close if so. |
| R7 | Losing both the DPAPI slot and the recovery key loses the data. | The first run forces a confirmation, Settings offers "Test recovery key", and a reminder comes every 6 months. |
| Q1 | Does the owner want market prices **off** by default? | On, with disclosure (D9). |
| Q2 | Will the database still be shared between two PCs through OneDrive? | C' supports it (recovery key once per PC), but a live SQLite file over sync risks corruption. Recommend the backup mirror instead. |
| Q3 | Should the password slot also go inside backups (open a backup with the password on a new PC)? | No. A stolen backup then stays a 128-bit problem. |
| Q4 | Should `bank_import_rows.raw_json` keep every original CSV column forever? | Unchanged for now. It is encrypted, but it's a retention decision for the owner. |
| Q5 | Windows ARM64 or 32-bit? | x64 only in v1. sqlcipher3 publishes the other wheels. |
| Q6 | Windows Hello/TPM unlock, or lock when Windows locks? | v2. |
| Q7 | Who is the legal publisher (individual or company, and which country)? | Decides the signing route (11.2). |

---

## 15. Evidence levels

| Level | Meaning | Examples |
|---|---|---|
| **Tested in sandbox (Linux)** | Run by the research agents on this repo or a scratch clone. | uvicorn crash with `stdout=None`; the missing-migrations behaviour; Host/Origin probes (400/403/303); the `/\evil.com` Back link; XSS payloads escaped on 13 pages; the 1 MB form-part limit (an 865 KB CSV gets 400); the sqlcipher3 swap (298 tests pass, all 4 contracts hold); conversion with verification; wrong key; unkeyed backup fails; VACUUM INTO encrypted; rekey in WAL; KDF timings (143–150 ms passphrase, 0.1 ms raw); Argon2id at 0.43 s; `cache_size` effect; PyInstaller one-folder freeze of sqlcipher3 on Linux. |
| **Read from source** | Upstream source or docs read at a pinned tag, but not run on Windows. | pywebview 6.2.1 threading, settings defaults, bridge injection, the rmtree bug and the MSHTML fallback; uvicorn thread and `started` behaviour; WebView2 registry detection and distribution; PyInstaller one-file and one-folder behaviour; Inno Setup directives; signing rules; GitHub Actions hardening. |
| **Unverified** | Needs a Windows run. | Everything in M7–M9. In particular: the NavigationStarting hook; DPAPI through ctypes; the sqlcipher3 Windows wheel inside a frozen exe; Smart App Control on unsigned one-file; `window.print()` and Save dialogs with debug off; `create_file_dialog` from the threadpool; Secure cookies over `http://127.0.0.1`. |

Several official sites were blocked by the sandbox proxy (listed in the [work log](WORK_LOG.md)). Their content was read from the same docs' GitHub source repositories, so the rendered pages may differ slightly.

---

## 16. Appendix: code sketches (untested)

These show the shape and the order of calls. They are not drop-in code.

### 16.1 Desktop entry (`lightning/desktop/app.py`)

```python
def run(argv: list[str] | None = None) -> int:
    logs.install()                                   # step 1: before anything can print
    multiprocessing.freeze_support()
    args = parse_args(argv)                          # --self-check, --demo (hidden)
    data = paths.data_dir(demo=args.demo)
    lock = instance.acquire(data)
    if lock is None:
        winapi.focus_window("Lightning")
        return 0
    try:
        problems = preflight(data)                   # WebView2, cipher_version, resources, tz
        if args.self_check:
            return 0 if not problems and self_test_encrypted_db() else 1
        if problems:
            winapi.message_box(problems.text(logs.path()))
            return 1
        session = Session.open(data, demo=args.demo) # setup / locked / recover / ready (DPAPI tried here)
        security = SecurityConfig.new()              # token + one-time launch code
        server = LocalServer.start(create_app(session, security))   # pre-bound 127.0.0.1:0
        window = open_window(f"{server.origin}/__launch?code={security.launch_code}", server.origin)
        window.events.shown += lambda: prices.start_if_enabled(session, server.loop)
        webview.start(gui="edgechromium", debug=False, private_mode=True)
        return 0
    finally:
        session.lock() if "session" in locals() else None
        server.stop(timeout=5) if "server" in locals() else None
        lock.release()
        logs.flush()
```

### 16.2 Server thread (`lightning/desktop/server.py`)

```python
class LocalServer:
    @classmethod
    def start(cls, app) -> "LocalServer":
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        config = uvicorn.Config(app, log_config=None, access_log=False, http="h11", loop="asyncio",
                                ws="none", lifespan="on", server_header=False, date_header=False)
        server = uvicorn.Server(config)
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True, name="server")
        thread.start()
        deadline = time.monotonic() + 10
        while not server.started:
            if not thread.is_alive() or time.monotonic() > deadline:
                raise StartupError("The local server did not start.")   # bind/lifespan failure → sys.exit in thread
            time.sleep(0.05)
        return cls(server, thread, port)

    def stop(self, timeout: float) -> None:
        self.server.should_exit = True
        self.thread.join(timeout)
```

### 16.3 Security middleware (`lightning/ui/security.py`)

```python
EXEMPT_LOCKED = ("/__launch", "/setup", "/unlock", "/recover", "/lock", "/static/")

class Guard:
    """Pure ASGI middleware: Host → session cookie → Fetch Metadata → lock gate; adds headers."""
    def __init__(self, app, cfg: SecurityConfig, session: Session): ...

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        req = Request(scope)
        if req.headers.get("host") != self.cfg.host:                      # "127.0.0.1:<port>"
            return await PlainTextResponse("Bad host", 400)(scope, receive, send)
        if req.url.path == "/__launch":
            return await self.launch(req)(scope, receive, send)           # one-time code → cookie, 303 /
        if not hmac.compare_digest(req.cookies.get("lightning_session", ""), self.cfg.token):
            return await PlainTextResponse("Forbidden", 403)(scope, receive, send)
        site = req.headers.get("sec-fetch-site")
        if req.method not in ("GET", "HEAD"):
            ok = site == "same-origin" if site else req.headers.get("origin") == self.cfg.origin
        else:
            ok = site in (None, "same-origin", "none")
        if not ok:
            return await PlainTextResponse("Forbidden", 403)(scope, receive, send)
        if self.session.state != "ready" and not req.url.path.startswith(EXEMPT_LOCKED):
            return await self.to_state_page(req)(scope, receive, send)
        await self.app(scope, receive, self.with_headers(send, static=req.url.path.startswith("/static/")))
```

### 16.4 `safe_local_path`

```python
_ALLOWED = re.compile(r"^/[A-Za-z0-9/_\-.~%?=&+,:]*$")

def safe_local_path(value: str | None, default: str) -> str:
    if not value or any(ch == "\\" or ord(ch) < 0x20 or ord(ch) == 0x7F for ch in value):
        return default
    parts = urlsplit(value)
    if parts.scheme or parts.netloc or not value.startswith("/") or value.startswith("//"):
        return default
    return value if _ALLOWED.match(value) else default
```

### 16.5 WebView2 detection and navigation guard

```python
GUID = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
KEYS = [(winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{GUID}"),
        (winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\Microsoft\EdgeUpdate\Clients\{GUID}"),
        (winreg.HKEY_CURRENT_USER, rf"Software\Microsoft\EdgeUpdate\Clients\{GUID}")]

def webview2_version() -> tuple[int, ...] | None:
    for hive, path in KEYS:
        try:
            with winreg.OpenKey(hive, path) as key:
                pv, _ = winreg.QueryValueEx(key, "pv")
        except OSError:
            continue
        version = tuple(int(p) for p in str(pv).split(".") if p.isdigit())
        if version and version > (0, 0, 0, 0):
            return version
    return None

def attach_navigation_guard(window, origin: str) -> None:
    def on_before_show():
        control = getattr(window.native, "webview", None) or window.native.browser.webview   # [unverified]
        def starting(sender, args):
            uri = str(args.Uri)
            if not (uri.startswith(origin + "/") or uri == "about:blank"):
                args.Cancel = True
        control.NavigationStarting += starting
    window.events.before_show += on_before_show
    window.events.initialized += lambda renderer: renderer == "edgechromium"   # False aborts start()
```

### 16.6 PyInstaller one-folder spec (`packaging/lightning-onedir.spec`)

```python
from PyInstaller.utils.hooks import collect_data_files
datas = collect_data_files("lightning") + collect_data_files("tzdata")
datas += [("MicrosoftEdgeWebview2Setup.exe", ".")]                     # fetched + signature-checked in CI
a = Analysis(["../desktop_main.py"], pathex=[".."], datas=datas,
             hiddenimports=["uvicorn.logging", "uvicorn.loops.asyncio", "uvicorn.protocols.http.h11_impl",
                            "uvicorn.lifespan.on", "python_multipart", "tzdata"],
             excludes=["tkinter", "PyQt5", "PyQt6", "PySide2", "PySide6", "qtpy", "gi", "cefpython3",
                       "webview.platforms.gtk", "webview.platforms.qt", "webview.platforms.cocoa",
                       "webview.platforms.android", "webview.platforms.cef", "pytest", "importlinter"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Lightning", console=False, upx=False,
          icon="lightning.ico", version="version_info.txt", disable_windowed_traceback=True)
coll = COLLECT(exe, a.binaries, a.datas, upx=False, name="Lightning")
# One-file variant: EXE(pyz, a.scripts, a.binaries, a.datas, name="Lightning", console=False, upx=False, ...)
#                   and no COLLECT.
```

### 16.7 Recovery key and slots

See `reference/keyvault_sketch.py` for the Crockford encoding with checksum, the HKDF data key, key_id, the Argon2id + AES-GCM password slot, ctypes DPAPI and wipe. It runs on Linux except for the DPAPI part, which was never run.
