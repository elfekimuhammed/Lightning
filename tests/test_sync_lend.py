"""Tasks 07 and 08: lend and hand back between two nodes with real encrypted files, over an in-process link.

The phone's ledger is the round-trip dummy profile. A fake bridge stands in for the app's session: it opens
the home ledger writable, read-only or not at all, as the home node asks."""
from __future__ import annotations

import io
import json
import shutil
import uuid
from pathlib import Path

import pytest

from lightning.bootstrap import build
from lightning.database.connection import Database
from lightning.runtime.paths import borrowed_profile
from lightning.runtime.roundtrip import PASSWORD
from lightning.security.keys import unwrap_key
from lightning.sync.control import ControlStore, Peer
from lightning.sync.copies import CopyRejected
from lightning.sync.domain import Accepted, Received
from lightning.sync.service import BorrowerNode, HomeNode, LinkDown
from lightning.sync.state import BorrowerModel, BorrowerState, HomeState, ProtocolError

FIXTURE = Path(__file__).parent / "fixtures" / "roundtrip"
KEY = unwrap_key(json.loads((FIXTURE / "keys.json").read_text()), PASSWORD)


class Bridge:
    def __init__(self, live: Path):
        self.live, self.unlocked, self.mode, self.db = live, True, "home", None

    def key(self):
        return KEY if self.unlocked else None

    def set_mode(self, mode):
        self.mode = mode

    def write(self, amount="10"):
        """A home edit, as the app would make it; refused unless the home is writable."""
        if self.mode != "home":
            raise PermissionError("the phone is read-only")
        container = build(self.live, key=KEY)
        try:
            account = container.accounts.list()[0]
            food = container.categories.get_by_code("EXP.PERSONAL.FOOD").id
            container.transactions.record_outflow("2026-06-30", account.id, amount, food, counterparty="Phone")
        finally:
            container.db.close()


class DirectLink:
    """The PC's view of the home, called in-process. `drop_reply` loses the next answer after the home acted."""

    def __init__(self, home: HomeNode, device_id: str):
        self.home, self.device, self.drop_reply, self.down = home, device_id, False, False

    def _call(self, method, *args):
        if self.down:
            raise LinkDown("phone out of reach")
        result = method(*args, peer=self.device)
        if self.drop_reply:
            self.drop_reply = False
            raise LinkDown("reply lost")
        return result

    def status(self, message):
        return self._call(self.home.status, message)

    def prefetch(self, message, sink):
        header, path = self._call(self.home.prefetch, message)
        sink.write(path.read_bytes())
        return header

    def borrow(self, request):
        return self._call(self.home.borrow, request)

    def activate(self, message):
        return self._call(self.home.activate, message)

    def cancel(self, message):
        return self._call(self.home.cancel, message)

    def send_return(self, begin, source):
        return self._call(self.home.receive_return, begin, source)

    def return_status(self, message):
        return self._call(self.home.return_status, message)


class Pair:
    def __init__(self, tmp: Path, name="Office PC"):
        self.tmp = tmp
        (tmp / "phone").mkdir(exist_ok=True)
        self.live = tmp / "phone" / "profile.db"
        if not self.live.exists():
            shutil.copyfile(FIXTURE / "profile.db", self.live)
            shutil.copyfile(FIXTURE / "keys.json", self.live.with_name("keys.json"))
        self.bridge = Bridge(self.live)
        db = Database(self.live, key=KEY)
        try:
            self.home = HomeNode.enable(db, live_path=self.live, control_folder=tmp / "phone-control",
                                        home_id=str(uuid.UUID(int=1, version=4)), bridge=self.bridge)
        finally:
            db.close()
        self.device = str(uuid.uuid4())
        self.home.pair(Peer(self.device, name, "", "", ""))
        model = self.home.model
        paths = borrowed_profile(model.profile_id, root=tmp / f"pc-{self.device[:8]}")
        paths.prepare()
        ControlStore(paths.data_dir).create(BorrowerModel(profile_id=model.profile_id, home_id=model.home_id,
                                                          lineage_id=model.lineage_id, device_id=self.device))
        self.pc = BorrowerNode(paths)
        self.link = DirectLink(self.home, self.device)

    def pc_edit(self, amount="777"):
        assert self.pc.writable
        container = build(self.pc.paths.working_path, key=KEY)
        try:
            account = container.accounts.list()[0]
            food = container.categories.get_by_code("EXP.PERSONAL.FOOD").id
            container.transactions.record_outflow("2026-06-30", account.id, amount, food, counterparty="PC")
        finally:
            container.db.close()


def counterparties(path: Path) -> list[str]:
    db = Database(path, key=KEY, read_only=True)
    try:
        return [row[0] for row in db.all("SELECT counterparty FROM transactions WHERE counterparty IN ('PC','Phone') "
                                         "ORDER BY id")]
    finally:
        db.close()


@pytest.fixture
def pair(tmp_path):
    return Pair(tmp_path)


def test_full_cycle_lend_edit_hand_back_and_lend_again(pair):
    pair.pc.fetch(pair.link, KEY)
    grant = pair.pc.borrow(pair.link, KEY)
    assert pair.home.model.state is HomeState.LENT and pair.bridge.mode == "reader"
    with pytest.raises(PermissionError):
        pair.bridge.write()
    pair.pc_edit()
    receipt = pair.pc.hand_back(pair.link)
    assert isinstance(receipt, Accepted)
    assert pair.home.model.state is HomeState.AT_HOME and pair.bridge.mode == "home"
    assert pair.pc.model.state is BorrowerState.HANDED_BACK and not pair.pc.writable
    assert counterparties(pair.live) == ["PC"]
    assert list(pair.live.parent.glob("*.before-*.db"))  # the phone keeps its copy from before the hand-back
    pair.bridge.write()  # the phone edits again
    pair.pc.fetch(pair.link, KEY)
    assert pair.pc.borrow(pair.link, KEY).epoch == grant.epoch + 1
    assert counterparties(pair.pc.paths.working_path) == ["PC", "Phone"]


def test_phone_edit_after_fetch_is_never_lost(pair):
    pair.pc.fetch(pair.link, KEY)
    pair.bridge.write()
    with pytest.raises(ProtocolError) as stale:
        pair.pc.borrow(pair.link, KEY)
    assert stale.value.code == "STALE_BASE"
    assert pair.home.model.state is HomeState.AT_HOME and pair.bridge.mode == "home"
    assert pair.pc.model.state is BorrowerState.ABORTED
    pair.pc.fetch(pair.link, KEY)
    pair.pc.borrow(pair.link, KEY)
    assert counterparties(pair.pc.paths.working_path) == ["Phone"]


def test_lost_grant_reply_is_recovered_by_asking_again(pair):
    pair.pc.fetch(pair.link, KEY)
    pair.link.drop_reply = True
    with pytest.raises(LinkDown):
        pair.pc.borrow(pair.link, KEY)
    assert pair.pc.model.state is BorrowerState.BORROW_PREPARED and not pair.pc.writable
    assert pair.home.model.state is HomeState.LENT
    grant = pair.pc.borrow(pair.link, KEY)
    assert pair.pc.writable and grant == pair.home.model.active.grant


def test_return_to_a_locked_phone_waits_for_its_unlock(pair):
    pair.pc.fetch(pair.link, KEY)
    pair.pc.borrow(pair.link, KEY)
    pair.pc_edit()
    pair.bridge.unlocked = False
    assert isinstance(pair.pc.hand_back(pair.link), Received)
    assert pair.home.model.state is HomeState.RETURN_RECEIVED
    assert pair.pc.model.state is BorrowerState.RETURNING and not pair.pc.writable
    assert isinstance(pair.pc.check_return(pair.link), Received)
    pair.bridge.unlocked = True
    pair.home.recover()
    assert isinstance(pair.pc.check_return(pair.link), Accepted)
    assert counterparties(pair.live) == ["PC"] and pair.pc.model.state is BorrowerState.HANDED_BACK


def test_unreachable_phone_at_close_seals_then_hands_back_later(pair):
    pair.pc.fetch(pair.link, KEY)
    pair.pc.borrow(pair.link, KEY)
    pair.pc_edit()
    pair.pc.seal()
    assert not pair.pc.writable
    pair.pc.reopen()
    pair.pc_edit("5")
    pair.pc.seal()
    pair.link.down = True
    with pytest.raises(LinkDown):
        pair.pc.hand_back(pair.link)
    assert pair.pc.model.state is BorrowerState.RETURNING  # frozen: no more edits, whatever happens
    pair.link.down = False
    assert isinstance(pair.pc.check_return(pair.link), Accepted)  # never arrived, so it is sent again
    assert counterparties(pair.live) == ["PC", "PC"]


def test_damaged_transfer_is_refused_and_resent(pair):
    pair.pc.fetch(pair.link, KEY)
    pair.pc.borrow(pair.link, KEY)
    real = pair.link.send_return

    def corrupt(begin, source):
        data = bytearray(source.read())
        data[5000] ^= 1
        return real(begin, io.BytesIO(bytes(data)))
    pair.link.send_return = corrupt
    with pytest.raises(ProtocolError) as damaged:
        pair.pc.hand_back(pair.link)
    assert damaged.value.code == "BAD_REQUEST" and pair.home.model.state is HomeState.LENT
    pair.link.send_return = real
    assert isinstance(pair.pc.hand_back(pair.link), Accepted)


def test_copy_of_another_profile_is_kept_for_repair_not_accepted(pair):
    pair.pc.fetch(pair.link, KEY)
    pair.pc.borrow(pair.link, KEY)
    db = Database(pair.pc.paths.working_path, key=KEY)
    try:
        with db.transaction():
            db.execute("UPDATE profile_identity SET profile_id = ?", (str(uuid.uuid4()),))
    finally:
        db.close()
    with pytest.raises(CopyRejected):
        pair.pc.hand_back(pair.link)
    assert pair.home.model.state is HomeState.NEEDS_REPAIR and pair.bridge.mode == "reader"
    assert list(pair.live.parent.glob("*.incoming-*.db"))  # evidence kept
    assert counterparties(pair.live) == []


def test_second_pc_cannot_borrow_while_lent_and_take_back_fences_the_first(tmp_path):
    first = Pair(tmp_path)
    first.pc.fetch(first.link, KEY)
    first.pc.borrow(first.link, KEY)
    second = Pair(tmp_path, "Laptop")  # same phone, a second paired PC
    with pytest.raises(ProtocolError) as busy:
        second.pc.fetch(second.link, KEY)
    assert busy.value.code == "ALREADY_LENT"
    first.home.take_back()
    assert first.home.model.state is HomeState.AT_HOME and first.bridge.mode == "home"
    first.pc_edit()
    with pytest.raises(ProtocolError) as fenced:
        first.pc.hand_back(first.link)
    assert fenced.value.code == "STALE_AUTHORITY" and first.pc.model.state is BorrowerState.NEEDS_REPAIR
    assert counterparties(first.live) == []


def test_crash_between_file_and_authority_finishes_at_next_unlock(pair, monkeypatch):
    pair.pc.fetch(pair.link, KEY)
    pair.pc.borrow(pair.link, KEY)
    pair.pc_edit()
    store = pair.home.store
    real = type(store).commit_authority

    def crash(self, expected):
        raise SystemExit("power cut after the file moved")
    monkeypatch.setattr(type(store), "commit_authority", crash)
    with pytest.raises(SystemExit):
        pair.pc.hand_back(pair.link)
    monkeypatch.setattr(type(store), "commit_authority", real)
    assert store.unresolved_promotion() is not None and not pair.home.writable()
    pair.home.recover()
    assert pair.home.writable() and pair.bridge.mode == "home"
    assert isinstance(pair.pc.check_return(pair.link), Accepted)
    assert counterparties(pair.live) == ["PC"]


def test_unpaired_or_revoked_pc_is_refused(pair):
    pair.home.revoke(pair.device)
    with pytest.raises(ProtocolError) as refused:
        pair.pc.fetch(pair.link, KEY)
    assert refused.value.code == "UNAUTHORIZED"
