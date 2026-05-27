#!/bin/bash

echo "[startup] postStartCommand using current path:    ${DEVC_CURRENT_PATH}"
echo "[startup] Python virtual env using venv name:     ${DEVC_VENV_NAME}"
echo "[startup] Jupyter using port:                     ${DEVC_JUPYTER_PORT}"
echo "[startup] Jupyter using log file:                 ${DEVC_JUPYTER_LOG}"


# --- Activate venv ---
source "$DEVC_VENV_NAME/bin/activate"

# ---- Truncate previous log ----
: > "${DEVC_JUPYTER_LOG}"

# --- Start Jupyter Lab ---
echo "[startup] Starting Jupyter Lab..."
# NOTE: Use nohup to prevent jupyter be killed after postStartCommand terminated !!!
nohup jupyter lab --ip=0.0.0.0 --port="${DEVC_JUPYTER_PORT}" --no-browser \
  --NotebookApp.token='' --NotebookApp.password=''  >> "${DEVC_JUPYTER_LOG}" 2>&1 &
JUPYTER_PID=$!

# --- Wait for port to be ready ---
echo "[startup] Waiting for Jupyter Lab to be ready on port ${DEVC_JUPYTER_PORT}..."

for i in $(seq 1 60); do
    # Connection to localhost (127.0.0.1) 28888 port [tcp/*] succeeded!
    if nc -z localhost "${DEVC_JUPYTER_PORT}" 2>/dev/null; then
        echo "Port ${DEVC_JUPYTER_PORT} is open"
        sleep 1
        break
    else
        echo "Port ${DEVC_JUPYTER_PORT} is NOT open"
    fi   
    sleep 1
done

echo "[startup] Jupyter Lab is ready on port ${DEVC_JUPYTER_PORT}"
echo "[startup] Background PID: $JUPYTER_PID"
echo "[startup] Script finished."
