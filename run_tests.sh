#!/bin/bash
REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_ROOT" || exit 1
if [ ! -x "$REPO_ROOT/.venv/bin/pytest" ]; then
    echo "Cannot run tests: pytest was not found in the venv."
    echo "Run 'bash check_env.sh' first to see what is wrong."
    exit 1
fi
exec "$REPO_ROOT/.venv/bin/pytest" "$@"
