#!/bin/bash
# check_env.sh -- verifies the aivu-greybox environment is ready to run tests.
# Usage:  bash check_env.sh
# Reports each check in plain English. Makes no changes to anything.

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_ROOT" || exit 1

problems=0
echo "Checking the aivu-greybox environment in:"
echo "  $REPO_ROOT"
echo

if [ -x "$REPO_ROOT/.venv/bin/python" ]; then
    echo "  OK    Virtual environment found (.venv at the repo root)."
else
    echo "  FAIL  No usable virtual environment at .venv -- it is missing or incomplete."
    problems=$((problems + 1))
fi

if [ -x "$REPO_ROOT/.venv/bin/pytest" ]; then
    echo "  OK    pytest is installed inside the venv."
else
    echo "  FAIL  pytest is not installed in the venv."
    problems=$((problems + 1))
fi

if [ -x "$REPO_ROOT/.venv/bin/python" ] && "$REPO_ROOT/.venv/bin/python" -c "import numpy, scipy" >/dev/null 2>&1; then
    echo "  OK    numpy and scipy import cleanly in the venv."
else
    echo "  FAIL  numpy or scipy will not import in the venv."
    problems=$((problems + 1))
fi

epw="$REPO_ROOT/code/aivu_greybox/tests/fixtures/Phoenix_AMY_2024.epw"
if [ -f "$epw" ]; then
    echo "  OK    Phoenix weather file is present in tests/fixtures/."
else
    echo "  FAIL  Phoenix weather file is missing."
    echo "        Expected at: code/aivu_greybox/tests/fixtures/Phoenix_AMY_2024.epw"
    problems=$((problems + 1))
fi

echo
if [ "$problems" -eq 0 ]; then
    echo "ALL GOOD -- the environment is ready. Tests can be run."
else
    echo "$problems problem(s) found above. The environment is NOT ready yet."
fi
