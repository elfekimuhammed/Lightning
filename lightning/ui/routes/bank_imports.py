from __future__ import annotations

import base64
from fastapi import APIRouter, Request

from lightning.bank_imports import OPTIONAL, REQUIRED, decode_csv
from lightning.core.errors import LightningError, ValidationError

from ..web import container, redirect, render

router = APIRouter(prefix="/accounts")

def _categories(c):
    return [{"id": cat.id, "label": c.categories.display_name(cat.id)} for cat in c.categories.pickable()]


@router.get("/{account_id:int}/import")
async def import_page(request: Request, account_id: int):
    c = container(request)
    account = c.accounts.get(account_id)
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
    categories = _categories(c)
    counterparties = c.counterparties.list_active()
    return render(request, "bank_import_preview.html", account=c.accounts.get(account_id), batch=batch, rows=rows,
                  categories=categories, counterparties=counterparties,
                  summary=c.bank_imports.summary(batch_id))


@router.post("/{account_id:int}/import/{batch_id:int}/confirm")
async def confirm(request: Request, account_id: int, batch_id: int):
    c = container(request)
    batch, rows = c.bank_imports.preview(batch_id)
    if batch["account_id"] != account_id:
        return redirect(f"/accounts/{account_id}", "Import batch not found for this account.")
    form = await request.form()
    decisions = {}
    for row in rows:
        row_id = row["_import_row_id"]
        category_choice = str(form.get(f"category_{row_id}", ""))
        whom = str(form.get(f"whom_{row_id}", ""))
        decision = {"category_id": category_choice if category_choice and category_choice != "__uncategorized__" else None,
                    "force_uncategorized": category_choice == "__uncategorized__",
                    "skip": form.get(f"skip_{row_id}") == "on",
                    "date": form.get(f"date_{row_id}", row["Date"]),
                    "counterparty": form.get(f"counterparty_{row_id}", row["Counterparty"]),
                    "amount": form.get(f"amount_{row_id}", row["Amount"]),
                    "notes": form.get(f"notes_{row_id}", row["Notes"]),
                    "whom": whom,
                    "counterparty_choice": form.get(f"counterparty_choice_{row_id}", "")}
        selected = decision["counterparty_choice"]
        if selected.startswith("existing:"):
            decision["counterparty_id"] = int(selected.split(":", 1)[1])
        elif selected == "new":
            decision["new_counterparty"] = decision["counterparty"]
        decisions[row_id] = decision
    try:
        count = c.bank_imports.confirm(batch_id, decisions)
    except LightningError as exc:
        batch, rows = c.bank_imports.preview(batch_id)
        for row in rows:
            row_id = row["_import_row_id"]
            row["Date"] = str(form.get(f"date_{row_id}", row["Date"]))
            row["Counterparty"] = str(form.get(f"counterparty_{row_id}", row["Counterparty"]))
            row["Amount"] = str(form.get(f"amount_{row_id}", row["Amount"]))
            row["Notes"] = str(form.get(f"notes_{row_id}", row["Notes"]))
            row["_whom"] = str(form.get(f"whom_{row_id}", ""))
            category_choice = str(form.get(f"category_{row_id}", ""))
            row["_category_id"] = int(category_choice) if category_choice.isdigit() else None
            row["_counterparty_choice"] = str(form.get(f"counterparty_choice_{row_id}", ""))
        counterparties = c.counterparties.list_active()
        return render(request, "bank_import_preview.html", account=c.accounts.get(account_id), batch=batch, rows=rows,
                      categories=_categories(c), counterparties=counterparties,
                      summary=c.bank_imports.summary(batch_id), error=exc.message, status_code=400)
    return redirect(f"/accounts/{account_id}?date={rows[0]['Date'] if rows else ''}",
                    f"Import complete: {count['posted']} posted, {count['skipped']} skipped, {count['duplicates']} duplicates.")
