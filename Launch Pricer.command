#!/bin/bash
# Double-click this file on macOS to launch the option pricer in your browser.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo
echo "  Option Pricer"
echo "  Installing anything missing, then opening your browser ..."
echo

pick_python() {
  if [[ -x "$ROOT/.venv/bin/python" ]]; then
    echo "$ROOT/.venv/bin/python"
    return 0
  fi
  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return 0
  fi
  if command -v python >/dev/null 2>&1; then
    command -v python
    return 0
  fi
  return 1
}

if ! PY="$(pick_python)"; then
  echo "Python 3 was not found."
  echo "Install it from https://www.python.org/downloads/ then double-click this file again."
  if command -v open >/dev/null 2>&1; then
    open "https://www.python.org/downloads/"
  fi
  echo
  read -r -p "Press Return to close this window..."
  exit 1
fi

"$PY" "$ROOT/launch.py" || status=$?
status="${status:-0}"
if [[ "$status" -ne 0 ]]; then
  echo
  echo "The pricer exited with an error ($status)."
  read -r -p "Press Return to close this window..."
  exit "$status"
fi
