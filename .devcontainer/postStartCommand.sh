#!/bin/bash

LOG_FILE="${HOME}/jupyter_lab.log"

# --- Parameters ---
export DEVC_CURRENT_PATH="$1"
export DEVC_VENV_NAME="$2"
export DEVC_JUPYTER_PORT="${3:-8888}"   # default port = 8888
export DEVC_JUPYTER_LOG="${HOME}/jupyter_lab.log"

echo "[startup] postStartCommand using current path: ${DEVC_CURRENT_PATH}"
echo "[startup] Python virtual env using venv name: ${DEVC_VENV_NAME}"
echo "[startup] Jupyter using port: ${DEVC_JUPYTER_PORT}"
echo "[startup] Jupyter using log file: ${DEVC_JUPYTER_LOG}"

# Each process when every start up
.devcontainer/StartJupyter.sh