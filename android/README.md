# Android dependency probe (task 04a)

This is a disposable arm64 build probe, not the Lightning Android app. It loads the
same Python 3.13 runtime and pinned native dependencies needed by the proposed
phone home node. It contains no profile or financial data.

Run the **Android dependency probe** GitHub Actions workflow manually, or run
`gradle --no-daemon :app:assembleDebug` from this directory with JDK 17,
Gradle 8.11.1, Android SDK platform/build-tools 35 and Python 3.13 installed.
Install the resulting APK on an arm64 phone and launch it: the screen must report
a SQLCipher version before the dependency-load part of 04a can pass.

GitHub Actions [run 37235081432](https://github.com/elfekimuhammed/Lightning/actions/runs/37235081432)
resolved each native dependency separately. The full build found no Android
distribution for `sqlcipher3==0.6.2`; the crypto-only build found only 42.0.8,
not pinned `cryptography==50.0.2`. No APK was produced or run on a phone.

Published-wheel check (2026-10-05): Chaquopy 17 supports Python 3.13
and arm64, but its [Android cryptography wheel index](https://chaquo.com/pypi-13.1/cryptography/)
lists 42.0.8 at most. Lightning pins 50.0.2, and its password slots use
`Argon2id`, [introduced in cryptography 44](https://cryptography.io/en/45.0.7/hazmat/primitives/key-derivation-functions/).
The [Chaquopy package guidance](https://chaquo.com/chaquopy/doc/current/faq.html)
says missing native packages need Android wheels built separately. Both pinned
native packages are unavailable to Chaquopy's resolver. Do not swap in
cryptography 42 or plaintext SQLite to make the probe pass.

The next step is a reproducible arm64 build of the two pinned Android wheels,
including their OpenSSL/SQLCipher link dependencies and 16 KB page support, then
an APK install and import check on a real device. If that fails, evaluate the
proposal's narrow native SQLCipher adapter without duplicating financial rules.

Source-wheel experiment [run 37235463323](https://github.com/elfekimuhammed/Lightning/actions/runs/37235463323)
also failed. `cryptography==50.0.2` reached Android Rust/C compilation but could
not find `Python.h` in the cross-build include paths. `sqlcipher3==0.6.2`
reached its Conan OpenSSL dependency graph and stopped because the Android
`settings.os.api_level` was undefined. These are build-configuration failures,
not evidence that compatible wheels are impossible. Fix and rerun both build
configurations before deciding whether the native adapter is necessary.

The next manual source-wheel run tests those two configuration fixes. The
cryptography job asks cibuildwheel to locate the target Python header and add
its directory to `CFLAGS`. The SQLCipher job patches only the downloaded
0.6.2 `setup.py` in its disposable build directory to pass
`os.api_level=24` to Conan. Its exact expected source line is checked before
patching. This is a feasibility probe, not a patched package for release;
produced wheels still need dependency/link, 16 KB page and on-device import
checks. [cibuildwheel environment syntax](https://cibuildwheel.pypa.io/en/stable/options/#environment)
and [Conan Android API setting](https://docs.conan.io/2.14/examples/cross_build/android/ndk.html)
are the build references.

The first configuration rerun, [run 37240415999](https://github.com/elfekimuhammed/Lightning/actions/runs/37240415999),
stopped before either compiler: cibuildwheel evaluates `CIBW_ENVIRONMENT_ANDROID`
without shell glob expansion, so the inline `find /tmp/cibw-run-*/...` received
the `*` literally. A small Python locator replaced that glob and requires
exactly one target `Python.h`. These were configuration errors, not wheel results.

The locator rerun, [run 37244107860](https://github.com/elfekimuhammed/Lightning/actions/runs/37244107860),
passed that earlier failure. Cryptography still fails when its Rust/C build
cannot include `Python.h`; cibuildwheel's Android environment subsequently
rewrites `CFLAGS`, so the compiler's actual include path must be inspected at
the build hook. SQLCipher passes `os.api_level=24` to Conan, then OpenSSL's
dependency graph rejects the incomplete profile because `settings.compiler`
is undefined. Neither job produced a wheel. The next probe must supply an
explicit Android Clang Conan profile and a target-header path that survives
the build environment setup. These remain configuration findings; they do not
establish Android runtime or 16 KB page compatibility.
