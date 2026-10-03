import asyncio
import base64

from starlette.requests import Request
from starlette.responses import Response

from lightning.runtime.http import (
    MAX_BODY,
    MAX_IMPORT_CONFIRM_BODY,
    MAX_IMPORT_CONFIRM_FIELDS,
    MAX_IMPORT_FILE_BYTES,
    MAX_IMPORT_MAP_BODY,
    MAX_IMPORT_UPLOAD_BODY,
    Credentials,
    Guard,
    _append_bounded_chunk,
    configure_memory_only_import_uploads,
    request_body_limit,
)
from lightning.runtime.app import _form_part_limit
from lightning.bank_imports import decode_csv
from lightning.core.errors import ValidationError


def _request(body: bytes, content_type: str) -> Request:
    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    return Request({
        "type": "http", "http_version": "1.1", "method": "POST", "scheme": "http",
        "path": "/", "raw_path": b"/", "query_string": b"", "root_path": "",
        "headers": [(b"host", b"testserver"), (b"content-type", content_type.encode())],
        "server": ("testserver", 80), "client": ("testclient", 50000), "app": None,
    }, receive)


def _multipart(boundary: str, field: str, data: bytes, filename: str | None = None) -> tuple[bytes, str]:
    disposition = f'Content-Disposition: form-data; name="{field}"'
    if filename is not None:
        disposition += f'; filename="{filename}"'
    body = (f"--{boundary}\r\n{disposition}\r\n\r\n".encode() + data
            + f"\r\n--{boundary}--\r\n".encode())
    return body, f"multipart/form-data; boundary={boundary}"


def test_only_csv_import_routes_receive_larger_bounded_body_budgets():
    assert request_body_limit("/accounts/17/import") == MAX_IMPORT_UPLOAD_BODY
    assert MAX_IMPORT_UPLOAD_BODY == MAX_IMPORT_FILE_BYTES + 64 * 1024
    assert request_body_limit("/accounts/17/import/map") == MAX_IMPORT_MAP_BODY
    assert MAX_IMPORT_MAP_BODY == ((MAX_IMPORT_FILE_BYTES + 2) // 3) * 4 + 64 * 1024
    assert request_body_limit("/accounts/17/import/25/confirm") == MAX_IMPORT_CONFIRM_BODY
    assert MAX_IMPORT_CONFIRM_FIELDS == 600_000
    assert request_body_limit("/profiles/new") == MAX_BODY
    assert request_body_limit("/accounts/17/register") == MAX_BODY


def test_guard_enforces_route_specific_body_limit_and_preserves_default():
    async def send_body(path: str, length: int):
        cfg = Credentials("http://testserver")
        cfg.used = True
        body = b"x" * length
        messages = []

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        async def endpoint(scope, receive, send):
            await receive()
            await Response("accepted", status_code=204)(scope, receive, send)

        scope = {
            "type": "http", "http_version": "1.1", "method": "POST", "scheme": "http",
            "path": path, "raw_path": path.encode(), "query_string": b"", "root_path": "",
            "headers": [(b"host", b"testserver"), (b"origin", b"http://testserver"),
                        (b"content-length", str(length).encode()),
                        (b"cookie", f"{cfg.cookie_name}={cfg.token}".encode())],
            "server": ("testserver", 80), "client": ("testclient", 50000), "app": None,
        }

        async def send(message):
            messages.append(message)

        await Guard(endpoint, cfg)(scope, receive, send)
        status = next(message["status"] for message in messages if message["type"] == "http.response.start")
        response_body = b"".join(message.get("body", b"") for message in messages
                                   if message["type"] == "http.response.body").decode()
        return status, response_body

    async def check():
        assert (await send_body("/accounts/17/import", MAX_IMPORT_UPLOAD_BODY))[0] == 204
        upload_error = await send_body("/accounts/17/import", MAX_IMPORT_UPLOAD_BODY + 1)
        assert upload_error[0] == 413
        assert "CSV files must be 5 MiB or smaller" in upload_error[1]
        assert (await send_body("/accounts/17/import/map", MAX_IMPORT_MAP_BODY))[0] == 204
        assert (await send_body("/accounts/17/import/map", MAX_IMPORT_MAP_BODY + 1))[0] == 413
        assert (await send_body("/profiles/new", MAX_BODY))[0] == 204
        assert (await send_body("/profiles/new", MAX_BODY + 1))[0] == 413

    asyncio.run(check())


def test_single_oversized_chunk_is_rejected_before_appending():
    chunks = bytearray(b"already received")
    before = bytes(chunks)
    assert not _append_bounded_chunk(chunks, b"x" * (MAX_BODY + 1), MAX_BODY)
    assert bytes(chunks) == before

    assert _append_bounded_chunk(chunks, b"small", MAX_BODY)
    assert bytes(chunks) == before + b"small"


def test_5_mib_csv_multipart_upload_stays_in_memory():
    configure_memory_only_import_uploads()
    payload = b"x" * MAX_IMPORT_FILE_BYTES
    body, content_type = _multipart("csv-boundary", "file", payload, "statement.csv")
    assert len(body) <= MAX_IMPORT_UPLOAD_BODY

    async def parse():
        async with _request(body, content_type).form(max_files=1, max_fields=10) as form:
            upload = form["file"]
            assert upload.size == MAX_IMPORT_FILE_BYTES
            assert not upload.file._rolled
            await upload.seek(0)
            assert await upload.read() == payload

    asyncio.run(parse())


def test_5_mib_base64_mapping_field_is_parsed_under_its_own_limit():
    payload = base64.b64encode(b"x" * MAX_IMPORT_FILE_BYTES)
    body, content_type = _multipart("map-boundary", "payload", payload)
    # Mapping controls and multipart headers fit in the reserved envelope.
    assert len(body) <= MAX_IMPORT_MAP_BODY
    assert _form_part_limit("/accounts/17/import/map") == MAX_IMPORT_MAP_BODY

    async def parse():
        async with _request(body, content_type).form(max_files=0, max_fields=2_000,
                                                     max_part_size=MAX_IMPORT_MAP_BODY) as form:
            encoded = form["payload"]
            assert len(encoded) == len(payload)
            assert len(base64.b64decode(encoded, validate=True)) == MAX_IMPORT_FILE_BYTES

    asyncio.run(parse())


def test_large_review_notes_field_uses_confirm_route_part_limit():
    notes = b"n" * (2 * 1024 * 1024)
    body, content_type = _multipart("notes-boundary", "notes_1", notes)
    assert _form_part_limit("/accounts/17/import/8/confirm") == MAX_IMPORT_CONFIRM_BODY

    async def parse():
        async with _request(body, content_type).form(max_files=0, max_fields=10,
                                                     max_part_size=MAX_IMPORT_CONFIRM_BODY) as form:
            assert len(form["notes_1"]) == len(notes)

    asyncio.run(parse())


def test_upload_picker_and_help_text_state_csv_limit_without_other_formats():
    from pathlib import Path

    template = (Path(__file__).parents[1] / "lightning/ui/templates/bank_import_upload.html").read_text()
    assert 'accept=".csv,text/csv"' in template
    assert "CSV files up to 5 MiB are supported." in template


def test_oversized_csv_decoder_returns_readable_mib_limit():
    try:
        decode_csv(b"x" * (MAX_IMPORT_FILE_BYTES + 1))
    except ValidationError as exc:
        assert exc.message == "CSV files must be 5 MiB or smaller."
    else:
        raise AssertionError("an oversized CSV was accepted")
