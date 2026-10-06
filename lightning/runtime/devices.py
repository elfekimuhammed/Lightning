"""Multiple devices inside the running app: the phone that holds a ledger and the PC that borrows it.

Everything here lives in this device's own app data (`root`), never in a profile folder:

    <root>/device/                 this device's identity (lightning.sync.identity)
    <root>/home/<profile folder>/  a ledger this device holds and lends: control store, checkpoints, home.json
    <root>/borrowed/<profile id>/  a ledger this PC borrows: control store, working copy, its own key slot

The sync link runs on its own threads. Whatever it needs from the open profile goes through `AppBridge`, which
asks the request gate on the app's event loop, so a lend never starts in the middle of a request.
"""
from __future__ import annotations

import asyncio
import json
import threading
from dataclasses import dataclass
from pathlib import Path

from lightning.sync.control import ControlStore
from lightning.sync.identity import DEFAULT_PORT, DeviceIdentity, load_or_create, local_address
from lightning.sync.service import BorrowerNode, HomeNode, LinkDown
from lightning.sync.state import BorrowerState, HomeState, ProtocolError

from .paths import ProfilePaths, app_data_root, resolve_profile

HOME_META = "home.json"
STATUS_TIMEOUT = 5


class AppBridge:
    """The home node's view of the app's open profile (lightning.sync.service.HomeBridge)."""

    def __init__(self, devices: "Devices", live: Path):
        self.devices, self.live = devices, Path(live)

    def _open_here(self) -> bool:
        session = self.devices.session
        return (session is not None and session.paths is not None and session.borrowed is None
                and Path(session.paths.db_path) == self.live)

    def key(self) -> bytes | None:
        return self.devices.session.sync_key if self._open_here() else None

    def set_mode(self, mode: str) -> None:
        if not self._open_here():
            return
        loop, gate = self.devices.loop, self.devices.gate
        if loop is None or gate is None:
            raise RuntimeError("The app is not running")
        asyncio.run_coroutine_threadsafe(gate.set_mode(mode), loop).result(120)


@dataclass(frozen=True)
class Borrowed:
    node: BorrowerNode
    profile_id: str
    name: str
    home_name: str

    @property
    def state(self) -> BorrowerState:
        return self.node.model.state


class Devices:
    def __init__(self, root: str | Path | None = None, *, port: int = DEFAULT_PORT, host: str = "0.0.0.0"):
        self.root = Path(root) if root is not None else app_data_root()
        self.port, self.host = port, host
        self.session = None      # the app's ProfileSession
        self.gate = None         # its SessionGate
        self.loop = None         # the app's event loop, set at startup
        self.server = None
        self.desk = None
        self._lock = threading.RLock()
        self._nodes: dict[Path, HomeNode] = {}

    # ------------------------------------------------------------ identity
    def identity(self, name: str | None = None) -> DeviceIdentity:
        folder = self.root / "device"
        if name is None:
            meta = folder / "device.json"
            name = json.loads(meta.read_text(encoding="utf-8"))["name"] if meta.exists() else "This device"
        return load_or_create(folder, name)

    def has_identity(self) -> bool:
        return (self.root / "device" / "device.json").exists()

    # ------------------------------------------------------------ the ledgers this device holds
    def home_folder(self, paths: ProfilePaths) -> Path | None:
        if paths.profile is None:
            return None  # only named profiles can be lent
        return self.root / "home" / paths.profile.profile_id

    def home_node(self, paths: ProfilePaths) -> HomeNode | None:
        folder = self.home_folder(paths)
        if folder is None or not (folder / "control.db").exists():
            return None
        return self._node(folder, Path(paths.db_path))

    def _node(self, folder: Path, live: Path) -> HomeNode:
        with self._lock:
            node = self._nodes.get(folder)
            if node is None:
                node = HomeNode(live_path=live, control_folder=folder, bridge=AppBridge(self, live))
                self._nodes[folder] = node
            return node

    def home_nodes(self) -> list[HomeNode]:
        nodes = []
        for meta in sorted((self.root / "home").glob(f"*/{HOME_META}")):
            try:
                live = Path(json.loads(meta.read_text(encoding="utf-8"))["live_path"])
                if live.exists() and (meta.parent / "control.db").exists():
                    nodes.append(self._node(meta.parent, live))
            except (OSError, ValueError, KeyError):
                continue
        return nodes

    def enable_home(self, session, phone_name: str) -> HomeNode:
        """On the owning thread, profile unlocked and writable: make this device the ledger's home."""
        paths = session.paths
        folder = self.home_folder(paths)
        if folder is None or session.borrowed is not None:
            raise ProtocolError("BAD_REQUEST", "Only a profile kept on this device can be lent.")
        identity = self.identity(phone_name)
        folder.mkdir(mode=0o700, parents=True, exist_ok=True)
        HomeNode.enable(session.container.db, live_path=paths.db_path, control_folder=folder,
                        home_id=identity.device_id, bridge=AppBridge(self, paths.db_path))
        (folder / HOME_META).write_text(json.dumps({"live_path": str(paths.db_path)}), encoding="utf-8")
        return self._node(folder, Path(paths.db_path))

    def role_for(self, selected: str) -> str:
        """How a profile kept here may open: "home" (writable) or "reader" (lent away, or a hand-back to
        finish first). Decided before any connection opens."""
        try:
            paths = resolve_profile(db_path=selected)
        except (OSError, ValueError):
            return "home"
        node = self.home_node(paths)
        if node is None:
            return "home"
        return "home" if node.writable() else "reader"

    def after_unlock(self, paths: ProfilePaths) -> None:
        """Finish an interrupted hand-back and accept a copy that arrived while locked: on a worker thread,
        because it changes the session's mode through the gate."""
        node = self.home_node(paths)
        if node is None:
            return

        def work():
            try:
                node.recover()
            except Exception:  # noqa: BLE001 - the state stays as recorded; the Devices page shows it
                pass
        threading.Thread(target=work, name="lightning-sync-recover", daemon=True).start()

    # ------------------------------------------------------------ listening for PCs (on the phone)
    def ensure_listener(self) -> None:
        from lightning.sync.transport import HomeServer, PairingDesk
        with self._lock:
            if self.server is not None:
                return
            self.desk = self.desk or PairingDesk()
            self.server = HomeServer(self.identity(), self.home_nodes, self.desk, host=self.host,
                                     port=self.port).start()

    def start(self, loop, session, gate) -> None:
        self.loop, self.session, self.gate = loop, session, gate
        if self.home_nodes():
            try:
                self.ensure_listener()
            except OSError:
                pass  # the port is busy: the Devices page says so when asked to pair

    def stop(self) -> None:
        with self._lock:
            if self.server is not None:
                self.server.stop()
                self.server = None

    def address(self) -> str:
        port = self.server.port if self.server is not None else self.port
        return f"{local_address()}:{port}"

    # ------------------------------------------------------------ the ledgers this PC borrows
    def borrowed(self) -> list[Borrowed]:
        found = []
        for meta in sorted((self.root / "borrowed").glob("*/profile.json")):
            try:
                from .paths import borrowed_profile
                paths = borrowed_profile(meta.parent.name, root=self.root)
                node = BorrowerNode(paths)
                model = node.model
                home = node.store.peer(model.home_id)
                found.append(Borrowed(node, model.profile_id, json.loads(meta.read_text(encoding="utf-8"))["name"],
                                      home.name if home else "your phone"))
            except (OSError, ValueError, KeyError, RuntimeError):
                continue
        return found

    def find_borrowed(self, profile_id: str) -> Borrowed | None:
        return next((b for b in self.borrowed() if b.profile_id == profile_id), None)

    def link(self, node: BorrowerNode, *, timeout: float | None = None):
        from lightning.sync.transport import link_to_home
        link = link_to_home(node, self.identity())
        if timeout is not None:
            link.timeout = timeout
        return link

    def hand_back_or_seal(self, node: BorrowerNode) -> str:
        """At close (Lock, Hand back, app exit): hand back when the phone answers, else keep the lend sealed
        here. Returns "accepted", "received" (the phone checks it at its next unlock), "sealed" or "returning"
        (sending started and will be retried)."""
        from lightning.sync.domain import Accepted, Status
        state = node.model.state
        if state not in (BorrowerState.BORROWING, BorrowerState.SEALED, BorrowerState.RETURNING):
            return state.value.lower()
        try:
            if state is not BorrowerState.RETURNING:
                self.link(node, timeout=STATUS_TIMEOUT).status(Status(node.model.device_id))
        except (LinkDown, ProtocolError):
            node.seal()
            return "sealed"
        try:
            receipt = node.hand_back(self.link(node)) if state is not BorrowerState.RETURNING \
                else node.check_return(self.link(node))
        except LinkDown:
            return "returning"
        return "accepted" if isinstance(receipt, Accepted) else "received"


def home_state_line(node: HomeNode | None) -> str:
    """What the phone's banner says while its ledger is away, or "" at home."""
    if node is None:
        return ""
    home = node.model
    if home.state is HomeState.AT_HOME:
        return ""
    if home.state is HomeState.NEEDS_REPAIR:
        return "The copy the PC handed back needs repair. Nothing was changed; it is read-only here."
    borrower = node.store.peer(home.active.grant.borrower_id) if home.active is not None else None
    name = borrower.name if borrower else "a PC"
    if home.state is HomeState.RETURN_RECEIVED:
        return f"{name} handed the ledger back. Checking it…"
    return f"Lent to {name} · read only"
