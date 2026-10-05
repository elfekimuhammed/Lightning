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
from lightning.ui.web import create_app, templates

from .http import (MAX_IMPORT_CONFIRM_BODY, MAX_IMPORT_CONFIRM_FIELDS,
                   MAX_IMPORT_MAP_BODY, Credentials, Guard,
                   body_receiver, configure_memory_only_import_uploads, equal)
from .paths import choose_data_root, discover_profiles, resolve_profile
from .roles import READ_ONLY_REFUSAL
from .session import ProfileError, ProfileSession

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
    return 512 * 1024


def _form_file_limit(path: str) -> int:
    # Only the initial CSV upload route accepts a file part. Rejecting files on
    # every other form avoids creating spooled temporary files on those routes.
    return 1 if re.fullmatch(r"/accounts/\d+/import", path) else 0


class SessionGate:
    """Serialize entire requests, including awaits, with lifecycle transitions.

    Every write also carries the token rendered with its profile. An old tab can
    never write into a new profile, even if it submits after that profile unlocks.
    """
    def __init__(self, app, session: ProfileSession):
        self.app, self.session = app, session
        self.mutex = asyncio.Lock()

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
            scope.setdefault("state", {}).update(secure_profiles=True, csrf=self.session.csrf,
                                                  session_token=self.session.token,
                                                  read_only=not self.session.role.writable)
            self.app.state.container = self.session.container
            if self.session.container is not None and request.url.path != "/profiles/health" and not request.url.path.startswith("/static/"):
                self.session.last_activity = time.monotonic()
            await self.app(scope, receive, send)


def profile_app(credentials: Credentials, root: Path | str | None = None):
    configure_memory_only_import_uploads()
    session = ProfileSession(root)
    app = create_app(None)
    app.state.profile_session = session
    gate = SessionGate(app, session)

    async def expire_sessions():
        while True:
            await asyncio.sleep(1)
            async with gate.mutex:
                if session.pending and time.monotonic() >= session.pending.expires:
                    session.pending = None
                if session.container and time.monotonic() - session.last_activity >= session.idle_seconds:
                    session.close()
                    app.state.container = None

    @asynccontextmanager
    async def lifespan(_app):
        expiry = asyncio.create_task(expire_sessions())
        try:
            yield
        finally:
            expiry.cancel()
            with suppress(asyncio.CancelledError):
                await expiry
            session.close()
            app.state.container = None

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
        values = dict(mode=mode, csrf=session.csrf, error=error, root=str(session.root),
                      profiles=[], backups=[], selected="", backup="", name="", recovery="",
                      active_name=session.name, notice="")
        values.update(context)
        return templates.TemplateResponse(request, "profiles.html", values, status_code=status)

    async def action(request, mode, operation, **context):
        try:
            result = operation()
            app.state.container = session.container
            return result or RedirectResponse("/" if session.container else "/profiles", 303)
        except ProfileError as exc:
            return page(request, mode, error=str(exc), status=400, **context)
        except Exception:
            # Never render native exception strings (paths, SQL, secrets).
            return page(request, mode, error="The operation could not finish. Your existing database was not replaced. Check the folder permissions, available space and app version.", status=400, **context)

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
            return page(request, "choose", profiles=found, backups=backups)
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
        def operation():
            pending = session.prepare(str(form.get("name", "")), str(form.get("password", "")), str(form.get("confirm", "")))
            return page(request, "recovery-key", recovery=pending.recovery, name=pending.paths.profile.name,
                        notice="Will create: " + str(pending.paths.db_path))
        return await action(request, "setup", operation)

    @app.post("/profiles/confirm")
    async def confirm(request: Request):
        form = await request.form()
        return await action(request, "setup", lambda: session.confirm(form.get("saved") == "yes"))

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
        return await action(request, "unlock", lambda: session.unlock(selected, str(form.get("password", ""))), selected=selected)

    @app.get("/profiles/recover")
    async def recover_page(request: Request):
        if session.container:
            return RedirectResponse("/profiles", 303)
        return page(request, "recover", selected=request.query_params.get("db", ""))

    @app.post("/profiles/recover")
    async def recover(request: Request):
        form = await request.form()
        selected = str(form.get("db", ""))
        def operation():
            session.recover(selected, str(form.get("recovery", "")), str(form.get("password", "")), str(form.get("confirm", "")))
            return page(request, "unlock", selected=selected, notice="Password reset. Unlock with your new password.")
        return await action(request, "recover", operation, selected=selected)

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
            session.change_password(str(form.get("current_password", "")), str(form.get("password", "")), str(form.get("confirm", "")))
            return page(request, "manage", notice="Password changed. Your recovery key is unchanged.")
        return await action(request, "manage", operation)

    @app.post("/profiles/lock")
    async def lock(request: Request):
        return await action(request, "manage", session.close)

    secured = Guard(gate, credentials)
    secured.session = session  # Lifecycle tests inspect synthetic state only.
    secured.gate = gate  # The sync service (task 07) changes roles through gate.change_role.
    return secured
