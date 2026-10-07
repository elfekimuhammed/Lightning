# Edit journal: every device writes, the home decides

**Status: proposal · 2026-10-07 · not built. Needs the owner's decision (section 1) before any code.**

Today one device writes at a time: the phone lends the ledger to one PC and gets it back ([multiple_devices.md](multiple_devices.md)). This proposal lets every paired device write at any time. Each save becomes a journal entry; the device that holds the ledger (the *decider*) applies entries one at a time through the normal services, and every device ends with the decider's ledger. Lend and hand-back stay, as the way the decider moves to a PC.

The owner's product decisions live in [Project Overview](../PROJECT_OVERVIEW.md#product-decisions-that-must-hold); the built sync design lives in [Architecture](../ARCHITECTURE.md#desktop-app-and-encrypted-profiles) (*Multiple devices*); claims live in [NOW.md](../../NOW.md). This file owns the proposed design, its rollout and its acceptance tests.

## Contents

| Section | Read it when |
|---|---|
| 1. Decision and why | Deciding whether to build it |
| 2. Guarantees | Writing or reviewing any part; these are the acceptance tests |
| 3. What the code does today | Before changing a save path or the sync code |
| 4. The model | Building the journal, the decider or a device's view |
| 5. Clashes and duplicates | Building review, or a new kind of entry |
| 6. Automatic edits | Touching payment matching, prices, SMS or anything that writes by itself |
| 7. With lend and hand-back | Changing the sync state machines |
| 8. Storage, durability and security | Building the journal store or the wire messages |
| 9. Rollout | Planning or claiming work |
| 10. Acceptance | Testing any stage |
| 11. Open questions | Before stage 1 |

## 1. Decision and why

**Owner decision needed:** replace "one device edits at a time" and "no automatic merge" (multiple_devices.md, R5 and *Deferred*) with "every paired device writes; the device holding the ledger decides, in one order, and asks the owner only about clashes".

Why (owner, 2026-10-07): a person adds a coffee on the phone in the evening while the office PC still has the ledger, imports the bank statement on the PC while the phone captured the same payments from SMS, and fixes a row on whichever device is in hand. Lend and hand-back alone cannot serve that: the phone only reads while lent, and edits on a PC the phone took back are lost.

Alternatives weighed, and why not:

| Alternative | Why not |
|---|---|
| Lend and hand-back only (today) | One writer; the evening case and lost edits after Take back stay. |
| Reconcile two copies at hand-back | Compares results without intent, so duplicates and deletes are guessed. Kept only to read a stranded old copy (section 7). |
| Every device equal, no decider | Nobody enforces money rules (a bill settled once, a closed account). Wrong for a ledger. |
| Order edits by their time alone | Device clocks drift and reorder a device's own edits. Not airtight. |
| A cloud server as the decider | The owner chose no remote finance server. |

## 2. Guarantees

Each is a test in section 10. "Airtight" means these hold under any interleaving of edits, disconnects, repeated or lost messages, crashes and revoked devices. It does not mean instant: without a server, entries reach the decider only when the devices meet on Wi-Fi.

| | Guarantee |
|---|---|
| G1 | **No lost edit.** An entry is durable on its device before the screen says Saved, and stays until the decider has accepted it or turned it down, and the device has shown which. |
| G2 | **Nothing twice.** An entry is identified by its device and that device's running number; a resend is recognised and answered with the first decision. |
| G3 | **One ledger.** Every device ends with the decider's ledger: same content fingerprint at the same version. |
| G4 | **Clashes are caught, never guessed.** An entry that changes a record the decider changed since the device saw it is applied only where fields do not overlap; otherwise it waits for the owner. Clocks never decide. |
| G5 | **Money rules hold.** Entries are applied through the same Python services as a direct save; an entry those services refuse is turned down with their reason. |
| G6 | **One order per device.** A device's entries are applied in the order it made them. |
| G7 | **Only paired devices write.** An entry from an unpaired or revoked device is refused before it is read. |
| G8 | **Full history.** Every accepted entry is kept with its device, time and version; undo is a new entry that reverses one. |

## 3. What the code does today

Checked 2026-10-07; each point shapes section 4.

- **A save is one database transaction.** `Database.transaction()` nests with savepoints, so one user action can be applied as one entry, all or nothing.
- **104 save actions** (`@router.post`) across 17 route modules: budget 18, investments 14, transactions 11, accounts 11, settings 6, reserves 6, planning 6, categories 6, rules 5, deposits 5, SMS 4, physical items 4, bank imports 4, and smaller ones. Each must become an entry kind before its area can be edited away from the decider.
- **Records have no device-made identity.** Every table uses `INTEGER PRIMARY KEY`; a transaction's `ref` comes from a per-day counter (`format_ref(doc_type, day, next_seq)`). Two devices adding on the same day make the same number and reference.
- **The app writes by itself.** Opening a profile runs migrations, seeds and an ownership repair, and fills and fetches prices (`session._fill_prices`, `live_prices.apply_finished` on the next page). Reading today's position settles bills that a posted payment already paid (`planning.match_payments`, from `position._at`). A read-only build already skips all of them (`build(read_only=True)`, `tests/test_session_roles.py`).
- **Rules categorise at save time** (`RuleService`), and bank imports match rows to existing ones on the device that imports.
- **Sync today:** pinned TLS between paired devices, signed challenges, 16 KB messages, `PROTOCOL_VERSION = 1` frozen in `tests/fixtures/sync_v1.json`, whole encrypted copies with `content_fingerprint`, verified promotion, base checkpoints kept on the home.
- **`audit_log`** records some changes with before and after values, but not every save and not with a device; it is not the journal.

## 4. The model

### Entries

One user action (one save on one screen) makes one entry:

| Field | Meaning |
|---|---|
| `device_id`, `seq` | The device and its running number. Together the entry's identity (G2, G6). |
| `kind`, `kind_version` | What it does, e.g. `transaction.add` v1, with its own validated, bounded fields. Never SQL, never a row copy. |
| `values` | What the user confirmed, fully resolved on the device: the dates typed, "today" as a date, the category after rules, amounts as text decimals. The decider never re-guesses what the user meant. |
| `creates` | Device-made IDs (UUIDs) for each record it adds, so a later entry can name a record the decider has not seen yet. |
| `changes` | For each existing record it changes or deletes: its UUID and the version the device saw. |
| `made_at`, `zone` | When it was made, on the device's clock. For display and for the default in a clash only. |
| `seen_version` | The ledger version the device's view was built on. |

### The decider

The device that holds the ledger: the phone at home, or the PC while it borrows (section 7). It keeps the **accepted journal** and the **ledger version**, a number raised by one for every accepted entry.

For each entry, in arrival order, keeping each device's own order (G6):

1. Refuse it unread if the device is not paired, or the kind or its version is unknown (G7; section 8).
2. If `(device_id, seq)` was decided before, answer that decision again (G2).
3. If `seq` is not the device's next number, hold it until the gap arrives.
4. Check `changes`: a record still at the version the device saw passes; otherwise section 5 decides.
5. Apply it through the services in one transaction, then raise the ledger version and record it as accepted with that version. A service's refusal turns it down with the refusal's words (G5).

The decider's own saves go through the same path, applied at once.

### What a device shows

Each device keeps the decider's ledger at some accepted version, plus its own entries not yet decided. Its screens show that ledger with the pending entries applied on a working copy, each pending row marked as pending. Pending rows count in no report until accepted, since one ledger records real money.

When the devices meet:

1. The device sends its undecided entries and learns each decision.
2. It receives the accepted entries after its version, and replays them on its copy through the same services.
3. It compares its content fingerprint with the decider's at that version. If they differ, for example after a code change, it takes a whole verified copy instead, as today's borrow does. Replay is fast; the fingerprint keeps it honest (G3).
4. It re-applies the entries still pending on top, and shows each accepted, turned down or waiting for the owner.

A device far behind, or new, starts from a whole copy, as today.

### Records need versions and device-made IDs

Every table an entry kind touches gets a `uid` (UUID text, unique) and a `version` (integer, raised on every change, by a trigger so no code path forgets). `ref` stays the human-facing number, assigned by the decider when it applies an add; a device shows "pending" until then.

## 5. Clashes and duplicates

| Situation | Decision |
|---|---|
| Record unchanged since the device saw it | Applied. |
| Changed meanwhile, other fields only (phone fixed the amount, PC the category) | Applied to its own fields. |
| Same field changed on both | Waits for the owner. Default: the later `made_at`, shown as a suggestion only. |
| Record deleted meanwhile | Turned down: "deleted on Phone at 14:02". The device keeps the entry visible so the user can add it again. |
| Delete of a record changed meanwhile | Waits for the owner. Default: keep. |
| Add that refers to a record turned down (a row in a new account that was refused) | Turned down with it; entries are grouped when one creates what another uses. |
| Add that looks like an existing row (same account, amount, date within 3 days, similar counterparty) | Applied, then flagged "looks like the same payment", using the bank-import matching. The owner keeps both or removes one, which is a new entry. |
| Same money as two different types (ATM: a transfer on the PC, cash in on the phone) | Flagged by amount and date across accounts. Never merged automatically. |
| A planned bill paid by two entries | The ledger allows one payment per bill and due date (`planned_payments`, unique), so the second link is refused; the row itself is applied and flagged. |
| Same name added on both (category "Gym" and "gym") | Names are canonical (Project Overview): the second add is applied as a use of the first, and the device is told. |

Waiting entries appear on the decider in a review list in the style of the phone's *From SMS*, one line each, with "Take all suggested" for the many and a choice for each. Owner choices are entries too, so every device learns them.

## 6. Automatic edits

The writes the app does by itself (section 3) run **only on the decider**, and each one it makes is recorded as an entry of the decider, so devices replay its result instead of redoing it: bill settling, price fills and fetches, SMS ingest, ownership repair. Devices open their copy with these writes off, as a read-only build does today. Migrations and seeds are not entries: a version change is section 8's compatibility rule.

## 7. With lend and hand-back

The lend protocol stays and moves the decider:

- **At home** the phone is the decider. Every PC writes through entries.
- **Lent**, the PC is the decider for the lend. It applies its own saves directly as entries, and the phone's evening coffee waits on the phone as a pending entry, shown as such.
- **Hand-back** returns the ledger with its accepted journal; the phone sends its pending entries to itself as the decider, with section 5's checks against the returned ledger.
- **Take back** (the PC is out of reach): the phone becomes the decider again from its own copy, under a new lineage as today. The PC's entries accepted during the lend are, for the phone, undecided entries from that PC; when it next meets the phone they are checked like any other. This replaces today's "the PC's edits will not come back".
- **A stranded copy with no journal** (a profile from before this change) can only be read side by side; reconcile by comparison is not built.

Over time, as more areas become entry kinds, borrowing is needed only for areas that are not entries yet.

## 8. Storage, durability and security

- **Where.** Each device keeps its undecided entries, and the decider its accepted journal, in an encrypted SQLite file beside the ledger, with the profile's key and FULL sync. Nothing financial goes in the plain control store.
- **Order of writes on a device.** Save the entry, then apply it to the working copy. At start, an entry saved but not applied is applied again; its `creates` IDs make this safe.
- **On the decider,** applying an entry and recording it as accepted happen in one transaction of the ledger, so a crash leaves both or neither.
- **On the wire.** A new `PROTOCOL_VERSION` (v1 stays frozen). Entries travel in batches inside today's pinned TLS link and signed challenge, at most 16 KB a message and a bounded batch, with a per-device limit on entries waiting.
- **Compatibility.** An entry kind carries its version. The decider refuses a kind or version it does not know, and the device says "update Lightning on this device"; a decider never guesses at an older or newer kind. A ledger migration raises the version; a device behind it takes a whole copy after updating.
- **Revoke** refuses that device's future entries; its accepted ones stay in the history.

## 9. Rollout

Each stage is shippable and tested end to end; an area not yet an entry kind is edited only on the decider (or by borrowing), as today.

| Stage | What | Done when |
|---|---|---|
| J1 | The journal store, entry identity, the decider loop, versions and UIDs on transactions and their lines, and the simulator of section 10, with no screens | G1–G8 hold in the simulator for `transaction.add` |
| J2 | Transactions from every device: add, edit amount, date, category, note and owner, delete, split; pending rows on screen; decisions shown | `tests/test_two_devices.py` gains the evening case, the both-devices edit and the review list |
| J3 | Imports as entries: SMS on the phone, bank CSVs on the PC, with the duplicate flags | SMS versus statement, case U1 below |
| J4 | Automatic edits as decider entries (section 6) | A device never writes by itself; replay converges |
| J5 | Lend moves the decider (section 7), Take back keeps the PC's entries | U9 below |
| J6+ | One area at a time: budget, planning, reserves, accounts, investments, deposits, items, rules, settings | Each area's save actions are entry kinds with tests |

## 10. Acceptance

**The simulator** (J1) runs seeded random scenarios: two to three devices editing offline and online, messages dropped, repeated and reordered, crashes between saving and applying and between applying and answering, clock skew of hours, revoked devices. After every scenario it checks:

- every device's fingerprint equals the decider's at the same version (G3);
- every entry ever saved is accepted, turned down or waiting, and its device shows which (G1);
- no entry applied twice, and each device's order kept (G2, G6);
- every account's balance equals the sum of its entries, as in a direct save (G5);
- every same-field clash reached the review list (G4);
- nothing from an unpaired or revoked device was read (G7).

**Use cases** (through the screens, extending `tests/test_two_devices.py`):

| | Case | Expected |
|---|---|---|
| U1 | The phone captured a card payment from SMS; the PC imported the statement with it | One applied, one flagged as the same payment |
| U2 | Coffee on the phone in the evening while the PC borrows | Pending on the phone; applied after the hand-back |
| U3 | The phone fixes Talabat's amount, the PC its category | Both applied |
| U4 | Both change the same amount, to 175 and 180 | Review; the later is suggested |
| U5 | The PC deletes a row the phone edited | Review; keep is suggested |
| U6 | The PC adds a row then edits it before the phone has seen either | Applied in order |
| U7 | The PC marks rent paid from the plan; the phone typed the rent | Bill settled once; the second row flagged |
| U8 | "Gym" on one device, "gym" on the other | One category |
| U9 | The phone took the ledger back; the PC meets it a week later | The PC's entries checked and applied or flagged, none lost |
| U10 | The PC's clock is three hours wrong | Order and outcome unchanged; only displayed times differ |
| U11 | The same batch is sent twice after a dropped answer | Applied once |
| U12 | A device on an older app version sends a newer kind | Refused with "update Lightning on this device"; the entry stays pending |

## 11. Open questions

- Whether the PC may decide while it borrows (section 7) or the phone always decides. Keeping the decider on the phone is simpler but needs the phone present for every PC save.
- How long turned-down entries stay visible on their device.
- Whether the decider's review is on the phone only, or also on a PC that is the decider.
- Size of the accepted journal over years: keep it all (history, G8) or fold old entries into a checkpoint.
