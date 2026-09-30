Lightning Windows feasibility check — P0, not the beta finance app

Extract the entire folder and double-click LightningProbe.exe on Windows x64.
Microsoft Edge WebView2 Runtime must be installed. Official download:
https://developer.microsoft.com/microsoft-edge/webview2/consumer/

This build creates and removes temporary synthetic data only. It never reads
or converts your Lightning financial database. The finance UI comes later.

Automated checks (PowerShell):
  $p = Start-Process .\LightningProbe.exe -ArgumentList '--self-check --report self-check.json' -Wait -PassThru
  $p.ExitCode
  Get-Content .\self-check.json

Window check (automatically closes after checking):
  $p = Start-Process .\LightningProbe.exe -ArgumentList '--smoke --report window-check.json' -Wait -PassThru
  $p.ExitCode
  Get-Content .\window-check.json

Expected: exit code 0 and "ok": true. Keep the JSON reports with your test notes.
Try again from a folder with spaces and non-ASCII characters and while offline.
No finance database, password or recovery key should appear in this folder.

For the eventual beta, replace the entire program folder when updating, with
Lightning closed. Financial data will live separately in the user's data folder.
Do not distribute this feasibility build as the finance beta.
