#!/bin/bash

LOG_FILE="${HOME}/jupyter_lab.log"

# --- Parameters ---
export DEVC_VENV_PATH="$1"

# --- Validate CURRENT_PATH ---
if [ -z "$DEVC_VENV_PATH" ]; then
    echo "[error] Missing parameter for  DEVC_VENV_PATH"
    exit 1
fi

echo "[startup] Using current path: $DEVC_VENV_PATH"

# Each process when every time devcontainer creating
.devcontainer/InitFinmind.sh
.devcontainer/InitGitEnv.sh

mkdir -p ~/.claude/commands
curl -o ~/.claude/commands/finmind.md \
  https://raw.githubusercontent.com/FinMind/FinMind/master/.claude/commands/finmind.md

mkdir -p /workspace/packages
pushd /workspace/packages
git clone https://github.com/FinMind/FinMind.git
git branch
popd