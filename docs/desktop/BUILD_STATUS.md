# Desktop build status

The owner approved building the amended plan. Work started from GitHub main
`991563e` in the isolated `codex/desktop-beta` branch.

## Current milestone: P0 Windows feasibility

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

Before proceeding to full beta integration, record a Windows result for the
window/navigation check and manual ordinary-user launch. The manual checklist
is in `packaging/PROBE_README.txt`. If CI cannot create an interactive window,
that is a failed gate requiring a PC/VM result, not a passed smoke test.

## Remaining implementation

P1–P8 in `REVIEW_AND_BUILD_PLAN.md`: persistent profile paths; atomic migration
bookkeeping; encrypted database driver and staged import/restore; full-app
HTTP/CSP hardening; password/recovery screens; shared session/lifecycle;
the actual finance window; beta ZIP/update validation; Windows and Linux
acceptance. Existing financial data must remain untouched until explicit import.

Two small-model workers implement the bounded window adapter and crypto checks.
The architect owns the loopback/build integration and reviews their changes.

## Results

- Linux Python 3.13: 332 tests passed, including 34 new feasibility checks.
- All four import contracts passed; `git diff --check` passed.
- Source self-check and a frozen Linux executable self-check both passed every
  encryption/resource check. The Linux freeze verifies packaging only, not a
  supported Linux desktop window.
- Windows workflow result and manual ordinary-user smoke: pending.
- Password slot default is Argon2id 64 MiB, 3 iterations, 4 lanes, with validated
  upper bounds before derivation. This replaces the draft's 256 MiB default for
  the initial beta profile; strong passphrases remain required in the future UI.
