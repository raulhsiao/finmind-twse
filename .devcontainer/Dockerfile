FROM python:3.11-slim
# coreutils procp
RUN apt-get update && apt-get install -y curl sudo git vim netcat-openbsd && \
    useradd -m -s /bin/bash vscode && \
    echo "vscode ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers && \
    curl -LsSf https://astral.sh/uv/install.sh | sh

ENV PATH="/root/.local/bin:${PATH}"

# Make uv available to the vscode user
RUN cp -r /root/.local /home/vscode/.local && \
    chown -R vscode:vscode /home/vscode/.local

WORKDIR /workspace
