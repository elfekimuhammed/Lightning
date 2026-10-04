# Multiple devices: home node and checkout protocol

**Status:** architecture proposal, 2026-10-04. No synchronization code has been built. This document records the owner's direction and the safety design to test before implementation.

*Added by Claude, 2026-10-04:* a **review** of this proposal, with the owner's new requirements and a recommended structure, is appended at the end under "Review by Claude".

## Decision and vocabulary

One Lightning codebase serves PC and Android. A user chooses one **home node** for each profile: initially a PC or laptop, later possibly a server. The home node coordinates access and holds the canonical database plus published encrypted checkpoints. A paired **reader node** may display a published checkpoint. At most one node is the **writer node**: the home node itself while the profile is at home, or a paired node holding an explicit checkout. The copy on a checked-out writer is its **working copy**. A returned copy becomes accepted only after the home node verifies and durably commits it.

“Writer” is the name for the temporary role. The home node remains the permanent coordinator and home for accepted versions. During a checkout, however, unreturned edits exist only on the writer (and any separate recovery copies). The home node's database is then the last accepted version, not necessarily the newest data. Reader screens must say which version they show and whether a checkout is in progress.

The initial product is single-user and single-profile-at-a-time. A future server may host several independent profiles, each with its own state machine and encryption key. No device opens the SQLite file over a network filesystem or syncs a live profile folder through a cloud drive.

## Guarantees and their limits

1. **One accepted history.** The home node accepts a returned snapshot only from the current writer, for the exact checkout and parent version it granted. Every accepted version has one predecessor. Stale or duplicate returns cannot overwrite a newer version.
2. **One cooperative writer.** Lightning's own software allows writes only on the node named in its durable checkout record. The home node becomes read-only before it issues a permit. A reader never writes, migrates, runs startup catch-up, or restores a backup. A local OS file lock still prevents two Lightning processes on one machine.
3. **No silent replacement.** Every handoff and check-in keeps the previous accepted version and the writer's working copy until the new version is verified, committed, and acknowledged. Ambiguous states stop writes and ask for repair; they never choose the newest-looking file.
4. **Detectable integrity failure.** Transfer hashes detect missing or changed ciphertext. Opening with the profile key, SQLCipher page checks, SQLite integrity and foreign-key checks, schema/version checks, and an application inventory check reject an invalid candidate. A hash alone does not prove that a database is healthy.
5. **Known durability boundary.** An edit is locally committed when SQLite commits on the writer. It is accepted by the home node only after check-in acknowledgement. Until then, loss of the writer and all of its recovery copies can lose that edit. The UI must always say when changes are only on the writer. No protocol can recover bytes that were never sent or backed up.
6. **Availability is secondary to safety.** A checkout never expires automatically. Network loss, sleep, restart, clock changes, and a lost acknowledgement cannot silently give writing permission to another node. If the writer is lost, explicit recovery starts a new history branch and quarantines the old checkout. Old copies may contain edits the home node has never seen.

These guarantees assume non-malicious, up-to-date Lightning clients and honest local storage/OS behavior. A compromised device or someone editing files outside Lightning can still copy data or create a divergent local database. The home node can reject its return, but cannot remotely prevent an offline device from changing its own files.

## Components and storage

```text
                          authenticated snapshot protocol
reader nodes  <-------------------------------------------->  home node
   read-only                                            coordinator + version store
                                                            | current writer at home
                                                            |
writer node  <---------------------------------------------> |
 working copy      checkout permit / encrypted return      |
```

- **Shared core:** existing Python finance services, FastAPI routes, Jinja templates, CSS, migrations, SQLCipher database format, and profile encryption. Platform shells differ: WebView2 on Windows; an Android shell/WebView and Python runtime on Android. Any Android-specific database adapter must implement the same database contract and pass cross-platform fixture tests; it must not create a second finance implementation.
- **Home-node coordinator:** a new service outside the browser UI. It serializes profile transitions with the existing request/session gate. It has a durable per-profile control record. Its network listener is separate from the current loopback-only UI server; the current `Guard` cookie and localhost checks are not remote-device authentication.
- **Version store and home working file:** immutable, encrypted accepted checkpoints plus manifests are separate from the home node's writable home database. While `AT_HOME`, that home database is canonical and readers may lag behind its most recently published checkpoint. Before checkout, freeze it and publish a checkpoint containing all committed home edits. At check-in, verify the candidate, retain it as an immutable checkpoint, and prepare a separate verified writable home copy. A control database identifies the active home file, last accepted checkpoint, and current checkout. Commit changes its durable pointers only after all newly referenced files and directory entries are flushed. Keep the prior accepted checkpoint and home recovery copy until retention/backup policy permits pruning. Implement and test the exact Windows and Android filesystem durability sequence; a multi-file rename is not itself a transaction.
- **Local node record:** paired device identity, role, accepted version/hash, checkout ID and epoch, working-copy path, dirty state, and last acknowledged return. Persist it before enabling or disabling writes. Do not infer who holds the writer role from file timestamps, folder names, or a lock file copied from another machine.
- **Profile identity:** immutable random profile ID; independent random home node ID and device IDs. A monotonically increasing checkout epoch and random checkout ID fence older permits. A version manifest binds profile ID, lineage ID, parent version/hash, version number, schema and protocol versions, key ID, snapshot byte length/hash, writer device, checkout ID, and creation time. Time is for display only, never ordering or expiry. The home node authenticates the manifest; the transport binds it to the paired sender.
- **Keys:** the SQLCipher data key remains the same across copies. Pairing must provision it only after the user unlocks and authorizes that device, over an authenticated encrypted channel. Each device stores its own password-wrapped key slot; do not send a password or blindly copy `keys.json`. Keep the existing recovery-key meaning. A paired reader can decrypt the profile and therefore must be treated as trusted with its contents.

**Current-code implications.** `lightning/database/snapshot.py` already creates and verifies encrypted snapshots, including committed journal/WAL data; use it as a starting primitive, not as the whole handoff. `lightning/database/staging.py` already stages candidates but does not promote them. `ProfileSession`, `SessionGate`, startup backups, migrations, and any automatic valuation/catch-up must consult the new role gate before touching the database. The current profile layout has a fixed live `.db` path; versioned promotion needs a resolver/pointer design and must preserve the existing profile/import/backup behavior.

## State machine

The authoritative control record is per profile. It is stored transactionally and re-read on every restart. The role gate also checks it before each write request, not only when a page is rendered.

| State | Accepted data | Allowed writer | Allowed actions |
|---|---|---|---|
| `AT_HOME` | Home node's live home database; published reader snapshot may lag | Home node | Read, write, publish reader snapshot, or begin checkout |
| `PREPARING` | Last accepted version | None | Drain writes, make/verify snapshot, stage transfer; abort before permit if safe |
| `CHECKED_OUT` | Last accepted version; writer may have newer local edits | Named writer only | Home node/other nodes read accepted snapshot; writer writes working copy or returns it |
| `RETURNING` | Last accepted version plus staged candidate | None | Writer has durably stopped writes; transfer, verify, retry, or repair |
| `COMMITTED` | New accepted version | Home node | Idempotently acknowledge check-in; writer remains read-only |
| `NEEDS_REPAIR` | Last known accepted version retained | None | Diagnose, compare recovery copies, explicit owner recovery |

`COMMITTED` may immediately become `AT_HOME` once the writer's durable stop-write declaration and home node commit are established. An unreceived acknowledgement does not let the writer resume: it retries the same return ID and receives the same answer. No automatic lease timeout exists.

**Invariant:** the home node never grants checkout B while checkout A is unresolved. A newer epoch fences old returns at the home node, but cannot force an offline old client to stop local writes. Recovery therefore creates a new lineage and warns that the old copy may diverge.

## Checkout: home node to writer

1. The paired requester authenticates and asks to check out a named profile. Both sides check protocol/schema compatibility, available storage, and whether the requester already has unreturned work. A device with an unresolved working copy cannot accept a fresh checkout.
2. Under the profile gate, the home node stops new writes, drains active requests, closes write connections, and creates a verified encrypted snapshot. It retains a pre-checkout recovery copy and records the base version/hash. If snapshot or durable control write fails, it remains or returns to `AT_HOME`; no permit is issued.
3. Transfer the snapshot to a new staging path on the requester in bounded, authenticated chunks. Resume is permitted only for the same snapshot hash and checkout attempt. The requester checks length/hash, unlocks it with the profile key, verifies database and schema, and persists its staged record. It is still read-only.
4. The home node durably records `CHECKED_OUT` with the requester device, base version, new epoch and checkout ID **before** sending a signed/authenticated permit. From that point it refuses every finance write, including hidden background writes and migrations.
5. The requester durably records the exact permit and promotes the staged snapshot to its working copy. Only then does its role gate permit writes. It acknowledges activation. A lost activation acknowledgement leaves the home node checked out; status/retry resolves it. The home node never assumes failure means it may write.

The transfer can be cancelled safely before step 4. After step 4, cancellation requires a return or an explicit recovery procedure, even if the requester says it never received the permit: the home node cannot prove that assertion after a network failure.

## While checked out

- The writer uses a local SQLCipher database and ordinary SQLite transactions. It can keep working without network access. Mark its durable state dirty **before admitting a write**; a failed write may leave a conservative dirty flag, but a crash cannot leave committed edits falsely marked clean. The app shows **“Changes on this device; not yet returned to [home node]”** and the time of the latest local recovery copy.
- Make verified encrypted local backups during a long checkout and before app shutdown. When connected, optionally upload **recovery checkpoints** to the home node. These are clearly marked *unaccepted* and never become reader-visible or grant anyone writing permission. This reduces possible loss if the writer device dies; it does not change the single-writer rule.
- The home node and other nodes may read only the last published checkpoint while checkout is active. Their UI shows its version/time and **“[device] is editing; newer changes may exist.”** Readers can also lag while the home node is editing at home, until it publishes a new checkpoint. If current remote reads are later required, design a separate writer-served read path; do not pretend a stale snapshot is current.
- A writer update that includes a schema migration is allowed only if the home node and every required node can understand the returned schema. Initially require the same compatible app/protocol release on home node and writer and block checkout/check-in across incompatible versions. Preserve the pre-migration snapshot.

## Check-in: writer to home node

1. Writer requests return. Its gate stops new writes, drains active requests, completes transactions, creates a verified encrypted snapshot, and retains the live working copy plus a recovery backup. It durably records `RETURNING`, including snapshot hash and a random return ID. From this point it cannot resume writes, even after restart or network loss.
2. Writer sends an authenticated stop-write declaration bound to the return ID and snapshot hash. Home node durably records `RETURNING`, then accepts the snapshot and manifest in bounded chunks. It requires matching profile, lineage, epoch, checkout ID, parent version/hash, key ID, schema compatibility, and size limits. It stores bytes at a new staging path; a transfer failure leaves `RETURNING` and the old accepted version intact.
3. An unlocked home node verifies ciphertext length/hash, opens the candidate with SQLCipher, runs page integrity, SQLite integrity and foreign-key checks, validates migration state and application inventory, and compares expected profile identity. It never tries a plaintext fallback. It retains a verified pre-check-in backup. If validation fails, it reports the reason category without secrets and keeps both copies for repair.
4. Home node flushes the candidate and immutable manifest, prepares and verifies a separate home working copy, then transactionally moves its control pointers to the new accepted checkpoint and home file and records the consumed return ID. Only after durable commit does it send the receipt. The previous version and home recovery copy are retained. If the home node crashes between commit and receipt, the same return ID yields the same receipt; it never installs twice.
5. Writer verifies the receipt matches its snapshot hash/version, durably marks its permit consumed, and remains read-only until a future checkout. It keeps its recovery copy under retention policy. Home node can resume its own writes after step 4 because the writer has already durably stopped writes in step 1.

Do not acknowledge *receipt of bytes* as *accepted version*. If the home node is locked and cannot open SQLCipher, it may hold an encrypted pending upload but must say **“received, awaiting verification”**; the writer stays in `RETURNING`. Whether the home node may keep its database key available for unattended verification is a separate key-custody decision.

## Network and security boundary

- Use a dedicated authenticated transport, initially direct over the local network. Discovery is convenience only; it never establishes trust. Pair by explicit approval on the home node, with a one-time code/QR and displayed fingerprint. Pin device identities; support explicit revocation. No public internet listener by default.
- Use a mature TLS 1.3 implementation with mutual device authentication, or an equivalently reviewed library; do not invent encryption or certificate validation. Separate permissions: reader, eligible writer, profile administrator. A reader cannot request checkout unless granted writer eligibility. Reauthenticate privileged transitions and protect against replay with checkout/return IDs and epochs.
- SQLCipher protects database snapshots at rest; TLS protects transfer. The transport must also authenticate manifests and enforce body size, chunk size, free-space, rate, and connection limits. Never log keys, passwords, recovery phrases, financial rows, transfer URLs/tokens, or raw exception text.
- Device private keys belong in OS-protected storage where available. The database and control files stay in private app storage with restrictive permissions. On Android, explicitly choose backup rules: default Auto Backup can include app-private files, so do not accidentally upload the home node record or an unreturned working copy to a cloud account.
- A lost/stolen paired device is a confidentiality incident: revoking its future network access does not erase snapshots or keys already on it. The current SQLCipher data key is shared among authorized devices; key rotation and old-backup handling need their own planned migration.
- The existing UI server remains loopback-only with its present Host/Origin/cookie/CSP protections. The sync listener does not expose finance routes or turn the WebView into a network API client. Pairing and transfer calls pass through a narrow typed service API and the session gate.

## Failure and recovery rules

| Event | Required behavior |
|---|---|
| Connection dies before permit | Discard/retry staged bytes; home node may resume writing only if it has not recorded the permit. |
| Connection dies after permit | Home node stays read-only; requester checks durable status and retries activation or return. No timeout takeover. |
| Writer crashes/restarts | Reopen only the recorded working copy with the same permit; do not take a fresh checkout. Keep local backups. |
| Home node crashes/restarts | Recover control state and accepted pointer before opening finance routes; verify referenced files. If any state/file mismatch, enter `NEEDS_REPAIR` read-only. |
| Check-in upload is partial, corrupt, or disk is full | Reject candidate, preserve previous accepted version and writer copy; retry the same return ID after repair. |
| Receipt is lost after commit | Home node answers repeated return ID with the original receipt; writer remains read-only until it records that receipt. |
| Wrong key, incompatible schema, or failed integrity check | Refuse promotion. Preserve both copies and show a specific repair state; never silently choose one. |
| Home node is offline | Existing checked-out writer may continue locally; no new checkout, check-in, or fresh reader snapshot. |
| Writer device is unavailable or destroyed | Home node remains checked out. Owner may recover a verified recovery checkpoint or last accepted version only through an explicit new-lineage procedure that states the possible lost edits. Old permits can never check in to the new lineage automatically. |
| Home node device/storage is lost | Restore its control record and accepted versions from verified backups. Compare paired devices' remembered version/epoch before allowing writes. If the history cannot be proved, enter repair and choose a new lineage explicitly. |

Never resolve a conflict by modification time, “latest file,” merging SQLite databases, or overwriting one copy. A manual branch recovery may need a human to inspect unreturned transactions and re-enter them; that is a separate repair workflow, not automatic merge.

## Downside audit and design pressure

This design deliberately buys simple financial history by making availability and some convenience worse. These are product costs, not edge cases to hide from the user.

| Downside | Concrete consequence | Mitigation and remaining cost |
|---|---|---|
| Home node unavailable | No new checkout or check-in; readers cannot refresh. A laptop asleep or a phone killed by Android is a weak always-on home node. | Existing writer keeps its valid working copy and backups; queue check-in. Show home node status. A later always-on server improves availability but adds hosting and key custody. |
| Long or forgotten checkout | The home node and every other device are blocked from editing for the entire checkout, including while the writer is offline. | Make current writer and checkout age conspicuous; remind the owner to check in. Do not auto-expire, because expiry can create two writers. |
| Stale reader data | Reports on readers can omit recent income, spending, balances and prices while another device or the home node edits. Acting on a stale Safe to spend figure could mislead the user. | Mark all reader pages as a published checkpoint with version/time and an editing warning. Consider restricting action-oriented figures while stale. Truly live reads require a separate writer read service. |
| Unreturned data loss | If the writer and all its backups die, its changes cannot be recovered from the home node's accepted version. The home node may not know exactly which edits were lost. | Local backups and optional unaccepted recovery uploads; conspicuous dirty status; explicit recovery warning. This risk cannot be eliminated while fully offline writes are allowed. |
| Manual recovery can fork history | If the owner breaks a stuck checkout, the old writer may later reappear with valid local edits. Its old permit cannot safely merge into the new accepted branch. | New lineage and quarantine; compare or re-enter edits manually. Never silently discard either copy. |
| More copies mean more exposure | Every reader and writer with the shared SQLCipher key can decrypt the profile; a stolen paired device or its backup broadens the attack surface. | Per-device access control, secure storage, app lock, revocation for future transfer, and encrypted backup discipline. Revocation cannot erase a copy already taken; key rotation is expensive. |
| Unattended home node conflicts with password-only unlock | The home node cannot fully verify a returned SQLCipher snapshot without the key. A headless/server home node must store or obtain a usable key. | First release requires unlock for handoff. Later unattended mode needs an explicit device-held-key threat-model decision and recovery plan. |
| Whole-database transfer cost | Each checkout/check-in moves the whole encrypted profile, even for one edited row; version retention can multiply disk use. Phones may have limited space, data plans, battery and background time. | Measure real profile sizes; use Wi-Fi and resumable chunks; enforce free-space checks and bounded retention. Incremental transfer would be a later, much more complex protocol. |
| Update coordination | A writer on a newer schema can return a database the home node or readers cannot open. | Compatibility handshake and staged app updates; block incompatible checkout/check-in and keep pre-migration versions. This may delay updates. |
| Complex state for the user | “At home”, “checked out”, “returning”, “received but unverified”, and “needs repair” require clear wording and recovery actions. | Design status and failure screens before implementation; test with Mohab. This is more visible complexity than today's single-device app. |
| New network surface | Pairing, certificates, transfer endpoints and device revocation create security work absent from the current loopback-only app. | Dedicated narrow listener, mutual authentication, strict limits, independent security review and adversarial tests. Do not expose the existing UI server. |
| Home node failure becomes central | Loss of the home node's control record can obscure who has the write permit even when database snapshots survive. | Back up control state with accepted versions, retain paired devices' remembered epochs, and fail closed on disagreement. A database backup alone is insufficient. |

**Architectural decision from this audit:** a phone should become the default home node only after real-device tests show it remains reachable enough for the intended workflow. The same protocol permits a PC or later server home node. The UX must never imply that a stale accepted snapshot includes unreturned edits.

## Build order and gates

0. **Android feasibility spike, before committing to the full mobile schedule.** On a real arm64 Android device, package the intended Python runtime, pinned `sqlcipher3` and `cryptography` dependencies, unlock a disposable existing Lightning profile, create/verify an encrypted snapshot, and run a minimal FastAPI page in WebView. If `sqlcipher3` cannot be built reliably, evaluate a narrow Android SQLCipher adapter. No second finance engine.
1. **Storage foundations on PC.** Finish safe candidate promotion and restore, versioned immutable snapshots, transactional control pointer, profile identity and durable role gate. Preserve existing single-PC mode. Test Windows power-loss/disk-full behavior and backup restore before any network feature.
2. **Protocol between two PCs.** Build pairing, authenticated transfer, checkout/check-in, idempotent retries, stale-reader labels, and explicit repair states. Start with one profile and one reader. Keep transport swappable so a future server can be the home node without changing database rules.
3. **Fault-injection gate.** Kill either process or cut the connection at every durable write, file flush, permit send, chunk boundary, commit, and receipt. Assert one accepted history, at most one cooperative writer, no silent overwrite, and preserved recovery copies. Exercise concurrent checkout requests, stale tabs, bad hashes, wrong keys, version mismatch, insufficient space, and clock changes. Run real two-PC suspend/restart and corrupted-backup drills.
4. **Android runtime and UI.** Bring the same Python services and pages to Android. Use private app storage and explicit backup behavior. Adapt shared templates/CSS to phone width under the brand guideline; run Mohab's year and real-device profile/restore checks.
5. **Android as home node, then optional server.** Reuse the PC-proven protocol. Test Android process death, phone sleep, low storage, network changes and OS backup/restore. A phone may be a poor always-available home node; the product must show when it is unreachable. A later server changes hosting and key custody, not the single-writer state machine.

**Acceptance before real financial data:** the user can identify the current writer, last accepted version, dirty/unreturned state, last verified recovery copy, and whether a reader is stale; every failed handoff has a safe retry or named repair path; restored backups cannot accidentally grant writing rights; and a full crash matrix passes on two PCs and an Android device. Mohab's finance figures must match before checkout, on the writer, and after check-in.

## Decisions still needed

1. **Unattended home node:** must the home node be unlocked and attended for checkout/check-in validation, or may it hold a device-protected key for background operation? The latter changes the current password-only threat model. First implementation can require unlock.
2. **Recovery checkpoint frequency:** local encrypted backups are mandatory; optional encrypted uploads to the home node reduce risk during a long checkout. Choose a cadence and retention limit after measuring database size and transfer cost.
3. **Reachability:** direct local-network pairing is the first transport. Remote access later needs a deliberate relay/VPN/server deployment and threat review; it is not achieved by exposing the current loopback UI.
4. **Lost-writer recovery permission:** define who may start a new lineage and how the warning records the possibility of lost edits. The technical default is explicit owner action only, with no automatic expiry.

## Source notes

- SQLite advises against directly opening a live database over a network filesystem because locking and sync semantics vary: <https://www.sqlite.org/useovernet.html>.
- SQLite's online backup API provides a consistent snapshot, and SQLCipher documents `sqlcipher_export` and `cipher_integrity_check`: <https://www.sqlite.org/backup.html>, <https://www.zetetic.net/sqlcipher/sqlcipher-api/>.
- Android private storage is suitable for sensitive app data, but its default Auto Backup behavior must be configured explicitly: <https://developer.android.com/training/data-storage/app-specific>, <https://developer.android.com/identity/data/autobackup>.
- Android Python packaging needs platform-compatible native wheels or builds: <https://www.chaquo.com/chaquopy/doc/current/faq.html>. Zetetic provides an Android SQLCipher library if a platform adapter is required: <https://www.zetetic.net/sqlcipher/sqlcipher-for-android-community/>.


---

## Review by Claude (2026-10-04, revised the same day): not part of Codex's proposal

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
- To be found by the PC, the phone app must be reachable on Wi-Fi. Android stops background apps, so this needs either the phone app open, or a foreground service with a visible notification (owner to choose, Review 5).
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

Still open:

- **Being found by the PC:** Android stops background apps. Either (a) the owner opens the phone app before using the PC, or (b) Lightning runs a foreground service on trusted Wi-Fi, which Android shows as a permanent notification and which uses some battery.
- **Which banks first**, and a few example SMS from each.

### Review 6. What Codex should do with this

- Record the owner's requirements (Review 1) in the Project Overview under *Product decisions that must hold*.
- Revise the proposal above: the phone as the default home; checkout as the core; version 1 cut as listed in Review 3; bank SMS read on return; the measured, byte-for-byte transfer.
- Raise any disagreement under *For the owner* in `NOW.md`, not by editing around this review.
