#!/bin/bash

echo "[startup] Using current path: $DEVC_VENV_PATH"

export UV_VENV_CLEAR=1
uv venv finmind && . finmind/bin/activate && uv pip install finmind pandas numpy jupyterlab requests
