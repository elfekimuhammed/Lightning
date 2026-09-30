# Desktop build status

The owner approved building the amended plan. Work started from GitHub main
`991563e` in the isolated `codex/desktop-beta` branch.

## Current milestone: P1/P2 profile and encrypted-storage foundations

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

Profile selection, password/recovery screens and the full finance window are **not
yet connected**. Documents may sync through OneDrive; local process locks do not
make live multi-computer database synchronization safe. The future chooser must
explain this and allow a non-synced folder.

## P0 engineering executable

The initial executable is `LightningProbe.exe`, deliberately labeled as an
engineering check. It does not read an existing financial database. It tests
SQLCipher, authenticated password slots, recovery keys, encrypted backups,
bundled resources, a protected loopback server, and WebView2 navigation.

The existing Linux browser app is still available through `python -m lightning`.
The new password primitives are not yet wired into that app's database lifecycle.
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

Remaining P3–P8 and P1/P2 integration in `REVIEW_AND_BUILD_PLAN.md`: full-app
HTTP/CSP hardening; profile picker and password/recovery screens; shared session/lifecycle;
safe candidate promotion/live restore;
the actual finance window; beta ZIP/update validation; Windows and Linux
acceptance. Existing financial data must remain untouched until explicit import.

Two small-model workers implemented the bounded window adapter and crypto checks.
The architect reviewed their changes and integrated the loopback host and build.
For P1/P2, two small-model workers implemented profile paths/locks and migration
atomicity. The architect reviewed those contracts and implemented encryption,
snapshot verification, staged copying and finance-service integration.

## Results

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
