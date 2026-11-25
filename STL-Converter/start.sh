#!/usr/bin/env bash
# Start the STL/STEP -> DAE converter (Mac/Linux). On the first start a private Python environment (.venv) is created.
cd "$(dirname "$0")" || exit 1
if [ ! -x .venv/bin/python ]; then
  command -v python3 >/dev/null || { echo "Python 3 is missing: https://www.python.org/downloads/"; exit 1; }
  echo "First start: setting up (about 1 minute, needs internet) ..."
  python3 -m venv .venv && .venv/bin/python -m pip install --upgrade pip >/dev/null && .venv/bin/python -m pip install -r requirements.txt \
    || { echo "Setup failed. Delete the .venv folder and try again."; rm -rf .venv; exit 1; }
fi
exec .venv/bin/python stl_converter.py "$@"
