#!/usr/bin/env bash
set -euo pipefail

# Build Flatpak for llm-cpp-toolkit

echo "Building Flatpak for llm-cpp-toolkit"

# Install flatpak-builder if not present
if ! command -v flatpak-builder &> /dev/null; then
    echo "Installing flatpak-builder..."
    sudo apt install flatpak-builder -y
fi

# Add Flathub repository if not already added
flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo

# Install required runtimes
flatpak install flathub org.freedesktop.Platform//23.08 org.freedesktop.Sdk//23.08 -y

# Clean previous builds
rm -rf build-dir repo .flatpak-builder || true

# Build the Flatpak
flatpak-builder build-dir io.github.gregvw.llm-cpp-toolkit.yml --force-clean --install-deps-from=flathub

# Create repository
flatpak build-export repo build-dir

echo "Flatpak built successfully!"
echo "Install with: flatpak install --user repo io.github.gregvw.llm-cpp-toolkit"