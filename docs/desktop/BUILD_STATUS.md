# Desktop build status

The owner approved building the amended plan. Work started from GitHub main
`991563e` in the isolated `codex/desktop-beta` branch.

## Current milestone: connected encrypted-profile development preview

The profile chooser, password/recovery screens and real finance UI are now
connected through a shared loopback runtime. This is a development preview,
not yet a generally distributable financial beta.

- `python -m lightning --profiles` starts the password-protected browser app on
  Linux. Windows `Lightning.exe` uses the same runtime in the guarded WebView2
  window. The existing `python -m lightning` legacy workflow remains unchanged.
- Start locked, discover Documents/Lightning profiles and their backups, or
  explicitly enter another folder/database path. No database is selected by age.
  Names retain the stable name/date/sequence/ID convention. Alternate selection
  currently uses path fields, not an operating-system file-picker dialog.
- Create a named encrypted profile with a 12-character-minimum passphrase,
  display its recovery key, and require an explicit saved-key confirmation.
  Setup does not write anything before confirmation. Each setup attempt gets a
  new confirmation token to prevent two tabs acknowledging different keys.
- Unlock, change password, reset a password using a verified recovery key,
  lock, and switch profiles. Recovery validates the database read-only before
  atomically replacing its password slot; it does not replace financial data.
- All encrypted connections stay on the ASGI owning thread. Complete requests
  serialize with lock/shutdown transitions. Finance writes carry a per-profile
  generation token, so a stale tab cannot save into a different profile.
- Idle lock after 15 minutes; trusted foreground keyboard/pointer activity is
  throttled, while background health polling never extends the session. Other
  open tabs clear on a lock broadcast or their next health check (15 seconds).
- Exact loopback Host and Origin, single-use launch exchange, per-instance
  HttpOnly/SameSite cookies, no-store responses, nonce-based script CSP, no
  inline event attributes, and a streamed 512 KiB request cap below the upload
  spool threshold. Fonts stay local in profile mode. HTTP access logs are off.
- A separate `Lightning.exe` / `Lightning-windows-x64.zip` build accompanies,
  but does not replace, the engineering probe. Its self-check exercises actual
  synthetic profile creation, finance route loading, backup, reopen and recovery.
  Window smoke uses a disposable root, never the user's Documents.

No personal database has been opened, moved, converted or replaced. Selecting
legacy plaintext or a backup as a live database fails with an explanation.
Legacy import and backup-restore UI/promotion remain pending. Do not work around
this by renaming a backup as a live profile. The current preview also does not
automatically refresh network market prices or perform the legacy launcher's
startup reevaluation catch-up. It uses saved data until a future explicit flow.

Two small-model workers produced the profile screens, packaging and browser
session helper, plus the first mechanical template changes. The architect
implemented/reviewed the lifecycle, security, finance integration and acceptance
checks. Final validation evidence is recorded below after the build completes.

### Connected-preview local validation

- Linux: **404 passed, 1 Windows-only skip**; all four import contracts and
  `git diff --check` passed.
- Chromium and Firefox: setup and saved-key confirmation, full-page account
  creation, popup account creation, cross-tab lock, password reopen, persistent
  records, mobile chooser/backups and CSP checks passed on disposable profiles.
- These checks caught and fixed Chromium's Origin:null behavior with a global
  no-referrer policy, a Firefox canceled-health-fetch navigation race, and long
  backup labels overflowing a narrow screen. Ordinary pages now use same-origin
  referrers; the launch-token exchange alone uses no-referrer.
- Local screenshots and scratch profiles are synthetic, outside Documents.
  Windows build and ordinary-PC checks are tracked separately; local browser
  results do not claim Windows acceptance.

## P1/P2 foundation milestone (historical)

The owner confirmed the probe launches on their Windows laptop. A different
Windows PC failed at window startup; its cause remains unresolved (it is not a
requirement to install Python). This is an open clean-machine compatibility issue,
not a reason to call the probe a complete finance beta.

The desktop worktree is now persistent at
`/home/x/projects/Lightning/.worktrees/desktop-beta`; the earlier `/tmp` worktree
was cleaned up and restored from its saved Git branch.

Implemented in this stage:

- Documents → Lightning is the **upcoming launcher's** default profile container,
  following the owner's amendment. Resolve actual Windows Documents, including
  redirection, and Linux's configured Documents directory. Alternate locations
  and explicit database choices are supported by the path API.
- Multiple named profiles, shallow read-only discovery and date/sequence/ID
  database filenames; canonical per-profile companion paths and OS instance locks.
  Discovery does not select a database automatically. Backups are listed separately.
- Opt-in encrypted database access through the existing finance services, with
  one-thread ownership and no plaintext fallback. The legacy browser launcher
  still uses its existing path and plaintext mode until session integration.
- Atomic migration SQL/version records, missing-resource and newer-schema guards,
  verified protected pre-upgrade backups, and encrypted snapshots reopened for
  integrity, foreign-key, schema, row-content and sequence comparisons.
- Explicit staged import/recovery copies that include committed WAL data and
  preserve the original. These produce candidates only; live restore/promotion
  must wait for session quiescing and user confirmation.
- Readable dated backup names, per-database retention and Settings listing.
  No real database has been moved, converted or imported during this work.

At this earlier milestone, profile selection, password/recovery screens and the
full finance window were not yet connected. Documents may sync through OneDrive; local process locks do not
make live multi-computer database synchronization safe. The future chooser must
explain this and allow a non-synced folder.

## P0 engineering executable

The initial executable is `LightningProbe.exe`, deliberately labeled as an
engineering check. It does not read an existing financial database. It tests
SQLCipher, authenticated password slots, recovery keys, encrypted backups,
bundled resources, a protected loopback server, and WebView2 navigation.

The existing Linux browser app is still available through `python -m lightning`.
The legacy mode is unchanged; use the new `--profiles` mode for password unlock.
Do not mistake a successful probe for a completed encrypted finance beta.

Run source self-checks:

```sh
python desktop_probe.py --self-check --report probe-result.json
```

Windows CI installs hash-locked dependencies, tests shared/platform adapters,
freezes a one-folder executable, runs its self-check and actual window smoke,
and packages a ZIP only after the required checks pass. The GitHub workflow
is `Windows desktop feasibility`. It uses read-only repository permissions
and does not publish to the owner's website.

The initial window/navigation checks and the owner's laptop launch passed.
The manual checklist is in `packaging/PROBE_README.txt`; offline/path cases and
the other PC's launch failure remain acceptance work.

## Remaining implementation

Remaining work in `REVIEW_AND_BUILD_PLAN.md`: explicit legacy import and safe
candidate promotion/backup restore, broader finance/CSP acceptance, ordinary
Windows machine compatibility (including the earlier failing PC), ZIP/update
acceptance, native file pickers, and final Windows/Linux beta checks. Existing
financial data must remain untouched until explicit import.

Two small-model workers implemented the bounded window adapter and crypto checks.
The architect reviewed their changes and integrated the loopback host and build.
For P1/P2, two small-model workers implemented profile paths/locks and migration
atomicity. The architect reviewed those contracts and implemented encryption,
snapshot verification, staged copying and finance-service integration.

## P1/P2 validation

- Local Linux/Python 3.13: **385 passed, 1 skipped**. The skipped test calls the
  actual Windows Documents known-folder API; it runs in Windows CI instead.
- All four import contracts passed; `git diff --check` passed.
- Tests cover encrypted finance-service use and the complete synthetic sample
  household, verified backups, wrong-key/no-plaintext-fallback behavior, source
  preservation including committed WAL rows, output-collision safety, protected
  upgrade backups, atomic migration failure/retry and abrupt process-exit rollback.
- Profile tests cover multiple names/locations, directory aliases, hardlink and
  database-symlink rejection, unfinished-directory sequences, safe Linux Documents
  parsing and real subprocess lock contention/release.
- The date rollover to October 1 exposed wall-clock-dependent historical test
  fixtures. Audit timestamps are now pinned in tests; the app's real clock behavior
  is unchanged. Text-resource checks explicitly use UTF-8 on Windows.
- CI runs the complete shared suite on Linux and focused desktop, profile,
  database and UI coverage on Windows to control runner costs. Earlier interrupted
  Windows runs are not counted as passes.
- [Final cross-platform run](https://github.com/elfekimuhammed/Lightning/actions/runs/36777173133)
  on code revision `eefc298` passed: Linux **385 passed, 1 Windows-only skip**;
  Windows **133 passed** with no skips, including actual Documents known-folder
  resolution and OS locks. All four import contracts passed on each platform.
  The frozen encryption/resource check and real guarded WebView2 window smoke
  also passed. Its downloadable ZIP remains the engineering probe, not the
  profile/password finance UI. A documentation-only follow-up records these
  results without another CI build.

## P0 validation (historical)

- Linux Python 3.13: 332 tests passed, including 34 new feasibility checks.
- All four import contracts passed; `git diff --check` passed.
- Source self-check and a frozen Linux executable self-check both passed every
  encryption/resource check. The Linux freeze verifies packaging only, not a
  supported Linux desktop window.
- Windows Python 3.13: all 34 focused tests and all four import contracts passed.
  The frozen executable passed encryption/resource checks and the real WebView2
  smoke (authenticated local page/API and blocked external navigation).
  Evidence: [successful Windows run](https://github.com/elfekimuhammed/Lightning/actions/runs/36770153942)
  on code revision `09a62c2db1a4a8e57992b54926e1778540c45f9a`.
- The ZIP and non-secret JSON reports are attached to that run (seven-day
  retention). The downloaded ZIP's SHA-256 matched `SHA256SUMS`.
- Manual ordinary-user launch: owner confirmed the laptop works after the
  close/reopen request. The other PC's failure is still open. Remaining manual
  coverage includes offline and paths containing spaces/non-ASCII characters.
  This build is unsigned; report any Windows warning rather than disabling
  antivirus protection. Do not distribute it as the financial beta.
- Password slot default is Argon2id 64 MiB, 3 iterations, 4 lanes, with validated
  upper bounds before derivation. This replaces the draft's 256 MiB default for
  the initial beta profile; strong passphrases remain required in the future UI.
