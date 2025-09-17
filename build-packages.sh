#!/usr/bin/env bash
set -euo pipefail

# Unified package builder for llm-cpp-toolkit
# Builds all distribution packages

VERSION=${VERSION:-$(cat VERSION)}
export VERSION

echo "Building packages for llm-cpp-toolkit v${VERSION}"

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to build specific package type
build_package() {
    local package_type="$1"
    echo "Building ${package_type}..."

    case "$package_type" in
        "appimage")
            cd appimage && ./build-appimage.sh && cd ..
            ;;
        "snap")
            cd snap && ./build-snap.sh && cd ..
            ;;
        "flatpak")
            cd flatpak && ./build-flatpak.sh && cd ..
            ;;
        "npm")
            echo "Building npm package..."
            npm pack
            ;;
        *)
            echo "Unknown package type: $package_type"
            return 1
            ;;
    esac
}

# Parse command line arguments
PACKAGES=()
BUILD_ALL=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --all)
            BUILD_ALL=true
            shift
            ;;
        --appimage)
            PACKAGES+=("appimage")
            shift
            ;;
        --snap)
            PACKAGES+=("snap")
            shift
            ;;
        --flatpak)
            PACKAGES+=("flatpak")
            shift
            ;;
        --npm)
            PACKAGES+=("npm")
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  --all        Build all available packages"
            echo "  --appimage   Build AppImage package"
            echo "  --snap       Build Snap package"
            echo "  --flatpak    Build Flatpak package"
            echo "  --npm        Build npm package"
            echo "  --help       Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# If no specific packages requested and not --all, show help
if [[ ${#PACKAGES[@]} -eq 0 && "$BUILD_ALL" == false ]]; then
    echo "No package type specified. Use --help for usage information"
    exit 1
fi

# If --all is specified, build all packages
if [[ "$BUILD_ALL" == true ]]; then
    PACKAGES=("appimage" "snap" "flatpak" "npm")
fi

# Build requested packages
for package in "${PACKAGES[@]}"; do
    echo "----------------------------------------"
    build_package "$package"
    echo "✓ ${package} package built successfully"
done

echo "----------------------------------------"
echo "All requested packages built successfully!"
echo "Built packages:"
for package in "${PACKAGES[@]}"; do
    echo "  - ${package}"
done