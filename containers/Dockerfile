# syntax=docker/dockerfile:1.6
ARG UBUNTU_IMAGE="docker.io/library/ubuntu:24.04@sha256:7c99632956543d4d6acdfb5a12dd0bafcd1e386bc9b87222e130c5daca7f8eab"

FROM ${UBUNTU_IMAGE} AS base

LABEL org.opencontainers.image.source="https://github.com/gregvw/llm-cpp-toolkit"
LABEL org.opencontainers.image.licenses="BSD-3-Clause"
LABEL org.opencontainers.image.title="LLM C++ Toolkit"

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=UTC

ARG LLVM_VERSION=18
ARG CORE_PACKAGES="build-essential cmake ninja-build git curl wget unzip python3 python3-pip python3-venv bear ripgrep fd-find jq"

RUN --mount=type=cache,target=/var/cache/apt --mount=type=cache,target=/var/lib/apt/lists \
    apt-get update && \
    apt-get install -y --no-install-recommends ${CORE_PACKAGES} "clang-${LLVM_VERSION}" "clangd-${LLVM_VERSION}" "clang-tidy-${LLVM_VERSION}" "clang-format-${LLVM_VERSION}" && \
    ln -sf "clang-${LLVM_VERSION}" /usr/bin/clang && \
    ln -sf "clang++-${LLVM_VERSION}" /usr/bin/clang++ && \
    ln -sf "clang-tidy-${LLVM_VERSION}" /usr/bin/clang-tidy && \
    ln -sf "clang-format-${LLVM_VERSION}" /usr/bin/clang-format && \
    rm -rf /var/lib/apt/lists/*

ARG PIP_PACKAGES="yq==3.2.3 pre-commit==3.7.0"
RUN python3 -m pip install --no-cache-dir ${PIP_PACKAGES}

ARG TOKEI_VERSION="12.1.2"
ARG TOKEI_SHA256="8fa0d30fd512d4d3080ca26b76adbe8c672705bca8dfe88902523b47c07c2c29"
ARG HYPERFINE_VERSION="1.18.0"
ARG HYPERFINE_SHA256="b7c0055e70bd6561f711c7f471a1f0ae8e7f1392f1c6dcc8ac0d4f1891e6c5ae"

RUN set -eux; \
    tmpdir="$(mktemp -d)"; \
    cd "$tmpdir"; \
    curl -fsSLo tokei.tar.gz "https://github.com/XAMPPRocky/tokei/releases/download/v${TOKEI_VERSION}/tokei-${TOKEI_VERSION}-x86_64-unknown-linux-gnu.tar.gz"; \
    echo "${TOKEI_SHA256}  tokei.tar.gz" | sha256sum -c -; \
    tar -xzf tokei.tar.gz --strip-components=1; \
    mv tokei /usr/local/bin/tokei; \
    curl -fsSLo hyperfine.tar.gz "https://github.com/sharkdp/hyperfine/releases/download/v${HYPERFINE_VERSION}/hyperfine-v${HYPERFINE_VERSION}-x86_64-unknown-linux-gnu.tar.gz"; \
    echo "${HYPERFINE_SHA256}  hyperfine.tar.gz" | sha256sum -c -; \
    tar -xzf hyperfine.tar.gz --strip-components=1; \
    mv hyperfine /usr/local/bin/hyperfine; \
    rm -rf "$tmpdir"

FROM base AS runtime
WORKDIR /opt/llmtk

COPY . .

RUN python3 -m pip install --no-cache-dir .

ENV LLMTK_DIR=/opt/llmtk \
    LLMTK_BOOTSTRAP_USE_SOURCE=/opt/llmtk \
    PATH="/opt/llmtk/.llmtk/bin:$PATH"

RUN groupadd -r llmtk && useradd -r -g llmtk -s /bin/bash -c "LLMTK User" llmtk && \
    mkdir -p /home/llmtk && chown -R llmtk:llmtk /home/llmtk /opt/llmtk

USER llmtk
WORKDIR /home/llmtk

RUN llmtk --bootstrap-info >/tmp/bootstrap.json && llmtk install --local

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 CMD llmtk doctor || exit 1
ENTRYPOINT ["llmtk"]
CMD ["--help"]

FROM base AS dev
WORKDIR /workspace
COPY . /opt/llmtk/
RUN if [ -f /opt/llmtk/requirements-dev.txt ]; then \
      python3 -m pip install --no-cache-dir -r /opt/llmtk/requirements-dev.txt; \
    fi
ENV LLMTK_DIR=/opt/llmtk \
    LLMTK_BOOTSTRAP_USE_SOURCE=/opt/llmtk \
    PATH="/opt/llmtk/.llmtk/bin:$PATH"
ENTRYPOINT ["/bin/bash"]
