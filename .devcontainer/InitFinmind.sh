#!/bin/bash

echo "[startup] Using current path: $DEVC_VENV_PATH"

mkdir -p /workspace/packages

pushd /workspace/packages
git clone https://github.com/FinMind/FinMind.git
pushd /workspace/packages/FinMind
git branch
cp -av /workspace/packages/FinMind/.claude/commands/* ~/.claude/commands/
popd
popd

export UV_VENV_CLEAR=1
uv venv finmind 
# source finmind/bin/activate 
uv pip install -r /workspace/packages/FinMind/requirements.txt \
   --python finmind
uv pip install finmind jupyterlab requests matplotlib scipy \
   --python finmind

