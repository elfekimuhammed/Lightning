"""Profile screens and serialized access to the existing finance application."""
from __future__ import annotations

import asyncio
import re
import time
from contextlib import suppress
from contextlib import asynccontextmanager
from pathlib import Path

from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, RedirectResponse, Response

from lightning.database.backup import list_backups
from lightning.sync.state import ProtocolError
from lightning.security.keys import SUGGESTED_QUESTIONS, suggest_password
from lightning.ui.web import create_app, templates

from .http import (MARKET_IMPORT_PATH, MAX_IMPORT_CONFIRM_BODY, MAX_IMPORT_CONFIRM_FIELDS, MAX_MARKET_IMPORT_BODY,
                   MAX_IMPORT_MAP_BODY, Credentials, Guard,
                   body_receiver, configure_memory_only_import_uploads, equal)
from .devices import Devices, home_state_line, move_to_phone, open_move
from .paths import choose_data_root, discover_profiles, resolve_profile
from .roles import READ_ONLY_REFUSAL, SessionRole
from .session import AttemptGuard, ProfileError, ProfileSession

_DEFAULT_FORM_FIELDS = 2_000
_IMPORT_CONFIRM_FORM_FIELDS = MAX_IMPORT_CONFIRM_FIELDS


def _form_field_limit(path: str) -> int:
    if re.fullmatch(r"/accounts/\d+/import/\d+/confirm", path):
        return _IMPORT_CONFIRM_FORM_FIELDS
    return _DEFAULT_FORM_FIELDS


def _form_part_limit(path: str) -> int:
    # The mapping page carries the CSV as base64 in one multipart text field.
    if re.fullmatch(r"/accounts/\d+/import/map", path):
        return MAX_IMPORT_MAP_BODY
    # A large CSV can include a correspondingly long notes cell in one review row.
    if re.fullmatch(r"/accounts/\d+/import/\d+/confirm", path):
        return MAX_IMPORT_CONFIRM_BODY
    if path == MARKET_IMPORT_PATH:
        return MAX_MARKET_IMPORT_BODY
    return 512 * 1024


def _form_file_limit(path: str) -> int:
    # Only the initial CSV upload and the market price file accept a file part. Rejecting
    # files on every other form avoids creating spooled temporary files on those routes.
    return 1 if re.fullmatch(r"/accounts/\d+/import", path) or path == MARKET_IMPORT_PATH else 0


class SessionGate:
    """Serialize entire requests, including awaits, with lifecycle transitions.

    Every write also carries the token rendered with its profile. An old tab can
    never write into a new profile, even if it submits after that profile unlocks.
    """
    def __init__(self, app, session: ProfileSession):
        self.app, self.session = app, session
        self.mutex = asyncio.Lock()

    async def set_mode(self, mode: str) -> None:
        """Sync's mode change for the open profile (lightning.runtime.devices.AppBridge), between requests."""
        async with self.mutex:
            try:
                self.session.set_mode(mode)
            finally:
                self.app.state.container = self.session.container

    def device_line(self) -> tuple[str, str]:
        """The status line under the header while a ledger is borrowed or lent, and its action."""
        devices, session = getattr(self, "devices", None), self.session
        if devices is None or session.paths is None:
            return "", ""
        if session.borrowed is not None:
            if session.role.writable:
                return f"Borrowed from {session.borrowed_home or 'your phone'}", "hand-back"
            return "Read only on this PC: the ledger is going home or needs repair.", ""
        try:
            line = home_state_line(devices.home_node(session.paths))
        except Exception:  # noqa: BLE001 - an unreadable record shows as needing the Devices page
            line = "The ledger's lending record needs checking."
        return line, ("take-back" if line else "")

    async def change_role(self, role) -> None:
        """Change the open profile's role between requests, never during one (multi-device task 06)."""
        async with self.mutex:
            try:
                self.session.change_role(role)
            finally:
                self.app.state.container = self.session.container

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        generation = self.session.token
        async with self.mutex:
            request = Request(scope)
            profile_route = request.url.path == "/profiles" or request.url.path.startswith("/profiles/")
            public = profile_route or request.url.path.startswith("/static/")
            if not public and self.session.container is None:
                return await RedirectResponse("/profiles", 303)(scope, receive, send)
            if scope["method"] not in ("GET", "HEAD"):
                if not profile_route and not self.session.role.writable:
                    return await PlainTextResponse(READ_ONLY_REFUSAL, 403)(scope, receive, send)
                if generation != self.session.token:
                    return await PlainTextResponse("Profile changed. Reload before submitting.", 409)(scope, receive, send)
                body = scope["state"]["request_body"]
                parsed = Request(scope, body_receiver(body))
                try:
                    async with parsed.form(max_files=_form_file_limit(request.url.path),
                                           max_fields=_form_field_limit(request.url.path),
                                           max_part_size=_form_part_limit(request.url.path)) as form:
                        token = form.get("csrf" if profile_route else "__session", "")
                        expected = self.session.csrf if profile_route else self.session.token
                        valid = isinstance(token, str) and equal(token, expected)
                except Exception:
                    valid = False
                if not valid:
                    return await PlainTextResponse("This form expired. Reload the page and try again.", 403)(scope, receive, send)
            line, device_action = self.device_line()
            scope.setdefault("state", {}).update(secure_profiles=True, csrf=self.session.csrf,
                                                  phone=getattr(self, "phone", False),
                                                  session_token=self.session.token,
                                                  read_only=not self.session.role.writable,
                                                  device_line=line, device_action=device_action)
            self.app.state.container = self.session.container
            if self.session.container is not None and request.url.path != "/profiles/health" and not request.url.path.startswith("/static/"):
                self.session.last_activity = time.monotonic()
            await self.app(scope, receive, send)


def profile_app(credentials: Credentials, root: Path | str | None = None, devices: Devices | None = None,
                *, phone: bool = False):
    """`phone`: the Android app, whose pages use the phone frame and screens (guideline Part C)."""
    configure_memory_only_import_uploads()
    session = ProfileSession(root)
    session.borrowed_home = ""
    app = create_app(None)
    app.state.profile_session = session
    gate = SessionGate(app, session)
    devices = devices if devices is not None else Devices()
    gate.devices = devices
    gate.phone = phone

    async def expire_sessions():
        while True:
            await asyncio.sleep(1)
            async with gate.mutex:
                if session.pending and time.monotonic() >= session.pending.expires:
                    session.pending = None
                if session.container and time.monotonic() - session.last_activity >= session.idle_seconds:
                    borrowed = session.borrowed
                    session.close()
                    app.state.container = None
                    if borrowed is not None:
                        borrowed.seal()  # idle lock away from the phone: keep the lend; hand back next time

    @asynccontextmanager
    async def lifespan(_app):
        devices.start(asyncio.get_running_loop(), session, gate)
        expiry = asyncio.create_task(expire_sessions())
        try:
            yield
        finally:
            expiry.cancel()
            with suppress(asyncio.CancelledError):
                await expiry
            borrowed = session.borrowed
            session.close()
            app.state.container = None
            if borrowed is not None:
                # Closing Lightning on the PC: hand back if the phone answers, else keep the lend sealed here.
                with suppress(Exception):
                    await asyncio.to_thread(devices.hand_back_or_seal, borrowed)
            devices.stop()

    app.router.lifespan_context = lifespan

    @app.get("/profiles/health")
    async def health():
        return JSONResponse({"ok": True, "locked": session.container is None, "session": session.token})

    @app.post("/__activity")
    async def activity():
        # Admitted under the current profile token; JS sends only in response to
        # trusted keyboard/pointer input, never from the background health poll.
        return Response(status_code=204)

    def page(request: Request, mode: str, *, error="", status=200, **context):
        values = dict(mode=mode, csrf=session.csrf, error=error, root=str(session.root), borrowed=[],
                      is_borrowed=session.borrowed is not None,
                      profiles=[], backups=[], selected="", backup="", name="", recovery="",
                      active_name=session.name, notice="", suggestion="", chosen_password="",
                      questions=SUGGESTED_QUESTIONS, question="", new_recovery="")
        if mode == "setup" and not context.get("suggestion"):
            values["suggestion"] = suggest_password()
        if mode == "manage":
            values["question"] = session.current_question()
        values.update(context)
        return templates.TemplateResponse(request, "profiles.html", values, status_code=status)

    async def action(request, mode, operation, **context):
        try:
            result = operation()
            app.state.container = session.container
            return result or RedirectResponse("/" if session.container else "/profiles", 303)
        except ProfileError as exc:
            return page(request, mode, error=str(exc), status=400, **context)
        except Exception as exc:
            # Never render native exception strings (paths, SQL, secrets); the error's kind alone helps a report.
            return page(request, mode, error="The operation could not finish. Your existing database was not "
                        f"replaced. Check the folder permissions, available space and app version ({type(exc).__name__}).",
                        status=400, **context)

    @app.get("/profiles")
    async def profiles(request: Request):
        if session.container:
            return page(request, "manage")
        try:
            root_value = request.query_params.get("root")
            if root_value:
                session.root = choose_data_root(root_value)
            found = discover_profiles(session.root)
            backups = []
            for info in found:
                paths = resolve_profile(info.path)
                backups.extend({"path": str(item.path), "label": item.path.name,
                                "db": str(paths.db_path)}
                               for item in list_backups(paths.backups_dir, paths.db_path))
            return page(request, "choose", profiles=found, backups=backups, borrowed=devices.borrowed())
        except (OSError, ValueError):
            return page(request, "choose", error="That folder could not be read. Choose another location.", status=400)

    @app.get("/profiles/new")
    async def new(request: Request):
        if session.container:
            return RedirectResponse("/profiles", 303)
        return page(request, "setup")

    @app.post("/profiles/new")
    async def prepare(request: Request):
        form = await request.form()
        suggestion = str(form.get("suggestion", ""))
        # "Use this password" takes the suggested words as the password, typed by nobody.
        chosen = suggestion if form.get("use_suggestion") == "yes" else ""
        password = chosen or str(form.get("password", ""))
        confirm = chosen or str(form.get("confirm", ""))
        def operation():
            pending = session.prepare(str(form.get("name", "")), password, confirm,
                                      str(form.get("question", "")), str(form.get("answer", "")))
            return page(request, "recovery-key", recovery=pending.recovery, name=pending.paths.profile.name,
                        chosen_password=chosen, notice="Will create: " + str(pending.paths.db_path))
        return await action(request, "setup", operation, name=str(form.get("name", "")), suggestion=suggestion,
                            question=str(form.get("question", "")))

    @app.post("/profiles/confirm")
    async def confirm(request: Request):
        form = await request.form()
        if session.pending is None:
            return page(request, "setup", error="Setup expired. Create the profile again.", status=400)
        pending = session.pending
        # Owner, 2026-10-06: the key is shown once and confirmed with a press, not typed back.
        return await action(request, "recovery-key", lambda: session.confirm(pending.recovery),
                            recovery=pending.recovery, name=pending.paths.profile.name if pending.paths.profile else "")

    @app.post("/profiles/cancel")
    async def cancel(request: Request):
        session.pending = None
        return RedirectResponse("/profiles", 303)

    @app.get("/profiles/unlock")
    async def unlock_page(request: Request):
        if session.container:
            return RedirectResponse("/profiles", 303)
        return page(request, "unlock", selected=request.query_params.get("db", ""))

    @app.post("/profiles/unlock")
    async def unlock(request: Request):
        form = await request.form()
        selected = str(form.get("db", ""))
        role = SessionRole.READER if devices.role_for(selected) == "reader" else SessionRole.HOME

        def operation():
            session.unlock(selected, str(form.get("password", "")), role=role)
            devices.after_unlock(session.paths)
        return await action(request, "unlock", operation, selected=selected)

    def known_question(selected: str) -> str:
        try:
            return session.question(selected)
        except (ProfileError, OSError, ValueError):
            return ""

    @app.get("/profiles/recover")
    async def recover_page(request: Request):
        if session.container:
            return RedirectResponse("/profiles", 303)
        selected = request.query_params.get("db", "")
        question = known_question(selected)
        return page(request, "recover", selected=selected, question=question,
                    error="" if question else "This profile's key file is missing or damaged, so it cannot be recovered here.")

    @app.post("/profiles/recover")
    async def recover(request: Request):
        form = await request.form()
        selected = str(form.get("db", ""))
        def operation():
            session.recover(selected, str(form.get("recovery", "")), str(form.get("answer", "")),
                            str(form.get("password", "")), str(form.get("confirm", "")))
            return page(request, "unlock", selected=selected, notice="Password reset. Unlock with your new password.")
        return await action(request, "recover", operation, selected=selected, question=known_question(selected))

    @app.get("/profiles/restore")
    async def restore_page(request: Request):
        if session.container:
            return RedirectResponse("/profiles", 303)
        return page(request, "restore", selected=request.query_params.get("db", ""),
                    backup=request.query_params.get("backup", ""))

    @app.post("/profiles/restore")
    async def restore(request: Request):
        form = await request.form()
        selected = str(form.get("db", ""))
        backup_path = str(form.get("backup", ""))
        if form.get("confirm") != "yes":
            return page(request, "restore", status=400, selected=selected, backup=backup_path,
                        error="Confirm that this backup will replace the current profile.")
        try:
            session.restore_backup(selected, backup_path, str(form.get("password", "")))
        except ProfileError as exc:
            return page(request, "restore", status=400, selected=selected,
                        backup=backup_path, error=str(exc))
        except Exception:
            # Replacement may already have happened before a disk or process
            # error. Never promise the old live path is still unchanged.
            return page(request, "restore", status=400, selected=selected,
                        backup=backup_path, error="Restore needs checking. Keep this profile locked and inspect the selected backup and retained copies before trying again.")
        return page(request, "unlock", selected=selected,
                    notice="Backup restored. The previous database was kept for recovery. Unlock this profile to review it.")

    @app.get("/profiles/restore/resume")
    async def resume_restore_page(request: Request):
        if session.container:
            return RedirectResponse("/profiles", 303)
        return page(request, "resume-restore", selected=request.query_params.get("db", ""))

    @app.post("/profiles/restore/resume")
    async def resume_restore(request: Request):
        form = await request.form()
        selected = str(form.get("db", ""))
        if form.get("confirm") != "yes":
            return page(request, "resume-restore", status=400, selected=selected,
                        error="Confirm that Lightning should check and resume this restore.")
        try:
            session.resume_interrupted_restore(selected, str(form.get("password", "")))
        except ProfileError as exc:
            return page(request, "resume-restore", status=400, selected=selected, error=str(exc))
        except Exception:
            return page(request, "resume-restore", status=400, selected=selected,
                        error="Restore recovery needs inspection. The profile remains locked and its copies were kept.")
        return page(request, "unlock", selected=selected,
                    notice="Restore checks finished. Unlock this profile to review the recovered database.")

    @app.post("/profiles/password")
    async def password(request: Request):
        form = await request.form()
        def operation():
            session.change_password(str(form.get("proof", "")), str(form.get("password", "")), str(form.get("confirm", "")))
            return page(request, "manage", notice="Password changed. Your recovery key and security question are unchanged.")
        return await action(request, "manage", operation)

    @app.post("/profiles/question")
    async def question(request: Request):
        form = await request.form()
        def operation():
            session.change_question(str(form.get("recovery", "")), str(form.get("question", "")), str(form.get("answer", "")))
            return page(request, "manage", notice="Security question changed. Your password and recovery key are unchanged.")
        return await action(request, "manage", operation)

    @app.post("/profiles/recovery-key")
    async def recovery_key(request: Request):
        form = await request.form()
        def operation():
            pending = session.prepare_recovery_key(str(form.get("answer", "")))
            return page(request, "manage", new_recovery=pending.recovery)
        return await action(request, "manage", operation)

    @app.post("/profiles/recovery-key/confirm")
    async def confirm_recovery_key(request: Request):
        form = await request.form()
        pending = session.pending_recovery
        def operation():
            session.confirm_recovery_key(pending.recovery if pending else "")
            return page(request, "manage", notice="New recovery key saved. The old one no longer works.")
        return await action(request, "manage", operation, new_recovery=pending.recovery if pending else "")

    @app.post("/profiles/lock")
    async def lock(request: Request):
        if session.borrowed is not None:
            return await hand_back(request)
        return await action(request, "manage", session.close)

    # ------------------------------------------------------------ multiple devices: the phone's side
    def device_page(request, **context):
        node = devices.home_node(session.paths) if session.paths is not None else None
        pending = devices.desk.pending if devices.desk is not None else None
        if pending is not None and (node is None or pending.node is not node):
            pending = None
        peers = node.store.peers() if node is not None else []
        home = node.model if node is not None else None
        lent_to = home.active.grant.borrower_id if home is not None and home.active is not None else ""
        return page(request, "devices", node=node, peers=peers, lent_to=lent_to, pending=pending,
                    address=devices.address() if devices.server is not None else "",
                    state_line=home_state_line(node), phone_name=devices.identity().name
                    if devices.has_identity() else "", **context)

    def home_only():
        if session.container is None:
            return RedirectResponse("/profiles", 303)
        if session.borrowed is not None:
            return RedirectResponse("/profiles", 303)
        return None

    @app.get("/profiles/devices")
    async def devices_page(request: Request):
        return home_only() or device_page(request)

    @app.post("/profiles/devices/pair")
    async def open_pairing(request: Request):
        if (refused := home_only()) is not None:
            return refused
        form = await request.form()
        name = " ".join(str(form.get("phone_name", "")).split())[:60]
        if not name:
            return device_page(request, error="Name this phone, so the PC can show it.", status=400)
        try:
            node = devices.home_node(session.paths) or devices.enable_home(session, name)
            devices.identity(name)
            devices.ensure_listener()
        except OSError:
            return device_page(request, error="Another app is using the port Lightning listens on. Close it and "
                                              "try again.", status=400)
        except (ProtocolError, ValueError) as exc:
            return device_page(request, error=str(exc), status=400)
        devices.desk.open(node, home_name=name, profile_name=session.name)
        return RedirectResponse("/profiles/devices", 303)

    @app.post("/profiles/devices/stop-pairing")
    async def stop_pairing(request: Request):
        if devices.desk is not None:
            devices.desk.close()
        return RedirectResponse("/profiles/devices", 303)

    @app.post("/profiles/devices/revoke")
    async def revoke(request: Request):
        if (refused := home_only()) is not None:
            return refused
        form = await request.form()
        node = devices.home_node(session.paths)
        if node is not None:
            node.revoke(str(form.get("device", "")))
        return RedirectResponse("/profiles/devices", 303)

    @app.post("/profiles/devices/take-back")
    async def take_back(request: Request):
        if (refused := home_only()) is not None:
            return refused
        form = await request.form()
        node = devices.home_node(session.paths)
        if node is None:
            return RedirectResponse("/profiles/devices", 303)
        if form.get("confirm") != "yes":
            return device_page(request, error="Tick the box to confirm that the PC's edits since it borrowed "
                                              "the ledger will not come back.", status=400)
        try:
            node.take_back(reopen=False)  # this request holds the gate: reopen here, not through it
            session.set_mode("home")
            app.state.container = session.container
        except ProtocolError as exc:
            return device_page(request, error=str(exc), status=400)
        return device_page(request, notice="The ledger is back on this phone. That PC's copy can no longer be "
                                           "handed back; it stays on the PC, read only.")

    # ------------------------------------------------------------ multiple devices: the PC's side
    @app.get("/profiles/connect")
    async def connect_page(request: Request):
        if session.container:
            return RedirectResponse("/profiles", 303)
        import socket as _socket
        return page(request, "connect", pc_name=_socket.gethostname()[:60] or "This PC")

    @app.post("/profiles/connect")
    async def connect(request: Request):
        from lightning.sync.identity import normalize_code
        from lightning.sync.service import LinkDown
        from lightning.sync.transport import join_home, pair
        if session.container:
            return RedirectResponse("/profiles", 303)
        form = await request.form()
        address, code = str(form.get("address", "")).strip(), str(form.get("code", ""))
        pc_name = " ".join(str(form.get("pc_name", "")).split())[:60]
        values = dict(address=address, pc_name=pc_name)
        try:
            normalize_code(code)
            if not pc_name:
                raise ValueError("Name this PC, so the phone can show it.")
            identity = devices.identity(pc_name)
            paired = await asyncio.to_thread(pair, address, code, identity)
            node = await asyncio.to_thread(join_home, paired, endpoint=address, identity=identity, root=devices.root)
        except (ProfileError, ValueError) as exc:
            return page(request, "connect", error=str(exc), status=400, **values)
        except (LinkDown, ProtocolError) as exc:
            return page(request, "connect", error=str(exc), status=400, **values)
        return page(request, "connected", digits=paired.digits, profile_name=paired.reply.profile_name,
                    home_name=paired.reply.home_name, profile_id=node.model.profile_id)

    @app.get("/profiles/borrowed")
    async def borrowed_page(request: Request):
        if session.container:
            return RedirectResponse("/profiles", 303)
        found = devices.find_borrowed(request.query_params.get("id", ""))
        if found is None:
            return RedirectResponse("/profiles", 303)
        return page(request, "borrowed", item=found)

    @app.post("/profiles/borrowed")
    async def open_borrowed(request: Request):
        import json as _json
        from lightning.security.keys import unwrap_key
        from lightning.sync.copies import CopyRejected
        from lightning.sync.service import LinkDown
        from lightning.sync.state import BorrowerState
        if session.container:
            return RedirectResponse("/profiles", 303)
        form = await request.form()
        found = devices.find_borrowed(str(form.get("id", "")))
        if found is None:
            return RedirectResponse("/profiles", 303)
        node = found.node
        attempts = AttemptGuard(node.paths.keys_path.with_name("attempts.json"))
        try:
            attempts.check()
            try:
                key = unwrap_key(_json.loads(node.paths.keys_path.read_text(encoding="utf-8")),
                                 str(form.get("password", "")))
            except ValueError as exc:
                attempts.failed()
                raise ProfileError("The password is incorrect. It is the profile's password, the same as on "
                                   "the phone.") from exc
            attempts.succeeded()
            state = node.model.state
            notice = ""
            if state is BorrowerState.SEALED:
                node.reopen()
            elif state is BorrowerState.RETURNING:
                result = await asyncio.to_thread(devices.hand_back_or_seal, node)
                if result in ("accepted", "handed_back"):
                    return page(request, "choose", notice=f"{found.name} is home on {found.home_name}. Open it "
                                                          "again to borrow it.", profiles=discover_profiles(session.root),
                                borrowed=devices.borrowed())
                notice = "The phone has not taken the ledger back yet. This copy is read only until it does."
            elif state is BorrowerState.NEEDS_REPAIR:
                notice = "The phone took the ledger back. This copy is kept here, read only."
            elif state is not BorrowerState.BORROWING:
                link = devices.link(node)
                if state is not BorrowerState.BORROW_PREPARED:
                    await asyncio.to_thread(node.fetch, link, key)
                await asyncio.to_thread(node.borrow, link, key)
            session.open_borrowed(node, key, name=found.name, writable=node.writable)
            session.borrowed_home = found.home_name
            app.state.container = session.container
            if notice:
                return page(request, "manage", notice=notice)
            return RedirectResponse("/", 303)
        except ProfileError as exc:
            return page(request, "borrowed", item=found, error=str(exc), status=400)
        except LinkDown:
            return page(request, "borrowed", item=found, status=400,
                        error=f"{found.home_name} did not answer. Open Lightning on it, on the same Wi-Fi, and try "
                              "again.")
        except ProtocolError as exc:
            return page(request, "borrowed", item=found, error=str(exc), status=400)
        except CopyRejected as exc:
            return page(request, "borrowed", item=found, error=str(exc), status=400)

    # ------------------------------------------------------------ moving a profile's home to the phone
    @app.get("/profiles/receive")
    async def receive_page(request: Request):
        pending = devices.desk.pending if devices.desk is not None else None
        if pending is not None and pending.receive is None:
            pending = None
        return page(request, "receive", pending=pending,
                    address=devices.address() if devices.server is not None else "",
                    phone_name=devices.identity().name if devices.has_identity() else "My phone")

    @app.post("/profiles/receive")
    async def open_receive(request: Request):
        if session.container:
            return RedirectResponse("/profiles", 303)
        form = await request.form()
        name = " ".join(str(form.get("phone_name", "")).split())[:60]
        if not name:
            return page(request, "receive", error="Name this phone, so the PC can show it.", status=400,
                        phone_name="", pending=None, address="")
        try:
            open_move(devices, session.root, name)
        except OSError:
            return page(request, "receive", error="Another app is using the port Lightning listens on. Close it "
                                                  "and try again.", status=400, phone_name=name, pending=None,
                        address="")
        return RedirectResponse("/profiles/receive", 303)

    @app.post("/profiles/move")
    async def move(request: Request):
        from lightning.security.keys import key_id
        from lightning.sync.copies import ensure_profile_id, schema_version
        from lightning.sync.identity import normalize_code
        from lightning.sync.service import LinkDown
        if session.container is None or session.borrowed is not None or not session.role.writable:
            return RedirectResponse("/profiles", 303)
        form = await request.form()
        address, code = str(form.get("address", "")).strip(), str(form.get("code", ""))
        pc_name = " ".join(str(form.get("pc_name", "")).split())[:60] or "This PC"
        try:
            normalize_code(code)
        except ValueError as exc:
            return page(request, "manage", error=str(exc), status=400)
        db = session.container.db
        profile_id = ensure_profile_id(db)
        schema, kid, name, paths = schema_version(db), key_id(session.sync_key), session.name, session.paths
        session.close()  # the file is closed before it moves; this request holds the gate, so nothing reopens it
        app.state.container = None
        try:
            moved = await asyncio.to_thread(move_to_phone, devices, paths=paths, profile_id=profile_id, name=name,
                                            key_id=kid, schema=schema, address=address, code=code, pc_name=pc_name)
        except (LinkDown, ProtocolError, ValueError) as exc:
            return page(request, "unlock", selected=str(paths.db_path), status=400,
                        error=f"{exc} {name} stays on this PC; unlock it to try again.")
        return page(request, "choose", profiles=discover_profiles(session.root), borrowed=devices.borrowed(),
                    notice=f"{name} now lives on {moved.done.home_name}. Check that it shows {moved.digits[:3]} "
                           f"{moved.digits[3:]}. Borrow it here under From your phone; the PC's old copy is kept "
                           "as a backup.")

    @app.post("/profiles/hand-back")
    @app.post("/sync/hand-back")  # the finance pages' banner, which carries the session token
    async def hand_back(request: Request):
        node = session.borrowed
        if node is None:
            return RedirectResponse("/profiles", 303)
        name, home_name = session.name, session.borrowed_home or "your phone"
        session.close()  # the working copy closes before it is frozen and sent
        session.borrowed_home = ""
        app.state.container = None
        result = await asyncio.to_thread(devices.hand_back_or_seal, node)
        notices = {
            "accepted": f"{name} is back on {home_name}, with your changes.",
            "received": f"{home_name} has your changes and takes them in when it is unlocked. Until then this PC "
                        "keeps a read-only copy.",
            "sealed": f"{home_name} did not answer. Your changes are saved on this PC; open {name} here to keep "
                      "working, or hand it back when the phone is near.",
            "returning": f"Sending to {home_name} stopped halfway. Open {name} here near the phone to finish.",
        }
        return page(request, "choose", notice=notices.get(result, ""), profiles=discover_profiles(session.root),
                    borrowed=devices.borrowed())

    secured = Guard(gate, credentials)
    secured.session = session  # Lifecycle tests inspect synthetic state only.
    secured.gate = gate  # The sync service (task 07) changes roles through gate.change_role.
    return secured
