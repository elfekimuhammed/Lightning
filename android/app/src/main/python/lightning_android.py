"""The phone app's Python side: the shared profile app on 127.0.0.1 for the WebView, and the PC listener.

Profiles live in app-private storage (`files/Lightning`), sync records beside them (`files/appdata`); both are
excluded from Google backup and device transfer (res/xml/data_extraction_rules.xml). The server keeps running
while the process lives, so reopening the app does not ask for a new launch link."""
from pathlib import Path

_host = None
_devices = None
_launched = False


def start(files_dir):
    """The URL the WebView opens: the single-use launch link the first time, the app itself afterwards."""
    global _host, _devices, _launched
    if _host is None:
        from lightning.runtime.app import profile_app
        from lightning.runtime.devices import Devices
        from lightning.runtime.http import Host

        files = Path(files_dir)
        _devices = Devices(files / "appdata")
        _host = Host(lambda credentials: profile_app(credentials, files / "Lightning", devices=_devices, phone=True)).start()
    if not _launched:
        _launched = True
        return _host.launch_url
    return _host.origin + "/"


def background_note():
    """What the notification says while the phone must keep listening (pairing, or the ledger is away), or ""
    when it may sleep."""
    from lightning.runtime.devices import home_state_line

    if _devices is None or _devices.server is None:
        return ""
    desk = _devices.desk
    if desk is not None and desk.pending is not None and not desk.pending.paired_name:
        return "Waiting for your PC to pair"
    for node in _devices.home_nodes():
        try:
            line = home_state_line(node)
        except Exception:  # noqa: BLE001 - an unreadable record still needs the listener
            line = "Checking where your ledger is"
        if line:
            return line
    return ""
