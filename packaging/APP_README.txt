Lightning for Windows — development preview

This unsigned preview includes private profiles protected by a password and a
recovery key, plus the Lightning finance app. Please test it with dummy data
first. This is an early development build and has not been code-signed.

Windows requirements
--------------------
Windows x64 and the Microsoft Edge WebView2 Runtime are required. Install the
runtime from Microsoft's official page if it is not already available:
https://developer.microsoft.com/microsoft-edge/webview2/consumer/

No Python installation is needed.

Getting started
---------------
1. Extract the entire ZIP to a folder you can write to.
2. Double-click Lightning.exe and create a profile.
3. Choose a passphrase of at least 12 characters. Save the displayed recovery
   key offline in a safe place. The recovery key can reset a forgotten password.
4. Create or open financial data in the profile.

Profile databases and their backups are stored separately from this application,
under Documents/Lightning. Do not open the same database on two computers at the
same time, including through a synced Documents folder.

Updating and backups
--------------------
To update Lightning, close it and replace the entire extracted application folder
with the contents of the new ZIP. This replaces application files only; it does
not replace profile data in Documents/Lightning. Keep a separate copy of the
profile backup folder before making changes to valuable data.

Current limits
--------------
This preview does not include legacy database import or a backup-restore screen.
The browser finance app's upload limit is 512 KiB per request.

Linux developers can continue using the source browser app with:
  python -m lightning --profiles

The Linux source app retains its browser workflow and profile storage behavior.
