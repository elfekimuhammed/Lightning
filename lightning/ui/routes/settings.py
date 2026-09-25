from __future__ import annotations

from fastapi import APIRouter, Request

from ..web import container, redirect, render

router = APIRouter(prefix="/settings")


@router.get("")
async def settings_page(request: Request):
    c = container(request)
    folder = c.data_dir / "backups"
    backups = sorted(folder.glob("lightning_*.db"), reverse=True)[:10] if folder.exists() else []
    return render(request, "settings/index.html", db_path=c.db.path, backups=[b.name for b in backups],
                  classes=c.assets.list_classes(), assets=c.assets.list_assets())


@router.post("/backup")
async def backup_now(request: Request):
    path = container(request).backup_now()
    return redirect("/settings", f"Backup saved as {path.name}." if path else "Nothing to back up yet.")
