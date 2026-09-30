# Desktop architecture review and implementation plan

Reviewed 2026-09-30. Planning and isolated verification only; desktop implementation has not started.

## Recommendation and scope

Keep FastAPI, Jinja, the existing UI and financial services. Add a thin Windows pywebview/WebView2 shell. Ship a PyInstaller **one-folder ZIP** containing `Lightning.exe` and its dependencies. Keep the Linux browser launcher as a supported way to use and test the same application. No frontend rewrite or separate financial implementation is needed.

This document amends [BUILD_SPEC.md](BUILD_SPEC.md). Its requirements supersede conflicting defaults and sketches there; the draft remains useful reference material, not executable instructions. In particular, D2, the one-file definition of done, M9 and the shutdown/restore/rekey sketches change below. Prior work-log claims are distinguished from verification in this review.

The owner's current instructions allow architecture changes and verification, and defer building until review is complete. References to automatically pushing, deleting old artifacts or publishing in the original draft do not authorize those actions during this review.

## Downloads, updates and persistent data

Release layout:

```text
Downloaded / extracted program (replaceable)
  Lightning-<version>-windows-x64/
    Lightning.exe
    _internal/
    README.txt + third-party notices

Windows / Linux user data (retained across releases; owner-amended default)
  <actual Documents folder>/Lightning/
    Personal_2026-10-01_001_a1b2c3d4/
      Personal_2026-10-01_001_a1b2c3d4.db
      keys.json
      instance.lock
      backups/

Explicitly selected external database
  <chosen folder>/chosen.db
  <chosen folder>/.chosen.db.lightning/
    keys.json
    backups/
    instance.lock
```

**Owner amendment during implementation:** use Documents → Lightning as the
default, offer an explicit location/database chooser, and support multiple named
profiles. Resolve Windows Documents through its known-folder API (including
redirection); Linux follows `XDG_DOCUMENTS_DIR`, falling back to `~/Documents`.
Do not silently move or convert existing files. Until the new launcher/profile
chooser is integrated, the legacy browser launcher retains its existing path.

Startup discovery means finding saved databases/profiles and backups, **not app
update checks**. Scan only the Lightning container or a user-selected folder,
not all Documents recursively. Present profiles and backups separately; never
automatically restore the newest-looking file. The user selects what to open.
Multiple finance accounts remain inside each independently encrypted profile.

Use human-readable filenames with a name, UTC date, sequence and short ID:
`Personal_2026-10-01_001_a1b2c3d4.db`. The creation identity stays stable across
saves and app updates. Backups append `_backup_<date>_<sequence>_<id>.db` to the
database stem; protected pre-upgrade copies use `_upgrade_` instead. Backups keep
their original schema records inside the encrypted snapshot. Readable filenames
do not imply readable financial contents. Keys/locks stay in the profile folder.

Documents may be cloud-synced. This is not a multi-computer synchronization
feature: local instance locks do not coordinate separate PCs through OneDrive.
Do not open a synced live database on multiple computers; prefer a non-synced
chosen folder for active use and transfer completed encrypted backups instead.
Warn about this in the upcoming chooser. Existing hardlinked DB paths are
unsupported because path-based locks cannot safely identify every hardlink.

Windows end users need neither Python nor Git. WebView2 remains a prerequisite; the app detects it and offers the official install path. The small bootstrapper needs internet. For a completely offline first installation, provide Microsoft's standalone runtime installer separately. Do not confuse offline everyday operation with offline runtime installation. [PyInstaller distribution](https://pyinstaller.org/en/stable/operating-mode.html), [Microsoft WebView2 distribution](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution).

Recommended user update instructions:

1. Close Lightning and wait for it to exit.
2. Extract the new ZIP into a fresh folder. Do not merge its contents into the old folder or replace only the EXE; dependencies can change.
3. Launch the new `Lightning.exe`. It opens the existing user-data location. Show the running version and an “Open data folder” action in Settings.
4. Keep the old program folder until the new version opens successfully. Update shortcuts if the path changed. Then the old program folder can be removed without touching user data.

Before pending schema migrations, create and verify an encrypted backup, record its schema version and retain it outside normal pruning. Abort migration if this backup fails. An old executable must refuse a newer schema **before making any write**. Program rollback is safe only when the schema is compatible; otherwise recovery requires the matching pre-upgrade database backup. Explain that restoring it discards later changes. Never promise that swapping the EXE alone reverses a database migration.

Release ZIPs must contain no real databases, backups, keys, logs, build secrets or local `.venv`. Include the version, tested OS, release notes and SHA-256 checksum. Checksums detect damage; they do not replace publisher signing. A “Download updates” action may open a fixed releases URL in the system browser; no background updater is needed in v1.

An unsigned ZIP is adequate for a controlled pilot only if tested on the recipients' PCs. Download reputation warnings and Smart App Control can prevent a smooth launch; ZIP packaging does not bypass them. Do not make disabling Windows protections the normal installation procedure. Broader distribution may require signing. [Microsoft Smart App Control](https://learn.microsoft.com/en-us/windows/apps/develop/smart-app-control/overview).

**Owner decision: Windows-first beta for a few selected testers; the owner will host the ZIP on their website.** The private source repository can remain private. Prepare the ZIP, checksum and release notes for that handoff. If downloads must be restricted technically, the website needs authentication or a controlled download mechanism; an unlisted URL alone does not provide access control. Website publishing is a later owner action, not part of this review.

## Linux support and shared architecture

The Windows executable does not run natively on Linux. pywebview itself supports Linux with Qt or GTK, but that adds another renderer, native dependencies and a separate validation matrix. Defer a packaged Linux window. Preserve `python -m lightning` / `run.sh` for Linux and use the same services, encrypted database format, migrations, security middleware and pages as Windows. [pywebview installation](https://pywebview.flowrl.com/guide/installation.html).

Common runtime owns configuration, paths, instance lock, session state, app construction and background jobs. The Windows launcher owns only platform/window integration. Browser mode must not import pywebview, pythonnet, WinForms, winreg or DPAPI at import time. Put Windows dependencies in an optional platform-specific group, and keep platform adapters behind small interfaces. Native file selection is an injected shell capability; UI routes must not import the desktop package and reverse the import layers.

**Owner decision: ask for a password on both Windows and Linux.** Use the same Argon2id/AES-GCM password slot on both. Defer DPAPI and automatic unlock entirely from v1. Copying an encrypted backup between operating systems uses the recovery key to open it and creates a local password slot on the destination. Do not synchronize a live DB or casually replace one PC's `keys.json` with another's. Recovery keys and local unlock settings serve different purposes.

Use separate real/demo profiles and locks, with a stable data location independent of working directory, checkout or app version. Resolve `--db` to a canonical database path and derive its lock/keys/backup profile consistently; two aliases for the same DB must not evade the instance lock. Preserve explicit legacy import rather than silently changing which database the user sees.

Linux browser testing covers business behavior and web UI, not Windows window events, downloads, DPAPI, packaging or shutdown. A Windows runner builds Windows artifacts; PyInstaller is OS-specific. A real Windows PC/VM interactive smoke pass remains a release gate.

## Required corrections to the draft

### 1. Own database access and lifecycle on one thread

The draft says the server event loop owns all database work, but builds/unlocks the session before starting that thread and closes it from the GUI main thread before stopping requests. Replace this with one ownership rule:

- Create/open/migrate/seed and close the database on the ASGI runtime's owning thread. The GUI passes commands through a thread-safe runtime interface. Network workers return data only.
- Start the runtime with a setup/locked session; initialize DB state in its lifespan/commands. Binding a socket and holding the instance lock precede DB work.
- On lock, restore or shutdown: stop admitting database operations, invalidate the session generation, cancel/discard pending worker results and drain active operations. Only then close connections and wipe key holders on their owning thread.
- On shutdown, request graceful server exit, let lifespan cleanup close the database after request draining, join the server and release the instance lock last. A timeout is a reported failure, not routine `os._exit(0)` success.
- Re-check state/generation after awaits: a POST can pass middleware, await form parsing, then resume after another task locked the app. Middleware alone is insufficient; the operation gate protects the actual service call.

Keep this a small runtime/session component, not a new service architecture. Crypto derivation may run in a worker to keep the loop responsive, but workers must not receive the container or database connection.

### 2. Make migration bookkeeping atomic

Current `database/migrator.py` commits migration SQL before writing its `schema_migrations` record. A crash can leave applied SQL without its recorded version. Ad hoc duplicate-column handling is not a general recovery mechanism.

Commit each migration and its version record together, with deliberate handling for optional migrations and SQLite `executescript` transaction behavior. Validate the migration manifest and maximum schema version before backup/seed/migration writes. Add crash/retry tests for table creation and representative ALTER migrations. A missing resource bundle must fail visibly.

### 3. Treat import and restore as staged operations

The reference encryption patch is **not safe to apply wholesale**: `build()` calls `encrypt_existing()`, which converts existing plaintext files in place. That conflicts with the draft's explicit copy-and-confirm import requirement. Reuse only reviewed driver/connection pieces.

Legacy import must require the old app to be closed, obtain a consistent SQLite snapshot without discarding WAL/journal contents, and preserve the source and its backups. Validate schema objects, row counts, foreign keys and application financial invariants as well as integrity checks. Work in a staging file under the destination profile. Promote only verified output; interrupted staging must be recognized on restart.

Restore must validate the candidate/key/schema before changing the live file, quiesce operations, and create a verified pre-restore backup while the live connection is usable. Stage a destination copy on the same filesystem, close all live handles, then atomically replace. Retain recovery material through successful reopen/migration. Do not copy bytes directly over the live file.

For a backup using another recovery key, prefer exporting the validated restored content into a staged DB encrypted with this profile's current key. This avoids an unnecessary multi-file DB/`keys.json` swap. Initial recovery of an existing database with missing keys is a separate flow: verify the supplied recovery key against the DB before writing a new slot.

### 4. Narrow the first encryption release

Retain encryption, encrypted backups, recovery-key setup, recovery restore and password unlock on both platforms. Defer the “create a new recovery key” feature and automatic rewriting of every backup/mirror. The proposed sequence (rekey live DB, rewrite backups, update `keys.json`) has a crash gap and can destroy the only matching key state.

A later rotation feature needs a recoverable multi-file commit protocol, protected transition key material, verified staged copies, interruption tests at every boundary and explicit handling of disconnected mirrors. Retaining old backups with their old key identifiers is preferable to silently rewriting backup history. This deferral does not remove ordinary password changes, which only rewrap the same data key.

Prototype corrections before reuse: actually inspect the result of `quick_check`, clean up failed partial backups, run cipher integrity validation, and prove wrong-key rejection by reading the schema. Do not treat a non-SQLite header as proof of correct encryption. Full key identifiers belong in verified metadata; a four-hex filename tag is only a display hint and can collide.

Validate `keys.json` type/version/lengths and impose upper bounds on Argon2 memory/time/parallelism before deriving a key. Authenticate canonical metadata, including slot parameters, using AEAD associated data. Test altered metadata and oversized values. Distinguish wrong-key/corrupt-file failure from a confidently diagnosed password typo. If DPAPI is added later, define ctypes signatures explicitly and test it on Windows; mocked tests cannot establish ABI correctness.

Describe the threat model accurately: a DB-only backup needs the recovery key, but someone who obtains both the DB and its password slot can attempt password guesses offline. Encourage a strong passphrase; Argon2 slows guessing rather than making a weak password equivalent to a random 128-bit secret. Neither design protects an unlocked computer from malware.

### 5. Make browser mode usable and keep security controls precise

Keep launch-code authentication and exact Host/Origin checks. Use a distinct unpredictable cookie name per process/profile so demo and real instances on different ports do not overwrite each other's session cookie. Cookies are scoped by host/path, not port; an ordinary browser is not equivalent to an isolated WebView2 profile.

Provide an authenticated same-user mechanism to request a fresh one-time launch URL on repeat browser launches, or a clear restart path. A consumed/expired 30-second URL must not permanently strand `--no-browser` users. Do not persist the session credential in plain logs. Ensure rejected launch requests, redirects and errors receive the security/no-cache headers too.

Match the locked-route allowlist by exact route or explicit path subtree, not broad string prefixes such as `/setupAnything`. Setup/recovery/unlock routes need state and method checks. Build an unlock/setup renderer that never calls `container()` or the financial sidebar; the current shared render helper assumes an unlocked container.

Enforce upload limits by counting received bytes, including missing/chunked Content-Length, before multipart buffering. Bound both uploaded CSV and encoded form payloads. Retain the no-plaintext-temp requirement. Idle lock tracks meaningful user activity rather than background polling. Test Firefox as well as Chromium; preserve existing form and popup behavior while enabling CSP.

### 6. Fail closed on desktop integration failures

Attach a native navigation guard before untrusted navigation can occur. A `loaded` callback that brings the page back is not a security fallback: scripts may already have run. If the native guard cannot be installed, fail startup visibly. Block unexpected schemes, new-window navigation and dropped files, and test the actual pinned WebView2/pywebview combination.

Keep private WebView storage separate from persistent data; pywebview 6.2.1 source confirms its cleanup removes the user-data folder. Never pass the Lightning data folder as `storage_path`. [Pinned pywebview source](https://github.com/r0x0r/pywebview/blob/6.2.1/webview/platforms/edgechromium.py).

The runtime registry identifier in the draft matches Microsoft's distribution source, but “version >= 86” is not proof that today's required APIs exist. Test capabilities against the pinned SDK/runtime. In Windows startup, require `edgechromium`; reject the IE fallback. Dispatch dialogs/window focus to the GUI thread and return results to the runtime; do not assume any arbitrary threadpool thread is a valid WinForms owner.

Address repeat-launch focus to the locked profile's owning process/window, not merely the title `Lightning`. Keep the instance lock until DB shutdown completes. Test a second launch while the first is still starting and while it is exiting.

## Budget-conscious work packets

Use the architect for contracts, data-safety decisions, integration and final review. Default bounded implementation tasks to a small model (Luna); escalate a task to a medium model only when a concrete failing test or design difficulty justifies it. Do not pay several agents to re-review the full repository.

| Packet | Owner | Deliverable and acceptance | Depends on |
|---|---|---|---|
| P0: frozen Windows feasibility | Small model; architect reviews | Minimal disposable spike: one-folder exe, WebView2 forced, native navigation hook, resource load, encrypted scratch DB and password-slot roundtrip. Build on Windows and run interactive smoke before investing in full UX. No real data. | Chosen Windows test machine |
| P1: paths and release contract | Small model | Platform path resolver, explicit legacy detection, per-profile lock contract, version metadata and optional dependency groups. Same data path after moving/replacing app folder; browser import succeeds without Windows dependencies. | P0 packaging constraints |
| P2: database upgrade safety | Medium only if needed; architect owns review | Reviewed SQLCipher adapter with explicit test keys, atomic migration records, schema/resource guards, verified uniquely named encrypted backup and staged conversion helpers. Failure/crash tests prove original data stays usable. | P1, architect's driver interface |
| P3: local HTTP and frontend hardening | Small model, split HTTP and template edits if useful | Launch/session guards, redirects, streamed upload cap; offline fonts/CSP and popup fixes. Tests cover real+demo coexistence, rejection paths and Firefox/Chromium forms. | Shared session interface |
| P4: key/session setup and recovery | Architect contracts; small model for screens/tests | Password slots over the P2 driver, recovery onboarding, password unlock on both OSes, staged restore. No DPAPI/rotation/mirror automation. No container-dependent locked pages. | P1, P2, P3 |
| P5: shared runtime lifecycle | Architect/medium model | Event-loop ownership, operation admission/drain, cancellation/generation handling, startup without network waits, graceful shutdown. Race tests cover save vs lock/exit/restore. | P2, P4 |
| P6: Windows shell | Small model using validated P0 adapter | Window launch, supported navigation, uploads/downloads, missing-runtime UI, per-profile repeat launch. Thin adapter over common runtime. | P0, P5 |
| P7: ZIP build and update validation | Small model | Locked Windows build, artifact allowlist, self-check in temp data, ZIP/checksum/notices and update instructions. N→N+1 data retention and older-app/newer-schema rejection. | P6 |
| P8: acceptance and release decision | Architect + Windows tester | Full integrated suite/import checks; Windows clean-machine and Linux browser acceptance; report remaining limitations before distribution. | All above |

Each task prompt specifies exact read/write scope, shared interface, acceptance tests and a stop condition. Workers must return changed paths, actual test results and uncertainties. Independent tasks may run in parallel only with disjoint write sets; schedule shared `bootstrap.py`, `main.py` and session changes sequentially. Run focused tests per packet and the full suite at integration, rather than mechanically rerunning everything for every documentation edit.

Defer DPAPI/automatic unlock, one-file packaging, automatic updater, Linux desktop packaging, installer, key rotation, cloud-backup mirroring and cosmetic additions. Local verified backups and a clear manual backup/export path remain required. Signing becomes a release decision if recipient machines reject unsigned builds. No cost or release-date estimate is credible until the Windows spike runs.

## Verification record

Source document/references fetched from GitHub main at `31a8ea5020cd99ea8d4d65e54285bccfe1fe501e`. Local app checkout is `bc622d95a1d761b5625c1204d02cd7114c2827aa`, six commits behind. Latest source was extracted into an isolated temporary directory for tests; the application checkout and real data were not updated or migrated.

Two bounded reviews were delegated to `gpt-6-luna`; the architect retained design decisions and synthesis. Windows GUI/frozen-artifact behavior remains untested in this Linux review and must not be reported as passed. DPAPI is deferred by the owner's password-only decision.

Verified on synthetic scratch data (SQLCipher package 0.6.2 installed only under `/tmp`):

- Recovery-key encode/parse and 32-byte HKDF derivation passed; the tested typo was rejected.
- Password wrap/unwrap passed with the sketch's 256 MiB / 3 iterations / 4 lanes Argon2id settings. Wrong password, altered authenticated metadata and altered ciphertext were rejected. This path uses `cryptography`'s Argon2id, not `argon2-cffi`.
- With the reference patch applied only in a disposable source copy, plaintext conversion preserved a synthetic row. Correct-key reopen, `integrity_check` and `cipher_integrity_check` passed; wrong-key and stock `sqlite3` reads were rejected.
- The prototype's encrypted backup reopened and passed integrity checks. These happy-path results do not establish crash safety or validate its automatic in-place conversion behavior.

**Latest baseline: all 298 tests passed (exit 0), including the architecture-contract test.** This is the current application before desktop/encryption implementation; it must not be described as the complete suite passing with encryption implemented. Warnings concern the Starlette/httpx TestClient deprecation and the stdlib SQLite date adapter; no test failures occurred.

- Four import contracts passed against the latest snapshot (92 files, 364 dependencies). The missing `import-linter` was installed in `/tmp/lightning-review-tools-50M7nE`, not the app's environment.
- Migration fault injection reproduced the crash gap: failing the version-row insert left the created table present without its migration record; retry failed with `table crash_probe already exists`. This is a confirmed defect in current code, not merely a hypothetical objection to the draft.
- Sandboxed pytest stalled in the first TestClient request after 23 tests. The isolated stalled test passed immediately outside the sandbox; the complete suite was then rerun there on synthetic data. The initial interrupted run is not counted as a full pass.

Reproduction context: latest snapshot directory `/tmp/lightning-desktop-review-7DhLtl`, Python `/home/x/projects/Lightning/.venv/bin/python` (3.14.7), pytest 9.1.1. Architecture checker: import-linter 2.15. The encryption probes used a separate disposable copy at `/tmp/lightning-prototype-copy.oWI0VN` and SQLCipher installed at `/tmp/lightning-sqlcipher-probe.I80RlC`; they were inline synthetic-data probes, not the full application suite. Temporary paths may disappear after this session.

Baseline command, run from the snapshot outside the restricted sandbox:

```sh
env PYTHONPATH=/tmp/lightning-review-tools-50M7nE:. PATH=/tmp/lightning-review-tools-50M7nE/bin:/home/x/projects/Lightning/.venv/bin:/usr/bin:/bin timeout --signal=INT 180s /home/x/projects/Lightning/.venv/bin/python -m pytest -q
```

Review disposition: proceed with the amended architecture when the owner starts the build, beginning with P0. This is architecture approval for implementation, not approval to ship an untested Windows binary. The app checkout is unchanged; reconcile it with the reviewed GitHub commit before implementation and rerun affected checks if that baseline has changed.

## Owner decisions before dependent implementation

- Resolved: the owner selected password unlock on both Windows and Linux. This overrides D6/first-run automatic-unlock choices in the original draft; recovery always creates a password slot in v1.
- Resolved: Windows-first beta; the owner will host the ZIP on their website for a few selected testers. Assign a Windows PC/VM and tester during P0/P8; no interactive Windows test machine has been exercised in this review.

No decision is needed to retain browser mode or choose a ZIP: those follow the owner's current constraints. Market prices retain the draft's on-with-disclosure default unless changed. Start building only after the owner chooses to proceed from this review.
