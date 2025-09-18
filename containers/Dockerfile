# Multi-stage Dockerfile for llm-cpp-toolkit
FROM ubuntu:24.04 AS base

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # Build essentials
    build-essential \
    cmake \
    ninja-build \
    git \
    curl \
    wget \
    unzip \
    # Python
    python3 \
    python3-pip \
    python3-venv \
    # Core tools
    clang-18 \
    clang-tools-18 \
    clang-tidy-18 \
    clang-format-18 \
    bear \
    # Search and file tools
    ripgrep \
    fd-find \
    # JSON/YAML tools
    jq \
    # Optional but useful
    include-what-you-use \
    cppcheck \
    universal-ctags \
    # Clean up
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create symbolic links for clang tools
RUN ln -sf clang-18 /usr/bin/clang && \
    ln -sf clang++-18 /usr/bin/clang++ && \
    ln -sf clang-tidy-18 /usr/bin/clang-tidy && \
    ln -sf clang-format-18 /usr/bin/clang-format

# Install additional tools via pip
RUN python3 -m pip install --no-cache-dir \
    yq \
    pre-commit

# Development stage with additional tools
FROM base AS development

# Install development and ergonomic tools
RUN apt-get update && apt-get install -y \
    # Additional dev tools
    gdb \
    valgrind \
    strace \
    # Ergonomic tools
    fzf \
    bat \
    tree \
    htop \
    # Version control
    git-extras \
    # Network tools
    httpie \
    # Documentation
    man-db \
    # Clean up
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install additional tools from GitHub releases
RUN curl -fsSL https://github.com/sharkdp/tokei/releases/latest/download/tokei-x86_64-unknown-linux-gnu.tar.gz | \
    tar -xzC /usr/local/bin tokei && \
    curl -fsSL https://github.com/sharkdp/hyperfine/releases/latest/download/hyperfine-v1.18.0-x86_64-unknown-linux-gnu.tar.gz | \
    tar -xzC /tmp && \
    mv /tmp/hyperfine-v1.18.0-x86_64-unknown-linux-gnu/hyperfine /usr/local/bin/ && \
    rm -rf /tmp/hyperfine-*

# Production stage
FROM base AS production

# Set working directory
WORKDIR /opt/llmtk

# Copy toolkit source
COPY . .

# Install llmtk
RUN python3 -m pip install --no-cache-dir -e .

# Create wrapper script
RUN echo '#!/bin/bash\nexec python3 /opt/llmtk/cli/llmtk "$@"' > /usr/local/bin/llmtk && \
    chmod +x /usr/local/bin/llmtk

# Set up environment
ENV LLMTK_DIR=/opt/llmtk
ENV PATH="/opt/llmtk/.llmtk/bin:$PATH"

# Create non-root user
RUN groupadd -r llmtk && useradd -r -g llmtk -s /bin/bash -c "LLMTK User" llmtk && \
    mkdir -p /home/llmtk && \
    chown -R llmtk:llmtk /home/llmtk /opt/llmtk

USER llmtk
WORKDIR /home/llmtk

# Install local tools
RUN llmtk install --local

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD llmtk doctor || exit 1

# Default command
CMD ["llmtk", "--help"]

# Development variant
FROM development AS dev

# Install additional development tools
RUN python3 -m pip install --no-cache-dir \
    pytest \
    black \
    isort \
    mypy \
    ruff

# Set working directory
WORKDIR /workspace

# Copy toolkit for development
COPY . /opt/llmtk/

# Set up development environment
ENV LLMTK_DIR=/opt/llmtk
ENV PATH="/opt/llmtk/.llmtk/bin:$PATH"

# Create development wrapper
RUN echo '#!/bin/bash\nexec python3 /opt/llmtk/cli/llmtk "$@"' > /usr/local/bin/llmtk && \
    chmod +x /usr/local/bin/llmtk

# Default to development user
USER root

# Entry point for development
ENTRYPOINT ["/bin/bash"]