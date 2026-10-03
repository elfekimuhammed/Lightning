import asyncio
from urllib.parse import urlencode

import pytest
from starlette.exceptions import HTTPException
from starlette.requests import Request

from lightning.runtime.app import _form_field_limit
from lightning.runtime.http import MAX_IMPORT_CONFIRM_BODY, MAX_IMPORT_CONFIRM_FIELDS
from lightning.ui.routes.bank_imports import _review_form_max_fields


def _form_request(body, path):
    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    return Request({
        "type": "http", "http_version": "1.1", "method": "POST", "scheme": "http",
        "path": path, "raw_path": path.encode(), "query_string": b"", "root_path": "",
        "headers": [(b"host", b"testserver"),
                    (b"content-type", b"application/x-www-form-urlencoded")],
        "server": ("testserver", 80), "client": ("testclient", 50000), "app": None,
    }, receive)


async def _read_form(request, **limits):
    # Starlette's form() returns an awaitable wrapper, not a coroutine that asyncio.run accepts.
    return await request.form(**limits)


def test_profile_gate_field_budget_accepts_review_over_former_40k_budget():
    # Eleven controls per row mirrors the review form; ordinary forms remain
    # limited to 2,000 fields while large imports receive a bounded larger cap.
    row_count = 4_001  # More than the former 40,000-field budget.
    values = {
        f"{field}_{row}": "value"
        for row in range(row_count)
        for field in (
            "date", "counterparty", "counterparty_choice", "category",
            "transfer_account_id", "owner_choice", "whom", "notes", "amount",
            "remember_category", "skip",
        )
    }
    body = urlencode(values).encode()
    path = "/accounts/1/import/1/confirm"

    with pytest.raises(HTTPException) as rejected:
        asyncio.run(_read_form(_form_request(body, path), max_fields=2_000))
    assert rejected.value.status_code == 400

    parsed = asyncio.run(_read_form(_form_request(body, path), max_fields=_form_field_limit(path)))
    assert len(parsed) == row_count * 11
    assert _form_field_limit("/accounts/1/import") == 2_000


def test_bounded_confirmation_limits_cover_about_fifty_thousand_rows():
    # The review template submits at most twelve controls per row. A 5 MiB
    # statement averaging about 105 bytes/row can therefore fit this budget.
    maximum_rows = (MAX_IMPORT_CONFIRM_FIELDS - 100) // 12
    assert _review_form_max_fields(maximum_rows) <= MAX_IMPORT_CONFIRM_FIELDS
    assert _review_form_max_fields(maximum_rows + 1) > MAX_IMPORT_CONFIRM_FIELDS
    assert MAX_IMPORT_CONFIRM_BODY == 32 * 1024 * 1024
