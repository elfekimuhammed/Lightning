# Matched PC and phone test builds

**Status:** proposal by Codex, 2026-10-07; rewritten by Claude the same day at the owner's request ("efficient, airtight, solid"). This is the instruction for building the test pair. When it is built, move what holds into Architecture › Desktop app and encrypted profiles › *Build and release* and delete this file. Public Windows releases and Google Play stay as Architecture and Project Overview › *Order to Google Play* say.

## What the owner gets

One manual run of the app workflow on `main` gives two downloads built and tested from **one commit**: `…-PC` (the Windows ZIP) and `…-Phone` (the APK of an app named **Lightning Test**). Each device downloads only its own file. A later Phone download installs over the earlier one and keeps its dummy profile. Dummy data only: a debug build is debuggable.

## Why today's path is not enough

- Windows and Android are separate workflows, so a "pair" can come from two commits.
- The APK is signed by the runner's throwaway debug key, with `versionCode = 1` under the release ID `org.lightning.app`, so a later APK may refuse to update the installed one.
- Its native wheels come from the artifacts of run 37449625570. GitHub deletes those when their retention ends (90 days by default, early January 2027), and then no APK can be built. If a wheel is missing, Gradle falls back to the package index; fastapi, uvicorn and jinja2 are pinned without their dependencies. Two builds can therefore carry different code.
- Every run also builds an unused crypto-only APK.

## One workflow, nothing built twice

Extend `.github/workflows/desktop-probe.yml` (shown as "PC and phone app") and delete `android-feasibility.yml`.

| Event | Linux suite | Windows | Android and bundle |
|---|---|---|---|
| Push to `main` | yes | no | no |
| Daily | yes | when the app changed (as now) | no |
| Tag `v*` | yes | yes | **never**; the release job is unchanged |
| Manual, on `main` only | skipped if an earlier run of this workflow passed it on this commit | reused if an earlier run built it on this commit and its artifact has not expired; otherwise built | yes |

A manual run on any other ref fails in the tests job, with the reason.

**Jobs.**
1. **tests** (Linux). For a manual run, `packaging/ci_scope.py` reads this workflow's earlier runs on `github.sha` (the API it already uses) and sets `reuse_run` (the newest run whose Windows job succeeded and whose `Lightning-v*-dev-*-Windows-x64` artifact has `expired: false`) and `suite=skip` (such a run, or any run whose tests job succeeded). An unknown answer means build and test, as now. Its cases get tests beside the existing ones in `tests/test_profile_packaging.py`.
2. **windows**: unchanged; skipped when `reuse_run` is set.
3. **android** (Linux, after tests, beside windows): the pinned build and checks below.
4. **bundle** (Linux): only when android succeeded and windows succeeded or was replaced by `reuse_run`. A reused ZIP must match its `APP_SHA256SUMS`, and its `BUILD_INFO.txt` commit must equal `github.sha`.

**Concurrency.** A manual run gets its own group, so a push to `main` never cancels it and it never cancels a push: `group: windows-app-${{ github.ref }}${{ github.event_name == 'workflow_dispatch' && format('-{0}', github.run_id) || '' }}`. Its Windows job is a job of this workflow on `main`, so the next daily run counts it and does not rebuild that commit.

**Cost** (billed minutes, from the runs of 2026-10-06; Windows counts double): a manual run that reuses the ZIP about 4; one that builds Windows about 31 (Linux suite 6, Windows 22, Android 2, bundle 1). Publishing the native wheels costs about 30, once, and again only when a native pin changes. Today's path costs about 60 when the wheels are rebuilt.

## Android inputs, pinned

- **Native wheels** (cryptography, sqlcipher3, cffi, pydantic_core). `android-native-wheels.yml` gets a `publish` input. When all four builds pass, a job with `contents: write` publishes them as a prerelease `android-wheels-<n>` of this repository, titled as a build input, not an app. It carries `SHA256SUMS` and `PROVENANCE.txt` (each source archive's SHA-256, NDK, Python and builder versions). `android/wheels.lock` commits the tag and each file's name and SHA-256. The android job downloads that release (`gh release download`, `contents: read`) and runs `sha256sum -c` before Gradle. Release assets do not expire; a replaced or deleted asset fails the check. To change a native pin: run the wheel workflow with `publish`, then commit the new lock.
- **Pure-Python packages.** `requirements/android.in` names what `android/app/build.gradle.kts` installs today (fastapi, uvicorn, jinja2, python-multipart, tzdata). uv compiles it with hashes into `requirements/android.lock`, like the desktop locks, leaving out the four native names. Gradle installs that lock plus the four wheels, each with its locked hash, under `--require-hashes`. It never names a version of its own.
- **No fallback.** Gradle fails when `wheelDir` is missing or lacks one of the four wheels; it never resolves them from an index.
- **After the build**, the job lists the `*.dist-info` folders inside the APK's Chaquopy requirement archives. It fails unless the names and versions equal the two locks exactly, which also catches a dependency that differs on Android.

## Android identity, signing and checks

- **Identity.** The workflow passes Gradle properties: `applicationId` `org.lightning.app.test`; label **Lightning Test**; `versionCode` = `git rev-list --count HEAD`, which grows with every commit on `main`, so an older build cannot install over a newer one (Android's rule); and `versionName` = `<DISPLAY_VERSION>-test.<count>+<commit8>`. Local builds keep `versionCode` 1. `org.lightning.app` stays reserved for the Play build. The phone's Settings shows the `versionName`, so a screenshot names the build.
- **Test key.** One dedicated key (RSA 3072, valid 30 years, PKCS#12, alias `lightning-test`), never a Play key. `tools/android_test_key.py` makes it on the owner's PC with Python and `cryptography`, which Lightning already needs. It prints the two secret values, `ANDROID_TEST_KEYSTORE` (base64) and `ANDROID_TEST_KEYSTORE_PASSWORD`, and the certificate's SHA-256 fingerprint. The fingerprint is public and is committed as `android/test-certificate.sha256`. The key never passes through the repository, an artifact, a log or an AI session. The job decodes it to `$RUNNER_TEMP` and deletes it after signing. **No secret, no APK:** the job never falls back to the runner's debug key, whose APK could not update the installed one. If the key is lost, the next APK needs one uninstall, which loses the dummy profile.
- **Checks on the built APK** (`apksigner` and `aapt2` from build-tools 35); each failure fails the job:
  - it is signed with scheme v2 or later, by exactly the pinned certificate;
  - its package, `versionCode` and `versionName` are the ones the job passed;
  - it has native libraries for `arm64-v8a` only;
  - its permissions equal `android/permissions.txt` (adding one, such as SMS for milestone 3, takes a deliberate commit);
  - it carries the files the current workflow requires, and no database, key, backup or log except the committed dummy fixture `roundtrip_fixture/profile.db`.

  Same ID, same certificate and a `versionCode` that never falls are exactly Android's rules for an update, so no emulator run is needed. The owner's install is the real-device proof.

## The bundle

- Two seven-day artifacts, `Lightning-Test-<version>-<count>-<commit8>-PC` and `…-Phone`. They hold the Windows ZIP (under its existing development name) and `Lightning-Test-<version>-<count>-<commit8>.apk`.
- Each also holds `SHA256SUMS` (for both files), `README.txt` and `BUILD.json`. The README gives the install steps, says dummy data only, and says to uninstall the old "Lightning" debug app once. `BUILD.json` records:
  - the commit, run, attempt and UTC time;
  - each file's name, size and SHA-256;
  - the Windows `BUILD_INFO.txt` identity, and the run it came from;
  - the Android ID, `versionCode`, `versionName`, certificate fingerprint, ABI and wheel tag.
- The bundle job writes them from the built files, only after every check above has passed. A run never offers half a pair. The bundle is not a release, is never attached to one, and needs neither the downloads token nor a price pack.

## The release path stays separate

A `v<version>` tag publishes only its tested Windows ZIP, as Architecture › *Build and release* says. For Google Play: a non-debuggable App Bundle (`.aab`) under `org.lightning.app`, signed in CI with the owner's **upload key** from restricted secrets, with an increasing `versionCode`, submitted to Play App Signing. Google then signs installs with its own app signing key, so an APK signed with the upload key cannot be promised to update a Play install. A direct-download channel needs its own decision. The upload key never enters a test build, a file, an artifact or a log. Publication stays gated on the phone milestones, the SMS and Play policy review, and ordinary-device acceptance ([app signing](https://developer.android.com/studio/publish/app-signing), [versioning](https://developer.android.com/studio/publish/versioning), [bundles](https://developer.android.com/studio/publish/upload-bundle)).

## Steps (push each one when its tests pass)

1. **Pinned inputs:** the wheel `publish` job, `android/wheels.lock`, `requirements/android.lock`, Gradle without fallback, and the after-build check. Run the wheel workflow with `publish` once, then commit the lock.
2. **Test identity:** Gradle's ID, label, version and signing; the key script; the fingerprint and permissions files; the APK checks; the phone's Settings showing the build. Then add to `OWNER.md`: run the script, add the two secrets, send the fingerprint.
3. **One workflow:** the android and bundle jobs in `desktop-probe.yml`, `ci_scope.py` reuse and suite skip with their tests, the concurrency group, the refusal outside `main`, `android-feasibility.yml` deleted, and `android/README.md` updated. One manual run proves it. Then move what holds into Architecture, replace `OWNER.md`'s two run links with "run *PC and phone app* by hand", and delete this file.
4. **Owner review**, at the milestone only: install both builds, uninstall the old Lightning once, pair, and run the milestone with dummy data.
