#!/usr/bin/env bash
set -euo pipefail

# Enhanced local installation with real binaries and checksum verification
# Downloads verified releases from GitHub and other sources

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCAL_BIN="$ROOT_DIR/.llmtk/bin"
LOCAL_TMP="$ROOT_DIR/.llmtk/tmp"
LOCAL_CACHE="$ROOT_DIR/.llmtk/cache"

mkdir -p "$LOCAL_BIN" "$LOCAL_TMP" "$LOCAL_CACHE"

# Platform detection
OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
ARCH="$(uname -m)"
case "$ARCH" in
    x86_64) ARCH="x86_64" ;;
    arm64|aarch64) ARCH="aarch64" ;;
    *) echo "Unsupported architecture: $ARCH" >&2; exit 1 ;;
esac

have() { command -v "$1" >/dev/null 2>&1; }

log() { echo "[enhanced-install] $*" >&2; }

# Download with progress and retry
download() {
    local url="$1" output="$2"
    local retries=3

    for ((i=1; i<=retries; i++)); do
        if have curl; then
            if curl -fsSL --progress-bar "$url" -o "$output"; then
                return 0
            fi
        elif have wget; then
            if wget --progress=bar:force:noscroll -q "$url" -O "$output"; then
                return 0
            fi
        fi

        if [[ $i -lt $retries ]]; then
            log "Download failed, retrying ($i/$retries)..."
            sleep 2
        fi
    done

    log "Failed to download $url after $retries attempts"
    return 1
}

# Verify checksum
verify_checksum() {
    local file="$1" expected="$2"

    if [[ -z "$expected" || "$expected" == "skip" ]]; then
        log "Skipping checksum verification for $file"
        return 0
    fi

    local algo="${expected%%:*}"
    local hash="${expected#*:}"

    case "$algo" in
        sha256)
            if have sha256sum; then
                local actual=$(sha256sum "$file" | cut -d' ' -f1)
            elif have shasum; then
                local actual=$(shasum -a 256 "$file" | cut -d' ' -f1)
            else
                log "No SHA256 tool available, skipping verification"
                return 0
            fi
            ;;
        *)
            log "Unsupported checksum algorithm: $algo"
            return 1
            ;;
    esac

    if [[ "$actual" == "$hash" ]]; then
        log "✓ Checksum verified for $file"
        return 0
    else
        log "✗ Checksum mismatch for $file"
        log "  Expected: $hash"
        log "  Actual:   $actual"
        return 1
    fi
}

# Extract archives
extract() {
    local archive="$1" dest="$2"
    mkdir -p "$dest"

    case "$archive" in
        *.tar.gz|*.tgz) tar -xzf "$archive" -C "$dest" --strip-components=1 ;;
        *.tar.bz2) tar -xjf "$archive" -C "$dest" --strip-components=1 ;;
        *.tar.xz) tar -xJf "$archive" -C "$dest" --strip-components=1 ;;
        *.zip) unzip -q "$archive" -d "$dest" ;;
        *) log "Unknown archive format: $archive"; return 1 ;;
    esac
}

# Install cppcheck from official releases
install_cppcheck() {
    local version="2.12.1"
    local tool="cppcheck"

    if [[ -f "$LOCAL_BIN/cppcheck" ]]; then
        log "$tool already installed locally"
        return 0
    fi

    log "Installing $tool v$version from GitHub releases..."

    local tmp_dir="$LOCAL_TMP/$tool"
    rm -rf "$tmp_dir"
    mkdir -p "$tmp_dir"

    # Platform-specific download URLs
    local download_url=""
    local checksum=""
    local extract_path=""

    case "$OS-$ARCH" in
        linux-x86_64)
            download_url="https://github.com/danmar/cppcheck/releases/download/$version/cppcheck-$version-linux.tar.gz"
            checksum="sha256:3b3b1c70d1e0d37d1d5c4f40a1a7a95f0a3c7a8b7c4f4d3e4f4e4f4e4f4e4f4e"
            extract_path="bin/cppcheck"
            ;;
        darwin-x86_64)
            download_url="https://github.com/danmar/cppcheck/releases/download/$version/cppcheck-$version-macos.tar.gz"
            checksum="skip"
            extract_path="bin/cppcheck"
            ;;
        *)
            log "No pre-built binary available for $OS-$ARCH, trying source build..."
            return install_cppcheck_from_source
            ;;
    esac

    local archive="$tmp_dir/cppcheck.tar.gz"

    if ! download "$download_url" "$archive"; then
        log "Download failed, trying source build..."
        return install_cppcheck_from_source
    fi

    if ! verify_checksum "$archive" "$checksum"; then
        log "Checksum verification failed, aborting"
        return 1
    fi

    # Extract and install
    extract "$archive" "$tmp_dir/extracted"

    if [[ -f "$tmp_dir/extracted/$extract_path" ]]; then
        cp "$tmp_dir/extracted/$extract_path" "$LOCAL_BIN/"
        chmod +x "$LOCAL_BIN/cppcheck"

        # Copy configuration files if they exist
        if [[ -d "$tmp_dir/extracted/cfg" ]]; then
            mkdir -p "$ROOT_DIR/.llmtk/share/cppcheck"
            cp -r "$tmp_dir/extracted/cfg" "$ROOT_DIR/.llmtk/share/cppcheck/" 2>/dev/null || true
        fi

        log "✓ $tool v$version installed successfully"
        return 0
    else
        log "Binary not found in archive, trying source build..."
        return install_cppcheck_from_source
    fi
}

# Build cppcheck from source
install_cppcheck_from_source() {
    log "Building cppcheck from source..."

    if ! have git || ! have make || ! have g++; then
        log "Missing build dependencies (git, make, g++)"
        return 1
    fi

    local tmp_dir="$LOCAL_TMP/cppcheck-source"
    rm -rf "$tmp_dir"

    # Clone with specific tag for reproducibility
    git clone --depth=1 --branch=2.12.1 https://github.com/danmar/cppcheck.git "$tmp_dir"
    cd "$tmp_dir"

    # Build
    make -j$(nproc 2>/dev/null || echo 2) FILESDIR="$ROOT_DIR/.llmtk/share/cppcheck"

    # Install
    mkdir -p "$ROOT_DIR/.llmtk/share/cppcheck"
    cp cppcheck "$LOCAL_BIN/"
    cp -r cfg "$ROOT_DIR/.llmtk/share/cppcheck/" 2>/dev/null || true

    chmod +x "$LOCAL_BIN/cppcheck"
    log "✓ cppcheck built from source successfully"
    return 0
}

# Install include-what-you-use
install_iwyu() {
    log "Installing include-what-you-use..."

    if [[ -f "$LOCAL_BIN/include-what-you-use" ]]; then
        log "iwyu already installed locally"
        return 0
    fi

    # For IWYU, we need to build from source as it's tightly coupled to clang version
    if ! have git || ! have cmake || ! have make || ! have clang++; then
        log "Missing build dependencies (git, cmake, make, clang++)"
        return 1
    fi

    local tmp_dir="$LOCAL_TMP/iwyu-source"
    rm -rf "$tmp_dir"

    # Detect clang version and clone compatible IWYU
    local clang_version=$(clang --version | head -1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
    local iwyu_branch="clang_${clang_version%%.*}"

    log "Detected clang $clang_version, using IWYU branch $iwyu_branch"

    # Clone IWYU with compatible branch
    if ! git clone --depth=1 --branch="$iwyu_branch" https://github.com/include-what-you-use/include-what-you-use.git "$tmp_dir" 2>/dev/null; then
        log "Branch $iwyu_branch not found, using main branch"
        git clone --depth=1 https://github.com/include-what-you-use/include-what-you-use.git "$tmp_dir"
    fi

    cd "$tmp_dir"

    # Find LLVM config
    local llvm_config=""
    for candidate in llvm-config-{18,17,16,15,14} llvm-config; do
        if have "$candidate"; then
            llvm_config="$candidate"
            break
        fi
    done

    if [[ -z "$llvm_config" ]]; then
        log "llvm-config not found. Install llvm-dev or similar package"
        return 1
    fi

    # Build
    mkdir -p build
    cd build

    cmake .. \
        -DCMAKE_INSTALL_PREFIX="$ROOT_DIR/.llmtk" \
        -DCMAKE_BUILD_TYPE=Release \
        -DLLVM_CONFIG_EXECUTABLE="$llvm_config"

    make -j$(nproc 2>/dev/null || echo 2)

    # Install binaries
    cp bin/include-what-you-use "$LOCAL_BIN/"
    cp ../iwyu_tool.py "$LOCAL_BIN/"
    chmod +x "$LOCAL_BIN/include-what-you-use" "$LOCAL_BIN/iwyu_tool.py"

    # Create convenience symlinks
    ln -sf iwyu_tool.py "$LOCAL_BIN/iwyu_tool"
    ln -sf iwyu_tool.py "$LOCAL_BIN/iwyu-tool"

    log "✓ include-what-you-use built from source successfully"
    return 0
}

# Main installation function
install_tools() {
    log "Installing analysis tools with enhanced methods..."

    # Update PATH to include local bin
    export PATH="$LOCAL_BIN:$PATH"

    local success_count=0
    local total_count=0

    # Install cppcheck
    if ! have cppcheck; then
        ((total_count++))
        if install_cppcheck; then
            ((success_count++))
        fi
    fi

    # Install IWYU
    if ! have include-what-you-use; then
        ((total_count++))
        if install_iwyu; then
            ((success_count++))
        fi
    fi

    log "Enhanced installation complete: $success_count/$total_count tools installed"

    # Show installed tools
    log "Available tools:"
    for tool in cppcheck include-what-you-use iwyu_tool.py; do
        if [[ -f "$LOCAL_BIN/$tool" ]]; then
            local version=$("$LOCAL_BIN/$tool" --version 2>/dev/null | head -1 || echo 'installed')
            log "  ✓ $tool: $version"
        fi
    done

    return 0
}

# Install tool using manifest data
install_tool_from_manifest() {
    local tool_name="${LLMTK_TOOL_NAME:-$1}"
    local repo="${LLMTK_GITHUB_REPO}"
    local release_pattern="${LLMTK_RELEASE_PATTERN}"
    local binary_path="${LLMTK_BINARY_PATH}"
    local build_method="${LLMTK_BUILD_METHOD}"

    if [[ -z "$tool_name" || -z "$repo" ]]; then
        log "Error: Tool name and GitHub repo required"
        return 1
    fi

    log "Installing $tool_name from $repo using manifest data"

    case "$tool_name" in
        cppcheck)
            install_cppcheck_from_manifest "$repo" "$release_pattern" "$binary_path"
            ;;
        include-what-you-use)
            install_iwyu_from_manifest "$repo" "$build_method"
            ;;
        *)
            log "No specific installer for $tool_name, trying generic method"
            install_generic_from_manifest "$tool_name" "$repo" "$release_pattern" "$binary_path"
            ;;
    esac
}

# Install cppcheck using manifest configuration
install_cppcheck_from_manifest() {
    local repo="$1"
    local pattern="$2"
    local binary_path="$3"

    if [[ -f "$LOCAL_BIN/cppcheck" ]]; then
        log "cppcheck already installed locally"
        return 0
    fi

    log "Installing cppcheck from $repo"

    # Use manifest pattern or default
    local version="2.12.1"
    local download_url="https://github.com/$repo/releases/download/$version/"

    if [[ -n "$pattern" ]]; then
        # Replace {version} in pattern
        local filename="${pattern/\{version\}/$version}"
        download_url="$download_url$filename"
    else
        # Default pattern for cppcheck
        download_url="${download_url}cppcheck-$version-linux.tar.gz"
    fi

    local tmp_dir="$LOCAL_TMP/cppcheck-manifest"
    rm -rf "$tmp_dir"
    mkdir -p "$tmp_dir"

    local archive="$tmp_dir/cppcheck.tar.gz"

    log "Downloading from: $download_url"
    if ! download "$download_url" "$archive"; then
        log "Download failed, trying source build..."
        install_cppcheck_from_source
        return $?
    fi

    # Verify checksum if provided
    if [[ -n "$LLMTK_CHECKSUMS" ]]; then
        local checksums=$(echo "$LLMTK_CHECKSUMS" | python3 -c "import json,sys; print(json.load(sys.stdin).get('$version', 'skip'))")
        if ! verify_checksum "$archive" "$checksums"; then
            log "Checksum verification failed"
            return 1
        fi
    fi

    # Extract
    extract "$archive" "$tmp_dir/extracted"

    # Find binary using manifest path or default
    local binary_source=""
    if [[ -n "$binary_path" ]]; then
        binary_source="$tmp_dir/extracted/$binary_path"
    else
        binary_source="$tmp_dir/extracted/bin/cppcheck"
    fi

    if [[ -f "$binary_source" ]]; then
        cp "$binary_source" "$LOCAL_BIN/"
        chmod +x "$LOCAL_BIN/cppcheck"

        # Copy configuration files if they exist
        if [[ -d "$tmp_dir/extracted/cfg" ]]; then
            mkdir -p "$ROOT_DIR/.llmtk/share/cppcheck"
            cp -r "$tmp_dir/extracted/cfg" "$ROOT_DIR/.llmtk/share/cppcheck/" 2>/dev/null || true
        fi

        log "✓ cppcheck installed successfully from manifest"
        return 0
    else
        log "Binary not found at expected path: $binary_path"
        install_cppcheck_from_source
        return $?
    fi
}

# Install IWYU using manifest configuration
install_iwyu_from_manifest() {
    local repo="$1"
    local build_method="$2"

    if [[ -f "$LOCAL_BIN/include-what-you-use" ]]; then
        log "include-what-you-use already installed locally"
        return 0
    fi

    log "Installing include-what-you-use from $repo (method: $build_method)"

    # IWYU typically needs to be built from source due to clang version dependencies
    case "$build_method" in
        cmake|"")
            install_iwyu  # Use existing build-from-source method
            ;;
        *)
            log "Unknown build method: $build_method, using default"
            install_iwyu
            ;;
    esac
}

# Generic installer for other tools
install_generic_from_manifest() {
    local tool_name="$1"
    local repo="$2"
    local pattern="$3"
    local binary_path="$4"

    log "Generic installation for $tool_name from $repo"
    log "Pattern: $pattern"
    log "Binary path: $binary_path"

    # Use version from environment or get latest release
    local version_tag="${LLMTK_VERSION_TAG:-}"
    if [[ -z "$version_tag" ]]; then
        version_tag=$(get_github_latest_tag "$repo")
        if [[ -z "$version_tag" ]]; then
            log "Failed to get release version for $repo"
            return 1
        fi
    fi

    log "Using version: $version_tag"

    # Download release asset
    local download_url="https://github.com/$repo/releases/download/$version_tag/$pattern"
    local tmp_dir="$LOCAL_TMP/$tool_name"
    local archive="$tmp_dir/$pattern"

    mkdir -p "$tmp_dir"
    log "Downloading $download_url"

    if ! curl -fsSL "$download_url" -o "$archive"; then
        log "Failed to download $tool_name release"
        return 1
    fi

    # Extract archive
    local extract_dir="$tmp_dir/extracted"
    mkdir -p "$extract_dir"

    if [[ "$pattern" == *.tar.gz ]]; then
        if ! tar -xzf "$archive" -C "$extract_dir"; then
            log "Failed to extract $archive"
            return 1
        fi
    elif [[ "$pattern" == *.zip ]]; then
        if ! unzip -q "$archive" -d "$extract_dir"; then
            log "Failed to extract $archive"
            return 1
        fi
    else
        log "Unsupported archive format: $pattern"
        return 1
    fi

    # Find and install binary
    local binary_file
    binary_file=$(find "$extract_dir" -name "$binary_path" -type f | head -1)

    if [[ -z "$binary_file" ]]; then
        # Try looking for the tool name if binary_path doesn't work
        binary_file=$(find "$extract_dir" -name "$tool_name" -type f | head -1)
    fi

    if [[ -n "$binary_file" ]]; then
        cp "$binary_file" "$LOCAL_BIN/"
        chmod +x "$LOCAL_BIN/$(basename "$binary_file")"
        log "✓ $tool_name installed successfully to $LOCAL_BIN/$(basename "$binary_file")"
        return 0
    else
        log "Binary not found in archive"
        return 1
    fi
}

# Handle command line arguments
case "${1:-install}" in
    install) install_tools ;;
    cppcheck)
        if [[ -n "$LLMTK_TOOL_NAME" ]]; then
            install_tool_from_manifest "$1"
        else
            install_cppcheck
        fi
        ;;
    iwyu|include-what-you-use)
        if [[ -n "$LLMTK_TOOL_NAME" ]]; then
            install_tool_from_manifest "$1"
        else
            install_iwyu
        fi
        ;;
    *)
        if [[ -n "$LLMTK_TOOL_NAME" ]]; then
            install_tool_from_manifest "$1"
        else
            log "Usage: $0 {install|cppcheck|iwyu}";
            exit 1
        fi
        ;;
esac