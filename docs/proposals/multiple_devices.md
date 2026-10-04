# Multiple devices: the phone lends the ledger

**Status · proposed, not built · 2026-10-04.** This is the agreed version 1 design for one Lightning codebase on PC and Android. The owner's product decisions are in [Project Overview](../PROJECT_OVERVIEW.md); Claude's review and the decisions made during it remain below as history. Acceptance still requires working code, real-device measurements and fault tests.

## Scope and names

The **home node** is the phone. It stores the accepted encrypted ledger in private app storage and may edit while the ledger is **at home**. A paired PC or laptop is a **borrower** while it holds the **working copy** and is the sole **writer node**. During that lend, the phone is a **reader node** and shows its last accepted ledger read-only. One profile has one writer at a time; there is no merge. The PC may continue editing its local working copy when the phone is out of reach.

User actions are **Pair**, **Lend**, **Hand back**, and explicit **Take back** after a lost borrower. A **prefetch copy** is encrypted data downloaded before the PC password is entered. A **recovery copy** is an unaccepted snapshot sent by the borrower during a lend. A **sealed copy** is the borrower's final local copy when it closes away from the phone. An **accepted version** is one the phone has fully verified and durably committed; versions have a parent and a lineage. Use plain device names such as “Office PC” on screen.

Version 1 has one phone home and paired PCs. It does not include general reader devices, a server home, cloud storage, a remote relay, continuous replication, a separate immutable version-store service, or automatic merging. The phone retains its current ledger and a few previous accepted encrypted copies. The same Python finance services, templates, CSS, SQLCipher format and financial rules run on PC and Android; only the shell and platform integration differ.

## Safety contract

1. **Only the recorded writer may change the ledger.** The home node durably records a lend before issuing its permit. While lent, it opens its ledger through `Database(read_only=True)` and disables migrations, startup catch-up, price refreshes, SMS posting and every other write path. The borrower allows writes only after durably recording the matching permit. Each device also keeps its local process lock.
2. **Never decide by file time.** Profile ID, parent accepted-version hash, lineage, checkout epoch, checkout ID, device ID and return ID bind each handoff. The home node rejects a stale or duplicate return. A clock reading is display information, not authority.
3. **Receive and accept are different.** A locked phone may receive and hash-check encrypted bytes. It calls them *received, checking*, keeps the old accepted ledger, and cannot edit the candidate. Only after unlock does it verify the SQLCipher pages, SQLite integrity, foreign keys, schema and contents, then durably accept the candidate. A transport receipt is not an acceptance receipt.
4. **Ambiguity stops promotion or reassignment.** A lost grant, upload or receipt is retried with the same IDs. There is no automatic lend expiry or silent takeover. A new writer is allowed only after a completed hand-back or explicit Take back into a new lineage.
5. **Unsent edits are at risk.** A successful local SQLite commit is durable on the borrower, but it is not yet accepted by the phone. If the borrower and its local backups disappear, only the last recovery copy actually received by the phone is recoverable. “Three minutes” is a target while transfers succeed, not an unconditional loss bound. Every screen must show where the newest known copy is.

These guarantees apply to cooperating Lightning clients and functioning device storage. A compromised paired device already holds the data key and can copy the financial data. Revoking its network identity cannot erase an old copy. No protocol can prevent an offline device from modifying its own files; the home node can refuse to accept an old lineage.

## Storage and service boundaries

| Place | Files and state | Rule |
|---|---|---|
| Phone private app storage | `profile.db`, previous accepted copies, durable lend record, staged returns and recent recovery copies | Exclude from Android Auto Backup. Never expose the live file through network shares. Keep the previous accepted copy until the next one is verified and recoverable. |
| Borrower `%LOCALAPPDATA%/Lightning` | Prefetch, working and sealed copies, durable lend record, local encrypted backups | Never put a live borrowed profile in Documents or OneDrive. A returned copy is retained as an encrypted backup. |
| Transport | A narrow sync listener separate from the loopback FastAPI UI server | Pair once by QR plus explicit owner approval; pin device identities and use authenticated encrypted transport. Discovery only finds the phone; it grants no trust. |

Each device has its own password-wrapped slot for the same SQLCipher data key. Pairing provisions that key only after unlock and approval over the authenticated channel; a password and recovery phrase are never sent. The phone can stage ciphertext while locked, but full verification waits for unlock. `lightning/database/snapshot.py` already creates verified encrypted snapshots; `staging.py` prepares candidates but does not promote them. The promotion, durable lend record, role gate and crash recovery still need to be built.

The home phone's normal database may use a rollback journal. A raw byte copy is allowed only after Lightning stops new writes, drains transactions, closes or quiesces the SQLite connection, and confirms that no hot journal must be recovered. Otherwise use a consistent SQLCipher snapshot. A hash of an unsafe live-file copy would prove only that bad bytes arrived unchanged. The phone resumes home writes after a prefetch, because prefetch itself grants nothing.

## Pair and prefetch

1. On first pairing, the user opens Lightning on the phone, scans the PC's QR code and approves its displayed identity. The PC receives its own key slot and a pinned home-node identity. Pairing may be revoked for future connections; existing encrypted copies remain on that device.
2. On later PC launches, the user opens Lightning on the phone with one tap. The phone starts a notification-backed Android service for the pending lend, subject to platform limits. The PC discovers the phone on local Wi-Fi, hotspot or a supported cable connection. If unreachable, it says so; it never invents a lend.
3. **Before the PC password is entered**, the phone briefly pauses writes and creates or copies a consistent encrypted snapshot. It sends that snapshot and a manifest with profile, lineage, schema, size and hash. The PC stages it under `%LOCALAPPDATA%`, checks length/hash, and can retain it as a local encrypted backup. The phone resumes writing. This overlaps transfer with password entry; it does not promise a fixed speed.
4. The PC unlocks the staged copy with its own password slot, verifies it, and checks app/schema compatibility. The staged copy is still read-only until the lend permit is durable on both sides.

## Lend

1. The PC asks to borrow the exact prefetched version. The phone serializes this with all finance requests and stops writes. The prefetch manifest carries both the transferred snapshot hash and the source-file hash measured while writes were paused. The phone rehashes the quiesced source file and compares it to that source hash; if it changed, it refreshes the prefetch and the PC verifies the replacement. A PC that cannot read the phone's schema must update before borrowing; only the home phone runs migrations.
2. The phone durably records `LENT(device, epoch, checkout_id, base_hash)` before sending a grant bound to those fields. It opens the ledger read-only. The PC durably records `BORROWING` and the permit before opening its working copy for writes. A missing acknowledgement leaves the phone lent; it never assumes the PC did not receive the grant.
3. If the PC cannot start using a grant, it first durably records `ABORTED` for that checkout ID and makes any delayed grant unusable. It sends an authenticated cancellation for that exact checkout ID. The phone durably records the cancellation before resuming writes. If cancellation cannot be proved, both remain blocked from a new lend until reconciliation or explicit Take back.

The phone can display the last accepted ledger read-only during a lend, marked “Lent to Office PC · newer changes may exist.” A figure such as Safe to spend must not look current without that warning. Other reader nodes are deferred.

## While lent, including an absent phone

- The borrower uses its local SQLCipher working copy and ordinary SQLite transactions, including offline. The role gate checks the durable lend state on restart and before writes. Compare a consistent working-copy hash with the borrowed base to detect changes. `audit_log` covers only some edits; it is helpful for explanation but cannot be the complete dirty signal. A take-back inspection compares the relevant tables between copies instead of claiming an exhaustive audit trail.
- After changes, send a verified encrypted recovery snapshot to the phone about every three minutes while reachable, and before closing. Retain the previous recovery copy until the new one is safely staged; recovery copies are **never accepted ledgers**. If the phone is unreachable, make a local encrypted snapshot and show the last copy known to be on the phone. Full-database uploads every three minutes may cost substantial battery and bandwidth on large profiles; measure this on a real phone.
- Closing while the phone is away saves a **sealed copy** and keeps the lend. The PC says that changes are saved here and will be handed back when both devices meet. Reopening the same PC while the copy is still sealed restores `BORROWING` so editing can continue. It records `RETURNING` only when the phone is reachable and transfer actually begins; reopening after that remains read-only until reconciliation. A bounded background task may retry while the PC is on; it never grants another writer.
- The phone's foreground service runs while preparing or servicing a lend, then stops when the ledger is home; if a borrower stays silent, it may stop after a bounded interval and schedule reminders. Start it from the user's foreground action and validate the service type, time limits and behavior on supported Android versions. After a long silence the phone reminds the owner which PC holds the ledger and when its last recovery copy arrived. A reminder never ends the lend automatically.

## Hand back and acceptance

1. The borrower quiesces writes, closes SQLite, creates and verifies a consistent encrypted candidate, and durably records `RETURNING(return_id, checkout_id, candidate_hash)`. It cannot resume editing this candidate after that point. It transfers bounded, resumable chunks with an authenticated manifest.
2. The phone checks sender, profile, lineage, epoch, checkout ID, parent hash, size, candidate hash and return ID. While locked it stores the candidate under a new staging name and replies **received, checking**. It retains the prior accepted ledger, stays non-writing, and gives the borrower no acceptance receipt.
3. At the next phone unlock, the phone opens the candidate using the SQLCipher key and runs `cipher_integrity_check`, SQLite `integrity_check`, `foreign_key_check`, schema checks and the existing snapshot inventory checks. A failure enters **Needs repair** with both old and new copies retained; it cannot silently roll back and post new transactions. If checks pass, it prepares a previous-version backup, promotes the candidate and durably records the new accepted version and consumed return ID. Recovery after a crash must finish or undo this promotion deterministically before any write is allowed.
4. The phone sends an **accepted** receipt bound to the return ID and hash. A repeated return receives the same receipt, never a second promotion. The borrower durably records `HANDED_BACK`, becomes read-only, and retains an encrypted backup. If the receipt is lost, it retries status; the phone may write after its own durable acceptance because the borrower had already stopped writes in step 1.

The user can close the PC after a locked-phone *received* receipt, but the UI must say the return is awaiting the phone's verification. If the phone remains locked, no node writes. The user opens the phone to complete acceptance. This is the cost of accepting encrypted bytes without keeping the SQLCipher key available in the background.

## Take back, loss and repair

**Take back is explicit owner recovery**, never a timeout. The phone shows the last accepted version and the time/hash of its latest verified recovery copy, states that newer PC edits may be missing, and asks the owner to choose that copy or the earlier accepted ledger. It begins a new lineage and rejects old checkout IDs. If the PC later returns, its later changes are quarantined for table-by-table inspection and manual re-entry; there is no automatic merge. The warning cannot claim a three-minute maximum if recovery uploads stopped earlier.

If the phone is lost while a PC holds the lend, the PC's working copy may seed a replacement phone under an explicit new lineage. If the phone is lost at home, a PC's most recent prefetch or returned backup may be restored; phone edits after that backup may be lost. Keep profile data local, with no automatic cloud copy. A stolen paired device remains a confidentiality risk even after network revocation.

At every ambiguous boundary, preserve both copies and show **Needs repair** rather than choosing the newest-looking file. Test wrong keys, schema mismatch, full disk, corrupt chunks, missing receipts, process kills, lost phone and lost PC. A return that has merely arrived on the phone cannot be used for finance reads or writes until full verification.

## Bank SMS after a lend

The phone does not ingest SMS while the PC holds the ledger. Once the phone has accepted the hand-back and is unlocked, it reads bank SMS since the last durable marker, routes known formats through the existing import-review and category rules, and stores message identity so a retry cannot post twice. Unclear messages wait for review; later CSV imports must recognize SMS-posted activity to avoid duplicates. Build and test parsers bank by bank from sanitized examples, including unknown formats. Messages deleted before the phone reads them may be missed, and the app must make that limitation clear. Android SMS access and Play distribution requirements require a separate platform acceptance check.

## Speed and build gates

Claude measured a 0.8 MB encrypted sample with 319 transactions in this container: copying plus SHA-256 took 5 ms, integrity checks 8 ms and a full re-encrypting snapshot with inventory checks 50 ms. These are **local sample measurements**, not phone or Wi-Fi handoff measurements. The product target is a handoff of seconds; prefetch hides transfer behind password entry when it can. Measure 1, 10, 50 and 100 MB encrypted profiles on ordinary PCs and a mid-range Android phone, reporting snapshot, network, verification and durable-commit time separately. No “few seconds at most” guarantee follows from the sample.

Build in finished gates:

1. Complete verified single-PC backup restore and candidate promotion, including crash, full-disk and old-version tests. This is already a release gap.
2. Implement Pair, prefetch, Lend, local working copy, recovery copies, Hand back, idempotent receipts and Take back between two PCs. Keep the same profile format and a swappable transport. Inject failure at every durable write and network boundary; assert one accepted lineage and one cooperative writer.
3. Prove the existing Python, `sqlcipher3`, `cryptography`, FastAPI and WebView stack on a real mid-range Android phone. Measure unlock, pages and large-profile handoff before committing to the Android shell.
4. Make the phone home, use private storage with Android Auto Backup excluded, and adapt the shared pages under the brand guideline. Test phone sleep, process death, local-network changes and foreground-service limits.
5. Add bank SMS ingestion only when the phone holds an accepted ledger, with deduplication, review and later CSV matching. Run a cross-device Mohab year, restore drills and a full fault matrix before real financial data.

The major remaining technical bet is Android compatibility with the pinned Python, SQLCipher and compiled dependencies. The major protocol tradeoff is deliberate: offline PC editing preserves availability but any changes not yet received by the phone can be lost with that PC. Lightning must always show the last accepted and last recovery versions so the owner can see that risk.

## Sources

- SQLite documents safe live snapshots and warns against raw file copies during active transactions: <https://www.sqlite.org/backup.html>, <https://www.sqlite.org/howtocorrupt.html>.
- SQLCipher documents page-integrity verification: <https://www.zetetic.net/sqlcipher/sqlcipher-api/>.
- Android documents private app storage, default Auto Backup behavior and foreground-service restrictions: <https://developer.android.com/training/data-storage/app-specific>, <https://developer.android.com/identity/data/autobackup>, <https://developer.android.com/develop/background-work/services/fgs/restrictions-bg-start>.


---

## Review by Claude (2026-10-04, revised the same day): not part of Codex's proposal

Superseded where it differs from the proposal above. Prefetch pauses writes or uses `snapshot()`; a locked phone holds a return as *received, checking* until verified at unlock; a lend ends only by the borrower's durable, authenticated cancel for that checkout ID; speeds are targets until measured on a phone; `audit_log` is not a full change record.

**This is a review, written by Claude at the owner's request. Everything above this line is Codex's proposal, unchanged apart from a one-line pointer under its status.** It records the owner's requirements (given on 2026-10-04, after the proposal was written), audits the proposal against the code, and recommends how to build it. Where the owner's requirements conflict with the proposal, the requirements win. No code was changed. Codex: revise the proposal, or answer under *For the owner* in `NOW.md`.

*Revision note.* An earlier version of this review recommended that the PC only show pages served by the phone. The owner rejected it: a PC must keep working if the phone goes quiet. That version also guessed that a checkout would take about a minute; measured, the work takes milliseconds (Review 3). This version replaces it.

### Review 1. The owner's requirements

1. **The phone is home, and it is mobile.** It holds the database and lends it to whichever paired PC or laptop wants to edit, one at a time, at home, at work or travelling.
2. **Connect once, then work alone.** One short exchange over Wi-Fi, then the PC edits its own temporary copy. If the phone goes quiet, the PC keeps working.
3. **The phone writes too.** It edits when the ledger is at home. A planned feature records bank SMS automatically (see requirement 8).
4. **A hand-off of seconds**, not a minute.
5. **The easiest path to build, with the lowest downside.**
6. **Fetch while the user types the password.** When the PC app opens and the phone is reachable and trusted, the transfer starts at once, so it is finished by the time the password is typed.
7. **Save often while lent.** The PC saves before it closes. While lent, it also sends the phone a recovery copy at an interval (about every 3 minutes), because people record or import and then spend a long time just reading.
8. **The phone reads SMS only when it holds the ledger.** It does not capture during a lend; when the ledger comes home, it reads the bank SMS that arrived since its last read.
9. **Everything stays local.** No cloud copies; an opt-in may come later.

### Review 2. Audit of the proposal

**The core is right for these requirements:** one writer at a time with checkout and check-in. Keep its safety principles: never open a live SQLite file over a network; never merge databases or choose "the newest file"; record durably before granting or acknowledging; epochs, checkout IDs and return IDs; a receipt that is not acceptance; fail-closed repair; new-lineage recovery; Android Auto Backup excluded; per-device password slots; a fault-injection gate before real data. Its claims about current code are accurate: `snapshot.py` verifies inventory and fsyncs; `staging.py` stages but never promotes; `keys.py` wraps one data key per password slot.

**Gaps:**

1. **It is bigger than version 1 needs.** Reader nodes, published checkpoints, a separate version store with a pointer resolver, role permissions and a future server home are not required by Review 1. Cut them from version 1 (Review 3 lists what stays).
2. **No plan for bank SMS.** Bank SMS keep arriving while a PC holds the ledger. The owner's answer: the phone reads them once it holds the ledger again (requirement 8, Review 3).
3. **OneDrive.** Profiles live under Documents (`runtime/paths.py`), which Windows often redirects to OneDrive. A borrowed copy, its control record and its recovery copies must live outside synced folders (`%LOCALAPPDATA%`). Immutable encrypted backups may stay in Documents.
4. **The foundation is unfinished single-PC work.** Promoting a verified copy and restoring a backup are not built, and both block the release anyway (`NOW.md`). Build them first.
5. **Hidden writers need a database-level guarantee.** Legacy startup posts revaluations and refreshes prices (`lightning/main.py`, about lines 90–100), and unlock can migrate. Open the copy a device does not hold the pen for read-only at the database (`Database(read_only=True)` exists), not through a check at every call site. Page views are safe: the remembered period is a cookie.
6. **Use `audit_log` as the change record.** It is written in the same transaction as every edit. It tells whether a borrowed copy has unreturned changes, and lists them if a lend is ever force-taken back.
7. **Device authentication is about network access, not trust between devices.** Every paired device holds the data key, so pairing decides who may connect and borrow, nothing more.
8. **Smaller:** schema lockstep means the Windows ZIP and the Android app update together; `os.fsync` cannot flush a folder on Windows, so the phone, not the PC, is the commit point that matters.

### Review 3. Recommended structure: the phone lends, a PC borrows

```
PHONE: home, travels with you
├─ ledger         profile.db (SQLCipher), private app storage, last few copies kept
├─ lend record    durable: at home, or lent to <device> with checkout ID and epoch
├─ recovery copy  the latest copy a borrowing PC sent (unaccepted; for take-back only)
└─ SMS marker     in the ledger: the last bank SMS already read

PC or laptop: borrows on demand
├─ borrowed copy  %LOCALAPPDATA%\Lightning, never in OneDrive
├─ lend record    durable: borrowing <checkout ID>, returning <return ID>, done
└─ backups        every returned copy kept as an encrypted backup of the phone
```

**Measured speed (this container, Mohab's sample profile, 319 transactions, 0.8 MB encrypted):** copy plus SHA-256 5 ms; open plus `integrity_check`, `foreign_key_check` and `cipher_integrity_check` 8 ms; a full re-encrypting `snapshot()` with inventory checks 50 ms. A phone may be several times slower and a heavy profile tens of MB, which is still a few seconds at most. **The hand-off time is the Wi-Fi transfer.** The database uses the default rollback journal (no WAL), so with writes paused, the file on disk is complete and can be sent byte for byte.

**Checkout: fetched while the password is typed (owner's requirement 6):**

1. **On opening**, the PC app finds the phone on Wi-Fi (Android NSD/mDNS; convenience only) and connects with pinned mutual TLS. The devices were paired once by QR: the phone scans the PC's code and the owner approves.
2. **Prefetch, before any password.** The phone sends its database file as it stands, with its hash and a small manifest (profile ID, lineage, schema version). This is still the phone's ledger: nothing is lent yet, so the phone keeps writing. The file is SQLCipher ciphertext, so sending it before anyone unlocks exposes nothing. The PC stores it in staging and checks the hash.
3. **On unlock**, the PC opens the staged copy with its own password slot and runs the checks (about 8 ms), then asks to borrow *that hash*.
4. **The lend itself is a few bytes.** If the phone's file still has that hash, the phone stops writing, durably records *lent to this PC* with a new checkout ID and epoch, and grants it. If the phone changed in the meantime (it read new SMS, say), it re-sends the file first: under a second for profiles of a few MB.
5. The PC durably records the checkout and promotes the copy. **From here the PC needs nothing from the phone.** If the grant never arrives, the PC records *checkout aborted* before the phone may write again.

Opening the PC app without unlocking costs nothing: the phone never stopped writing.

**While lent:**

- The PC edits normally, offline included.
- **Recovery copies (owner's requirement 7):** when the borrowed copy has changed (`audit_log` grew), the PC sends it to the phone at most every 3 minutes, and always before closing. The phone keeps only the latest one, marked *unaccepted*: it is never the ledger, and is used only by an explicit take-back. If the phone is out of reach, the PC skips that send and keeps a local recovery snapshot (50 ms) instead.
- The phone shows its last copy read-only: "Lent to Office PC since 14:05".

**Return (the same few seconds):**

1. The owner presses **Hand back**, or closes Lightning, which saves and hands back. The PC first checks that the phone is reachable. If it is not, the PC keeps the lend and hands back automatically next time they meet.
2. Once reachable, the PC stops writes, durably records *returning* with a return ID, and sends the file.
3. The phone checks the hash, manifest, epoch and checkout ID. **This needs no key**, so the phone does not have to be unlocked: a trusted PC already opened and checked the copy. It renames the file into place (an atomic rename in its private folder), keeps the previous copy, records *at home*, and replies with a receipt. A repeated return ID gets the same receipt. The next time the phone app is unlocked, it opens the copy and runs the full checks once. If they fail, it goes back to the previous copy and asks the PC for its backup.
4. The PC records the receipt and keeps the returned file as a backup.
5. **SMS (owner's requirement 8):** once the phone holds the ledger again and is unlocked, it reads the bank SMS that arrived since its marker. It posts them through the existing import review and category rules: confident ones post themselves, unclear ones wait. Each SMS is stored with its identity, so none posts twice, and each is matched against later statement CSVs (roadmap M7). An SMS deleted before the phone reads it is missed.

**When things go wrong:**

| Event | What happens |
|---|---|
| The phone goes quiet during a lend | Nothing. The PC keeps working and hands back later. |
| Wi-Fi drops mid-return | The PC stays read-only and retries the same return ID; the phone answers idempotently. |
| A forgotten lend | The phone cannot edit, and SMS wait in the phone's inbox until the ledger comes home. Nothing is lost. The phone reminds the owner. |
| The borrowing PC is lost or dead | **Take back** (explicit, owner only): the phone resumes from the PC's latest recovery copy as a new lineage. At most about 3 minutes of edits are lost, and the warning says so. If that PC comes back, Lightning lists its later edits from `audit_log` for re-entry. It never merges them. |
| The phone is lost while lending | The PC holds the newest data. Pair a new phone and hand it home as a new lineage. |
| The phone is lost while at home | Restore from the newest copy the PC holds. Edits made on the phone since then are lost; SMS can be read again from the bank's messages on the new phone. No cloud copy (owner's requirement 9). |

**Cut from version 1:** a capture queue and an always-on SMS receiver (owner's requirement 8), cloud backups (requirement 9), reader nodes and published checkpoints (the phone is the reader), a separate version store and pointer resolver (the phone keeps its live file plus a few previous copies), role permissions (every paired device may borrow), remote reachability and a server home. All can be added later without changing the lend protocol.

**Remaining downsides:**

- The PC must be near the phone to start or end a lend: the same Wi-Fi, the phone's hotspot, or a USB cable.
- A forgotten lend blocks editing on the phone, and its SMS wait.
- Starting a lend takes one tap on the phone. After that, a notification-backed background service carries it until the ledger is home (Review 5).
- Python on Android is the biggest technical bet.
- Every paired device can decrypt the profile.
- App versions must match across devices.

### Review 4. Build order, with gates

1. **Single-PC restore and promotion** (release blocker anyway), with power-loss and disk-full tests on Windows.
2. **Lend and return between two PCs**, one acting as home: pairing, prefetch, the lend records, transfer, 3-minute recovery copies, receipts, take-back, a crash test at every durable step. This proves the whole protocol on familiar ground, and it gives PC-to-laptop lending even if Android slips.
3. **Android spike** on a real mid-range phone: Python runtime, `sqlcipher3`, `cryptography`, FastAPI in a WebView. Measure unlock time, page times and a lend of a large profile. **Gate:** an unreliable build, or pages over about a second, means a rethink before step 4.
4. **Phone as home:** private storage, Auto Backup off, phone-width screens under the brand guideline.
5. **Bank SMS:** read new SMS since the marker when the phone holds the ledger; parse each bank's format; post through the existing import review with category rules; match against later statement CSVs, so nothing counts twice (roadmap M7). Google Play requires a permissions declaration for SMS access; budgeting apps such as Say already read bank SMS, so prepare that declaration.
6. **Fault gate on a PC and a phone**, then a full Mohab year driven across both, before any real financial data.

### Review 5. The owner's answers, and what is still open

Answered 2026-10-04 (now requirements 6–9 in Review 1):

1. Accepting a return: prefetch when the app opens, so the hand-off is done by the time the password is typed. The phone accepts a return without being unlocked (hash and manifest), and checks it fully at its next unlock.
2. Closing the PC saves and hands back; while lent, a recovery copy goes to the phone about every 3 minutes.
3. A borrowing PC does not pull SMS; the phone reads them once it holds the ledger again.
4. SMS through Google Play: apps such as Say do it, so plan for Play's SMS permissions declaration.
5. Bank SMS formats: still open. Each bank words its messages differently, so the parser needs a few real examples from each bank the owner uses, with the numbers changed.
6. Backups: local only; a cloud opt-in may come later.

Answered later the same day:

- **Being found by the PC:** the phone app runs in the background **only while something is happening**, never all the time. One tap starts it: the owner opens the phone app (Lightning says "Open Lightning on your phone"). From then until the ledger is home again, an Android foreground service keeps the phone reachable. It shows a notification ("Ready for your PC", then "Lent to Office PC") and stops by itself when the ledger is home, or after a few idle minutes if no lend starts. Recovery copies and the hand-back need no app open. Waking the phone with no tap would need a cloud push service, which requirement 9 rules out.
- **Bank SMS formats:** no samples yet. Make time to log how each bank words its SMS, bank by bank, as examples are gathered.

### Review 6. Further improvements (Claude's suggestions)

1. **Background only during a lend** (owner agreed, Review 5). Without it, Android pauses the app once the phone is put down, and the 3-minute recovery copies and the hand-back on close stop reaching it.
2. **Closing the PC with the phone out of range** (refined with the owner).
   - **The PC** saves a final sealed copy, ready to send, in `%LOCALAPPDATA%` (never OneDrive). It says "Your phone isn't nearby. Your changes are saved here and will go back the next time both are on." It keeps the lend: reopened before it meets the phone, it simply carries on editing. That is safe, because the phone still records the ledger as lent to this PC. It records *returning* and stops editing only when it actually starts sending. A small background task hands back as soon as the phone is reachable while the PC is on.
   - **The phone** cannot tell a closed PC from one editing out of range; it only sees silence, so it tracks the last contact. After about 15–30 minutes of silence, its background service stops (battery) and a scheduled reminder takes over, which needs nothing running. **Reminders:** after about 8 hours, "Your ledger is still on Office PC. Last copy here: 14:05. Turn on Lightning on that PC with your phone nearby." Then once a day, plus a banner in the app.
   - After a few days, the reminder also offers **Take back** (Review 3, "When things go wrong"), naming the time of the latest recovery copy the phone holds. The owner sets the timings; the numbers here are starting points.
3. **Each prefetch is a backup.** Every PC launch fetches the phone's file (Review 3, checkout step 2). Keep the last few as encrypted backups of the phone. With everything local, losing the phone at home then costs only what changed since the PC last opened.
4. **Teach SMS formats bank by bank.** An SMS from a bank sender in a format Lightning does not know goes to review. The owner marks the amount, date and counterparty once, and Lightning saves that as the pattern for that bank. Each saved pattern, with its numbers changed, becomes a test fixture. This is how the owner's "log each bank over time" happens without collecting samples upfront.
5. **One rule for app versions.** The phone updates from Google Play; the PC is updated by hand. Only the home phone ever migrates the database. A PC whose app cannot open the phone's schema does not borrow, and says "Update Lightning on this PC", with the download link.

### Review 7. Names for every part

One name per thing, in code, docs and tests. The words a person sees on screen are in the last column, under the brand guideline's plain-words rule. Codex's names are kept where they exist: home node, writer node, reader node, working copy, accepted version, lineage. When this is built, these move into the Glossary.

**Devices** (permanent, set by pairing):

| Name | What it is | On screen |
|---|---|---|
| Home node | The phone. It holds the ledger, and is the only place a returned copy becomes an accepted version. | "your phone" |
| Paired device | A PC or laptop paired once with the home node by QR. It has a name the owner picks. | "Office PC" |

**Roles** (who may edit right now; exactly one writer at a time):

| Name | What it is | On screen |
|---|---|---|
| Writer node | The one device that may edit now: the home node while the ledger is at home, or a borrower during a lend | — |
| Borrower | A paired device while it is the writer node. **This is the PC with the temporary file.** | "Editing on this PC" |
| Reader node | A device showing a copy it may not edit: the home node during a lend (later, other paired devices too) | "Lent to Office PC · read only" |

**Copies** (files):

| Name | What it is | Where |
|---|---|---|
| Ledger | The accepted database | Home node, private app storage |
| Accepted version | Each ledger the home node accepted, numbered, with its lineage | Home node (current, plus the last few) |
| Prefetch copy | The ledger fetched when the PC app opens, before the password is typed; becomes the working copy if a lend starts | Paired device, `%LOCALAPPDATA%` |
| Working copy | The borrower's editable copy: **the temporary file** | Borrower, `%LOCALAPPDATA%` |
| Recovery copy | The working copy sent to the home node about every 3 minutes; never accepted, used only by Take back | Home node (latest only) |
| Sealed copy | The borrower's final working copy, saved on close while the phone is away, waiting to be handed back | Borrower |
| Backup | An encrypted copy kept for restore: prefetch and returned copies on the PC, previous accepted versions on the phone | Both |

**Actions:**

| Name | Codex's name | What happens | On screen |
|---|---|---|---|
| Pair | pairing | Once per device, by QR | "Pair this PC" |
| Lend | checkout | The home node grants the writer role to a paired device | "Lent to Office PC" |
| Hand back | check-in, return | The borrower returns its working copy; the home node accepts it | "Hand back" |
| Take back | explicit recovery | The owner ends a lend without a hand-back; the home node resumes from its recovery copy as a new lineage | "Take back" |

**Lend states** (the durable lend record on each side):

- Home node: **At home** → **Lent** (to a borrower) → **Returning** → **At home**; or **Needs repair**.
- Borrower: **Prefetched** → **Borrowing** → **Hand-back pending** (closed while the phone was away) → **Returning** → **Handed back**; or **Aborted** (the lend never started).

### Review 8. What Codex should do with this

- Record the owner's requirements (Review 1) and answers (Review 5) in the Project Overview under *Product decisions that must hold*.
- Revise the proposal above: the phone as the default home; checkout as the core; version 1 cut as listed in Review 3; bank SMS read on return; the measured, byte-for-byte transfer.
- Use the names in Review 7 throughout the revised proposal.
- Raise any disagreement under *For the owner* in `NOW.md`, not by editing around this review.
