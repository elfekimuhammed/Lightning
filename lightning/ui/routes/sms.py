"""From SMS (milestone 3): paste bank messages, say once which account an ending is, then review them on the
bank import's review screen. The phone app will also send new messages here by itself."""
from __future__ import annotations

import re
from datetime import datetime

from fastapi import APIRouter, Request

from lightning.core.errors import LightningError
from lightning.sms_imports import MAX_TEXT, SALARY_ENDING

from ..web import container, redirect, render

router = APIRouter(prefix="/sms")
MAX_PASTE = 50  # messages in one paste


def _page(request, c, **context):
    accounts = [a for a in c.accounts.list(active_only=True) if a.account_type.value in ("BANK", "CASH")]
    names = {a.id: a.name for a in c.accounts.list()}
    batches = [b | {"account": names.get(b["account_id"], "")} for b in c.bank_imports.waiting_all()
               if str(b["file_name"]).startswith("SMS ")]
    return render(request, "sms.html", waiting=c.sms_imports.waiting(), accounts=accounts, batches=batches,
                  salary=SALARY_ENDING, **context)


@router.get("")
async def sms_page(request: Request):
    return _page(request, container(request))


@router.post("/paste")
async def paste(request: Request):
    c = container(request)
    form = await request.form()
    text = str(form.get("messages", ""))[:MAX_TEXT * MAX_PASTE]
    messages = [m.strip() for m in re.split(r"\n\s*\n", text) if m.strip()][:MAX_PASTE]
    if not messages:
        return _page(request, c, error="Paste one or more bank messages, a blank line between each.")
    now = datetime.now()
    result = c.sms_imports.read([("", m, now) for m in messages])
    found = sum(len(c.bank_imports.preview(batch)[1]) for batch in result["staged"].values())
    parts = []
    if found:
        parts.append(f"{found} ready to review")
    if result["waiting"]:
        parts.append(f"{result['waiting']} waiting for their account")
    if result["skipped"]:
        parts.append(f"{result['skipped']} skipped (read before, or not a payment)")
    return redirect("/sms", "; ".join(parts).capitalize() + ".")


@router.post("/assign")
async def assign(request: Request):
    c = container(request)
    form = await request.form()
    try:
        batch = c.sms_imports.assign(str(form.get("ending", "")), int(str(form.get("account_id", "0")) or 0))
    except (LightningError, ValueError) as exc:
        return _page(request, c, error=getattr(exc, "message", "") or "Choose the account for these messages.")
    if batch is None:
        return redirect("/sms", "Saved.")
    account_id = c.bank_imports.preview(batch)[0]["account_id"]
    return redirect(f"/accounts/{account_id}/import/{batch}", "Check each row, then post them.")
