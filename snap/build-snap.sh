#!/usr/bin/env bash
set -euo pipefail

# Build Snap package for llm-cpp-toolkit

echo "Building Snap package for llm-cpp-toolkit"

# Install snapcraft if not present
if ! command -v snapcraft &> /dev/null; then
    echo "Installing snapcraft..."
    sudo snap install snapcraft --classic
fi

# Clean previous builds
snapcraft clean || true

# Build the snap
snapcraft

echo "Snap package built successfully!"
ls -la *.snap