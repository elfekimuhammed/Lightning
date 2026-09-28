from __future__ import annotations

import base64
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from lightning.bank_imports import OPTIONAL, REQUIRED, SEPARATE_AMOUNT_FIELDS, decode_csv
from lightning.core.errors import LightningError, ValidationError
from lightning.core.money import fmt

from ..web import container, redirect, render

router = APIRouter(prefix="/accounts")


def _budget_import_feedback(c, batch_id: int) -> str:
    _, rows = c.bank_imports.preview(batch_id)
    by_month: dict[str, set[int]] = {}
    for row in rows:
        if row.get("_status") != "POSTED" or not row.get("_transaction_id"):
            continue
        txn = c.transactions.get(int(row["_transaction_id"]))
        for line in txn.lines:
            if line.category_id and line.effect.value == "OUTFLOW":
                by_month.setdefault(txn.date[:7], set()).add(line.category_id)
    impacts = []
    for month, category_ids in by_month.items():
        view = c.budgets.month_view(month)
        budget_lines = {line.category_id: line for section in view.sections for line in section.lines}
        for category_id in category_ids:
            line = budget_lines.get(category_id)
            if line:
                shown = line
                if shown.remaining is None and shown.covered:
                    parent = c.categories.get(category_id).parent_id
                    while parent:
                        ancestor = budget_lines.get(parent)
                        if ancestor and ancestor.remaining is not None:
                            shown = ancestor
                            break
                        parent = c.categories.get(parent).parent_id
                status = (f"{fmt(shown.remaining)} {c.base_currency} left" if shown.remaining is not None
                          else ("inside a group limit" if line.covered else "unplanned"))
                impacts.append(f"{line.name} ({status})")
    return f" Budget · {', '.join(impacts[:3])}." if impacts else ""

def _categories(c):
    return [{"id": cat.id, "label": c.categories.display_name(cat.id)} for cat in c.categories.pickable()]


def _ai_reference(c):
    return {"counterparties": [party["name"] for party in c.counterparties.list_active()],
            "categories": _categories(c)}


def _ai_prompt(account, reference):
    cats = "\n".join(f"- {item['label']} (id: {item['id']})" for item in reference["categories"])
    parties = "\n".join(f"- {name}" for name in reference["counterparties"])
    return f'''Prepare an account statement CSV for review and import into Lightning.
Account: {account.name}
Currency: {account.currency}

Return a standard UTF-8 CSV file with a header row, using exactly this canonical schema: Date,Amount,Counterparty,Category,Notes,Reference. Date and Amount are required; the remaining columns are optional and may be blank. Date must use YYYY-MM-DD. If the source only has separate inflow/outflow columns, the importer also accepts Date,Inflow,Outflow instead of Amount; each row must have a value in exactly one of those amount columns, with no Amount column.

Quote CSV fields when needed to preserve commas, quotes, or line breaks. Preserve the source dates and amount values in meaning; do not change currency, round, or infer missing values. Express direction as the account's perspective: money into the account is positive and money out is negative. For separate columns, place nonnegative values in Inflow or Outflow respectively. Keep optional values only when present in the source. Reference is an optional source transaction identifier. Do not add unsupported columns.

Match Category only to the exact pickable category labels below. Match Counterparty only when the source supports a confident match to one of the existing active names below; do not invent matches or create names. Leave unknown or ambiguous categories blank (and leave unknown counterparties unchanged or blank if absent). Do not use category IDs as CSV values.

Existing active counterparties:\n{parties or '- (none)'}

Pickable categories:\n{cats or '- (none)'}

Review every output row against the source before confirming the import. Do not claim the import is complete.'''


def _review_form_max_fields(row_count: int) -> int:
    # Each row has fewer than 12 submitted fields; leave room for form metadata.
    return max(1_000, row_count * 12 + 100)


@router.get("/{account_id:int}/import")
async def import_page(request: Request, account_id: int):
    c = container(request)
    account = c.accounts.get(account_id)
    return render(request, "bank_import_upload.html", account=account,
                  ai_prompt=_ai_prompt(account, _ai_reference(c)))


def _render_upload(request, c, account_id, *, error="", status_code=200):
    account = c.accounts.get(account_id)
    return render(request, "bank_import_upload.html", account=account,
                  ai_prompt=_ai_prompt(account, _ai_reference(c)), error=error, status_code=status_code)


@router.get("/{account_id:int}/import/ai-reference.json")
async def ai_reference(request: Request, account_id: int):
    c = container(request)
    account = c.accounts.get(account_id)
    return JSONResponse({"account": account.name, "currency": account.currency, **_ai_reference(c)},
                        headers={"Content-Disposition": 'attachment; filename="lightning-import-reference.json"',
                                 "Cache-Control": "no-store"})


@router.get("/{account_id:int}/import/ai-template.csv")
async def ai_template(request: Request, account_id: int):
    container(request).accounts.get(account_id)
    return PlainTextResponse("Date,Amount,Counterparty,Category,Notes,Reference\r\n",
                             media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": 'attachment; filename="lightning-import-template.csv"'})


@router.post("/{account_id:int}/import")
async def upload(request: Request, account_id: int):
    c = container(request)
    form = await request.form()
    upload_file = form.get("file")
    if not upload_file or not getattr(upload_file, "filename", ""):
        return _render_upload(request, c, account_id, error="Choose a CSV file.", status_code=400)
    data = await upload_file.read()
    try:
        headers, _ = decode_csv(data)
        mapping = c.bank_imports.suggested_mapping(account_id, headers)
        saved_mapping = c.bank_imports.saved_mapping(account_id, headers)
        if saved_mapping:
            batch_id, repeated = c.bank_imports.stage(
                account_id, upload_file.filename, data, saved_mapping,
                invert_amount=saved_mapping.get("amount_sign") == "invert")
            if repeated:
                return redirect(f"/accounts/{account_id}/import/{batch_id}",
                                "This exact file was already imported.")
            return redirect(f"/accounts/{account_id}/import/{batch_id}")
        return render(request, "bank_import_map.html", account=c.accounts.get(account_id), headers=headers,
                      payload=base64.b64encode(data).decode("ascii"), filename=upload_file.filename,
                      required=REQUIRED, optional=OPTIONAL, amount_fields=SEPARATE_AMOUNT_FIELDS,
                      suggested_amount_model=mapping.get("amount_model", "SINGLE"), mapping=mapping,
                      invert_amount=mapping.get("amount_sign") == "invert")
    except LightningError as exc:
        return _render_upload(request, c, account_id, error=exc.message, status_code=400)
    if repeated:
        return redirect(f"/accounts/{account_id}/import/{batch_id}", "This exact file was already imported; no rows were posted again.")
    return redirect(f"/accounts/{account_id}/import/{batch_id}")


@router.post("/{account_id:int}/import/map")
async def map_columns(request: Request, account_id: int):
    c = container(request)
    form = await request.form()
    headers = []
    data = b""
    mapping = {}
    filename = str(form.get("filename", "statement.csv"))
    try:
        data = base64.b64decode(str(form.get("payload", "")), validate=True)
        headers, _ = decode_csv(data)
        amount_model = str(form.get("amount_model", "SINGLE"))
        mapping = {"amount_model": amount_model}
        selected_amount_fields = REQUIRED if amount_model == "SINGLE" else ("Date", *SEPARATE_AMOUNT_FIELDS)
        mapping.update({key: str(form.get(f"map_{key}", "")) for key in (*selected_amount_fields, *OPTIONAL)})
        mapping = {key: value for key, value in mapping.items() if value}
        batch_id, repeated = c.bank_imports.stage(account_id, filename, data, mapping,
                                                     invert_amount=form.get("amount_sign") == "invert")
    except (ValueError, LightningError) as exc:
        if isinstance(exc, ValidationError) and exc.field == "mapping":
            return render(request, "bank_import_map.html", account=c.accounts.get(account_id), headers=headers,
                          payload=base64.b64encode(data).decode("ascii"), filename=filename,
                          required=REQUIRED, optional=OPTIONAL, amount_fields=SEPARATE_AMOUNT_FIELDS,
                          suggested_amount_model=mapping.get("amount_model", "SINGLE"), mapping=mapping,
                          invert_amount=form.get("amount_sign") == "invert", error=exc.message, status_code=400)
        msg = exc.message if isinstance(exc, LightningError) else "The uploaded statement could not be read. Upload it again."
        return _render_upload(request, c, account_id, error=msg, status_code=400)
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
                  counterparty_search_names=c.counterparties.search_names(),
                  summary=c.bank_imports.summary(batch_id))


@router.post("/{account_id:int}/import/{batch_id:int}/confirm")
async def confirm(request: Request, account_id: int, batch_id: int):
    c = container(request)
    batch, rows = c.bank_imports.preview(batch_id)
    if batch["account_id"] != account_id:
        return redirect(f"/accounts/{account_id}", "Import batch not found for this account.")
    # Starlette defaults to 1,000 form fields. The review has several editable
    # controls per imported row, so size the parser budget to this staged batch.
    form = await request.form(max_fields=_review_form_max_fields(len(rows)))
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
                    "owner_choice": form.get(f"owner_choice_{row_id}", ""),
                    "counterparty_choice": form.get(f"counterparty_choice_{row_id}", ""),
                    "remember_category": form.get(f"remember_category_{row_id}") == "on"}
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
            row["_owner_choice"] = str(form.get(f"owner_choice_{row_id}", ""))
            category_choice = str(form.get(f"category_{row_id}", ""))
            row["_category_id"] = int(category_choice) if category_choice.isdigit() else None
            row["_counterparty_choice"] = str(form.get(f"counterparty_choice_{row_id}", ""))
            row["_remember_category"] = form.get(f"remember_category_{row_id}") == "on"
            row["_skip"] = form.get(f"skip_{row_id}") == "on"
        counterparties = c.counterparties.list_active()
        return render(request, "bank_import_preview.html", account=c.accounts.get(account_id), batch=batch, rows=rows,
                      categories=_categories(c), counterparties=counterparties,
                      counterparty_search_names=c.counterparties.search_names(),
                      summary=c.bank_imports.summary(batch_id), error=exc.message, status_code=400)
    if count.get("errors"):
        batch, review_rows = c.bank_imports.preview(batch_id)
        for row in review_rows:
            row_id = row["_import_row_id"]
            row["Date"] = str(form.get(f"date_{row_id}", row["Date"]))
            row["Counterparty"] = str(form.get(f"counterparty_{row_id}", row["Counterparty"]))
            row["Amount"] = str(form.get(f"amount_{row_id}", row["Amount"]))
            row["Notes"] = str(form.get(f"notes_{row_id}", row["Notes"]))
            row["_whom"] = str(form.get(f"whom_{row_id}", row.get("_whom", "")))
            row["_owner_choice"] = str(form.get(f"owner_choice_{row_id}", ""))
            category_choice = str(form.get(f"category_{row_id}", ""))
            row["_category_id"] = int(category_choice) if category_choice.isdigit() else None
            row["_counterparty_choice"] = str(form.get(f"counterparty_choice_{row_id}", ""))
            row["_remember_category"] = form.get(f"remember_category_{row_id}") == "on"
            row["_skip"] = form.get(f"skip_{row_id}") == "on"
            row["_row_error"] = count["errors"].get(int(row_id))
            row["_hide_row"] = not bool(row["_row_error"])
        counterparties = c.counterparties.list_active()
        msg = (f"Nothing was imported. {len(count['errors'])} row(s) need attention. "
               "Only rows with problems are shown; other rows remain in the review and their edits are kept.")
        return render(request, "bank_import_preview.html", account=c.accounts.get(account_id), batch=batch,
                      rows=review_rows, categories=_categories(c), counterparties=counterparties,
                      counterparty_search_names=c.counterparties.search_names(),
                      summary=c.bank_imports.summary(batch_id), msg=msg)
    feedback = _budget_import_feedback(c, batch_id)
    if count.get("ambiguous_reserves"):
        feedback += f" {count['ambiguous_reserves']} row(s) could match multiple reserves; review them on the Reserves page."
    batch, result_rows = c.bank_imports.preview(batch_id)
    return render(request, "bank_import_preview.html", account=c.accounts.get(account_id), batch=batch,
                  rows=result_rows, categories=_categories(c), counterparties=c.counterparties.list_active(),
                  counterparty_search_names=c.counterparties.search_names(), summary=count,
                  msg=f"Import complete: {count['posted']} posted, {count['skipped']} skipped, {count['duplicates']} duplicates.{feedback}")
