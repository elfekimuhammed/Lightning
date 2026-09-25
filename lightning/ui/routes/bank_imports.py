from __future__ import annotations

import base64
import hashlib

from fastapi import APIRouter, Request

from lightning.accounts.domain import AccountType
from lightning.bank_imports import OPTIONAL, REQUIRED, decode_csv
from lightning.core.errors import LightningError, ValidationError
from lightning.counterparties import normalize
from lightning.categories.domain import Movement

from ..web import container, redirect, render

router = APIRouter(prefix="/accounts")

def _key(value: str) -> str:
    return hashlib.sha1(normalize(value).encode()).hexdigest()[:12]


def _categories(c):
    return [{"id": cat.id, "label": c.categories.display_name(cat.id)}
            for movement in (Movement.OUTFLOW, Movement.INFLOW) for cat in c.categories.pickable(movement)]


def _choices(c, value):
    exact = c.counterparties.resolve(value)
    return {"exact": exact, "suggestions": c.counterparties.suggestions(value)}


@router.get("/{account_id:int}/import")
async def import_page(request: Request, account_id: int):
    c = container(request)
    account = c.accounts.get(account_id)
    if account.account_type != AccountType.BANK:
        raise ValidationError("CSV import is currently available for bank accounts only.")
    return render(request, "bank_import_upload.html", account=account)


@router.post("/{account_id:int}/import")
async def upload(request: Request, account_id: int):
    c = container(request)
    form = await request.form()
    upload_file = form.get("file")
    if not upload_file or not getattr(upload_file, "filename", ""):
        return render(request, "bank_import_upload.html", account=c.accounts.get(account_id), error="Choose a CSV file.", status_code=400)
    data = await upload_file.read()
    try:
        headers, _ = decode_csv(data)
        try:
            batch_id, repeated = c.bank_imports.stage(account_id, upload_file.filename, data,
                                                       invert_amount=form.get("invert_amount") == "on")
        except ValidationError as exc:
            if exc.field == "mapping":
                return render(request, "bank_import_map.html", account=c.accounts.get(account_id), headers=headers,
                              payload=base64.b64encode(data).decode("ascii"), filename=upload_file.filename,
                              required=REQUIRED, optional=OPTIONAL)
            raise
    except LightningError as exc:
        return render(request, "bank_import_upload.html", account=c.accounts.get(account_id), error=exc.message, status_code=400)
    if repeated:
        return redirect(f"/accounts/{account_id}/import/{batch_id}", "This exact file was already imported; no rows were posted again.")
    return redirect(f"/accounts/{account_id}/import/{batch_id}")


@router.post("/{account_id:int}/import/map")
async def map_columns(request: Request, account_id: int):
    c = container(request)
    form = await request.form()
    try:
        data = base64.b64decode(str(form.get("payload", "")), validate=True)
        mapping = {key: str(form.get(f"map_{key}", "")) for key in (*REQUIRED, *OPTIONAL)}
        mapping = {key: value for key, value in mapping.items() if value}
        batch_id, repeated = c.bank_imports.stage(account_id, str(form.get("filename", "statement.csv")), data, mapping,
                                                     invert_amount=form.get("amount_sign") == "invert")
    except (ValueError, LightningError) as exc:
        msg = exc.message if isinstance(exc, LightningError) else "The uploaded statement could not be read. Upload it again."
        return render(request, "bank_import_upload.html", account=c.accounts.get(account_id), error=msg, status_code=400)
    if repeated:
        return redirect(f"/accounts/{account_id}/import/{batch_id}", "This exact file was already imported.")
    return redirect(f"/accounts/{account_id}/import/{batch_id}")


@router.get("/{account_id:int}/import/{batch_id:int}")
async def preview(request: Request, account_id: int, batch_id: int):
    c = container(request)
    batch, rows = c.bank_imports.preview(batch_id)
    if batch["account_id"] != account_id:
        return redirect(f"/accounts/{account_id}", "Import batch not found for this account.")
    raw_by_key = {_key(row["Counterparty"]): row["Counterparty"] for row in rows}
    raw_names = list(raw_by_key.values())
    groups = [{"raw": raw, "key": _key(raw), **_choices(c, raw)}
              for raw in raw_names]
    categories = _categories(c)
    for group in groups:
        group["suggested_category_id"] = next((row["_category_id"] for row in rows if row["Counterparty"] == group["raw"] and row["_category_id"]), None)
    counterparties = c.counterparties.list_active()
    return render(request, "bank_import_preview.html", account=c.accounts.get(account_id), batch=batch, rows=rows,
                  groups=groups, categories=categories, counterparties=counterparties,
                  summary=c.bank_imports.summary(batch_id))


@router.post("/{account_id:int}/import/{batch_id:int}/confirm")
async def confirm(request: Request, account_id: int, batch_id: int):
    c = container(request)
    batch, rows = c.bank_imports.preview(batch_id)
    if batch["account_id"] != account_id:
        return redirect(f"/accounts/{account_id}", "Import batch not found for this account.")
    form = await request.form()
    groups = {g["key"]: g["raw"] for g in ({"key": _key(r["Counterparty"]), "raw": r["Counterparty"]} for r in rows)}
    decisions = {}
    for row in rows:
        row_id = row["_import_row_id"]
        key = _key(row["Counterparty"])
        choice = str(form.get(f"counterparty_{key}", ""))
        group_category = form.get(f"category_cp_{key}") or None
        decision = {"category_id": form.get(f"category_{row_id}") or group_category,
                    "skip": form.get(f"skip_{row_id}") == "on"}
        if choice.startswith("existing:"):
            decision["counterparty_id"] = int(choice.split(":", 1)[1])
        elif choice == "new":
            decision["new_counterparty"] = str(form.get(f"canonical_name_{key}", "")).strip()
        if form.get(f"category_cp_{key}"):
            decision["remember_category"] = True
        decisions[row_id] = decision
    try:
        count = c.bank_imports.confirm(batch_id, decisions)
    except LightningError as exc:
        batch, rows = c.bank_imports.preview(batch_id)
        raw_by_key = {_key(row["Counterparty"]): row["Counterparty"] for row in rows}
        raw_names = list(raw_by_key.values())
        groups_view = [{"raw": raw, "key": _key(raw),
                        "suggested_category_id": next((r["_category_id"] for r in rows if r["Counterparty"] == raw and r["_category_id"]), None),
                        **_choices(c, raw)} for raw in raw_names]
        counterparties = c.counterparties.list_active()
        return render(request, "bank_import_preview.html", account=c.accounts.get(account_id), batch=batch, rows=rows,
                      groups=groups_view, categories=_categories(c), counterparties=counterparties,
                      summary=c.bank_imports.summary(batch_id), error=exc.message, status_code=400)
    return redirect(f"/accounts/{account_id}?date={rows[0]['Date'] if rows else ''}",
                    f"Import complete: {count['posted']} posted, {count['skipped']} skipped, {count['duplicates']} duplicates.")
