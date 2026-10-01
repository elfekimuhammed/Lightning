# Encrypted profile preview

This build connects multiple password-protected profiles to the real finance UI.
Use synthetic/test data while Windows beta acceptance is still underway.

## Linux

From the desktop-beta checkout, with its encrypted dependencies installed:

```sh
.venv/bin/python -m lightning --profiles
```

For a separate test location:

```sh
.venv/bin/python -m lightning --profiles --profile-root /tmp/lightning-test-profiles
```

Leave the terminal running. Closing a browser tab does not stop the local server;
use **Profiles & lock** to lock immediately, or Ctrl+C in the terminal to stop.
Without `--profiles`, the original browser launcher and database path are unchanged.
The profile launcher does not auto-import the legacy database.

## Windows

Extract the versioned Lightning ZIP once into a new folder; run `Lightning.exe`
directly from that folder. The download contains only the finance app. Python is bundled;
Microsoft Edge WebView2 Runtime is a separate Windows prerequisite.

Create a profile, save its recovery key separately, then confirm. Use a strong
passphrase of at least 12 characters. The password protects the database contents,
not the filename/profile name. The recovery key grants access without the password;
keep it private and outside the database folder.

## Files and updates

The default is the computer's actual Documents folder (including redirection):

```text
Documents/Lightning/
  Home_2026-10-01_001_1a2b3c4d/
    Home_2026-10-01_001_1a2b3c4d.db
    keys.json
    instance.lock
    backups/
      Home_2026-10-01_001_1a2b3c4d_backup_2026-10-02_001_5e6f7a8b.db
```

The example dates/IDs are illustrative. The live database keeps its creation
identity across saves and app releases. Backups get their own UTC date, sequence
and ID. Password reset/change keeps the database recovery key unchanged.
An encrypted backup alone requires the recovery key; keep that key backed up too.
The chooser lists backups separately and never selects the newest automatically.

Close Lightning before replacing its whole extracted application folder. Do not
replace Documents/Lightning. Keep the complete profile folder together when
moving it; selecting an isolated database may require recovery to recreate its
password slot. Do not simultaneously open a synced database on two computers.
Downgrading the application is not necessarily safe after a schema upgrade.

## Current boundaries

- Alternate folders and database files are selected by entering their paths.
- Legacy plaintext import and backup restoration are not available in the UI yet.
  Selecting either as a live profile is refused, leaving the source untouched.
- Uploads are limited to 512 KiB per request to prevent plaintext temp-file spooling.
- Startup does not fetch market prices or run legacy reevaluation catch-up.
- The build is unsigned; do not disable antivirus protection to use it.
- This is local encryption, not an online account system, and cannot protect
  an already-unlocked computer from malware.

## Developer verification

`python desktop_app.py --self-check --report result.json` uses disposable data
only. On Windows, `--smoke --report window.json` checks the real profile chooser
and blocked external navigation using a temporary profile root.

`packaging/check_profile_browser.cjs` exercises Chromium and Firefox setup,
finance account saves, popup saves, cross-tab locking, reopening, mobile layout
and CSP. It requires Playwright via NODE_PATH and the project Python selected by
LIGHTNING_PYTHON; optional LIGHTNING_CHROMIUM/LIGHTNING_FIREFOX override browser
executables. It creates a distinct temporary directory and preserves synthetic
screenshots there for inspection; it never uses Documents.
