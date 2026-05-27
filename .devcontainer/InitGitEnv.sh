#!/usr/bin/env bash
# =============================================================================
# Git Configuration Setup
#
# Configures global git settings for the vscode user.
# Runs once via postCreateCommand when the container is first created.
#
# Settings applied:
#   - user.name                  : commit author name
#   - user.email                 : commit author email
#   - http.postBuffer = 100 MB   : allow large pushes (LFS / big repos)
#   - http.maxRequests = 5       : limit parallel HTTP requests
#   - core.fileMode = false      : ignore file mode (chmod) changes,
#                                   useful when host/container UIDs differ
# =============================================================================
set -e

echo "[setup_git] Configuring global git settings..."

git config --global user.name        "Raul Hsiao"
git config --global user.email       "Raul_Hsiao@chicony.com"
git config --global http.postBuffer  104857600
git config --global http.maxRequests 5
git config --global core.fileMode    false
git config --global init.defaultBranch main

# ---- Show resulting config for verification ----
echo "[setup_git] Active git configuration:"
git config --global --list | sed 's/^/  /'

echo "[setup_git] ✓ Done"