#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
python_command="${PYTHON:-python3}"

if ! "$python_command" -m venv .venv; then
    if command -v uv >/dev/null 2>&1; then
        echo "Python's venv bootstrap is unavailable; using uv to seed .venv."
        uv venv --python "$python_command" --seed --allow-existing .venv
    else
        echo "Install your Python's venv support (e.g. python3-venv on Debian/Ubuntu), or install uv, then rerun this command." >&2
        exit 1
    fi
fi

.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip check
echo "Ready. Activate with: source .venv/bin/activate"
