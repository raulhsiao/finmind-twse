#!/bin/bash

localWorkspaceFolder="$1"      # 若未提供參數，預設使用

echo "PWD: $(pwd)"  # /opt/workspace/finmind-dev
echo "localWorkspaceFolder: ${localWorkspaceFolder}"

if [ -z "$localWorkspaceFolder" ]; then
    echo "[error] Missing localWorkspaceFolder parameter"
    echo "Usage: $0 <localWorkspaceFolder>"
    exit 1
fi

if [ -f ${localWorkspaceFolder}/.env ]
then
  ls -l ${localWorkspaceFolder}/.env
else
  cp ${localWorkspaceFolder}/env.example ${localWorkspaceFolder}/.env
  touch ${localWorkspaceFolder}/.env
fi
