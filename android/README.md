# Android dependency probe (task 04a)

This is a disposable arm64 build probe, not the Lightning Android app. It loads the
same Python 3.13 runtime and pinned native dependencies needed by the proposed
phone home node. It contains no profile or financial data.

Run the **Android dependency probe** GitHub Actions workflow manually, or run
`gradle --no-daemon :app:assembleDebug` from this directory with JDK 17,
Gradle 8.11.1, Android SDK platform/build-tools 35 and Python 3.13 installed.
Install the resulting APK on an arm64 phone and launch it: the screen must report
a SQLCipher version before the dependency-load part of 04a can pass.

GitHub Actions [run 37234716636](https://github.com/elfekimuhammed/Lightning/actions/runs/37234716636)
reached dependency resolution and failed on `sqlcipher3==0.6.2`:
“No matching distribution found.” No APK was produced or run on a phone.

Published-wheel check (2026-10-05): Chaquopy 17 supports Python 3.13
and arm64, but its [Android cryptography wheel index](https://chaquo.com/pypi-13.1/cryptography/)
lists 42.0.8 at most. Lightning pins 50.0.2, and its password slots use
`Argon2id`, [introduced in cryptography 44](https://cryptography.io/en/45.0.7/hazmat/primitives/key-derivation-functions/).
The [Chaquopy package guidance](https://chaquo.com/chaquopy/doc/current/faq.html)
says missing native packages need Android wheels built separately. The pinned
`sqlcipher3` Android wheel was not available to Chaquopy's resolver. The CI
build confirmed this first failure, but has not yet isolated `cryptography`
in a separate resolver run. Do not swap in cryptography 42 or plaintext SQLite
to make the probe pass.

The next step is a reproducible arm64 build of the two pinned Android wheels,
including their OpenSSL/SQLCipher link dependencies and 16 KB page support, then
an APK install and import check on a real device. If that fails, evaluate the
proposal's narrow native SQLCipher adapter without duplicating financial rules.
