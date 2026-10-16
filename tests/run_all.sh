#!/usr/bin/env bash
# Runs every test. Usage: tests/run_all.sh [--no-docker]   (runtime integration needs Docker; skipped explicitly otherwise)
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="tests/lib${PYTHONPATH:+:$PYTHONPATH}" PYTHONDONTWRITEBYTECODE=1
[ "${1:-}" = "--no-docker" ] && export SE_SKIP_DOCKER=1
python3 scripts/build-adapters.py --check
python3 -m unittest discover -s tests -p 'test_*.py' -t tests -v
