"""Frozen-app acceptance using a disposable household, never user data."""
from pathlib import Path
from tempfile import TemporaryDirectory

from lightning.ui.web import UI_DIR, create_app

from .session import ProfileSession


def run_profile_checks() -> dict[str, bool]:
    checks = {"profile_resources": all((UI_DIR / item).is_file() for item in (
        "templates/profiles.html", "static/profiles.css", "static/session.js",
        "static/app.js", "static/fonts/fonts.css",
    )), "profile_setup": False, "profile_reopen": False, "profile_recovery": False,
              "finance_routes": False, "profile_backup": False}
    with TemporaryDirectory(prefix="lightning-profile-check-") as folder:
        session = ProfileSession(Path(folder) / "Profiles")
        try:
            pending = session.prepare("Synthetic household", "temporary synthetic password", "temporary synthetic password")
            session.confirm(True)
            path = session.paths.db_path
            session.container.settings.set("profile_check", "synthetic marker")
            checks["profile_setup"] = path.is_file() and b"synthetic marker" not in path.read_bytes()
            app = create_app(session.container)
            checks["finance_routes"] = (str(app.url_path_for("dashboard")) == "/"
                                        and str(app.url_path_for("new_account")) == "/accounts/new")
            session.close()
            session.unlock(str(path), "temporary synthetic password")
            checks["profile_reopen"] = session.container.settings.get("profile_check") == "synthetic marker"
            checks["profile_backup"] = bool(session.container.backup_files())
            session.close()
            session.recover(str(path), pending.recovery, "recovered synthetic password", "recovered synthetic password")
            session.unlock(str(path), "recovered synthetic password")
            checks["profile_recovery"] = session.container.settings.get("profile_check") == "synthetic marker"
        finally:
            session.close()
    return checks
