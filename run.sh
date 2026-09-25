#!/usr/bin/env bash
# Lightning launcher for macOS / Linux
set -u
cd "$(dirname "$0")"
[ -x .venv/bin/python ] || python3 -m venv .venv
if [ ! -f .venv/.requirements-installed ] || [ requirements.txt -nt .venv/.requirements-installed ] ||
   ! .venv/bin/python -c 'import fastapi, uvicorn, jinja2, multipart' >/dev/null 2>&1; then
    .venv/bin/python -m pip install --quiet --disable-pip-version-check -r requirements.txt || exit 1
    touch .venv/.requirements-installed
fi
server_pid=""
stop_server() {
    if [ -n "$server_pid" ] && kill -0 "$server_pid" 2>/dev/null; then
        kill -TERM "$server_pid" 2>/dev/null || true
        wait "$server_pid" 2>/dev/null || true
    fi
    server_pid=""
}
trap 'stop_server; exit 130' INT
trap 'stop_server; exit 143' TERM

while true; do
    .venv/bin/python -m lightning "$@" &
    server_pid=$!
    if [ ! -t 0 ]; then
        wait "$server_pid"
        exit $?
    fi
    printf '\nLightning is running. Type y then Enter to restart it; press Ctrl+C to stop.\n'
    while kill -0 "$server_pid" 2>/dev/null; do
        if IFS= read -r -t 1 answer; then
            case "$answer" in
                y|Y)
                    printf 'Restarting Lightning...\n'
                    stop_server
                    break
                    ;;
                *)
                    printf 'Type y then Enter to restart Lightning.\n'
                    ;;
            esac
        fi
    done
    if [ -n "$server_pid" ]; then
        wait "$server_pid"
        status=$?
        server_pid=""
        if [ "$status" -ne 0 ]; then
            printf 'Lightning exited with status %s. Type y then Enter to start it again, or Ctrl+C to quit.\n' "$status"
            while IFS= read -r answer; do
                case "$answer" in
                    y|Y) break ;;
                    *) printf 'Type y then Enter to start Lightning again.\n' ;;
                esac
            done
            [ "${answer:-}" = y ] || [ "${answer:-}" = Y ] || exit "$status"
        else
            exit 0
        fi
    fi
done
