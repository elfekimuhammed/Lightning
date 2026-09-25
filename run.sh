#!/usr/bin/env sh
# Lightning launcher for macOS / Linux
cd "$(dirname "$0")"
[ -x .venv/bin/python ] || python3 -m venv .venv
if [ ! -f .venv/.requirements-installed ] || [ requirements.txt -nt .venv/.requirements-installed ] ||
   ! .venv/bin/python -c 'import fastapi, uvicorn, jinja2, multipart' >/dev/null 2>&1; then
    .venv/bin/python -m pip install --quiet --disable-pip-version-check -r requirements.txt || exit 1
    touch .venv/.requirements-installed
fi
exec .venv/bin/python -m lightning "$@"
