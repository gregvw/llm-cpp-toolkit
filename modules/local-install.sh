#!/usr/bin/env bash
set -euo pipefail

# Local installation script for tools without sudo requirements
# Downloads pre-built binaries when possible, falls back to building from source

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCAL_BIN="$ROOT_DIR/.llmtk/bin"
LOCAL_TMP="$ROOT_DIR/.llmtk/tmp"

mkdir -p "$LOCAL_BIN" "$LOCAL_TMP"

# Detect OS and architecture
OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
ARCH="$(uname -m)"
case "$ARCH" in
    x86_64) ARCH="x86_64" ;;
    arm64|aarch64) ARCH="aarch64" ;;
    *) echo "Unsupported architecture: $ARCH" >&2; exit 1 ;;
esac

have() { command -v "$1" >/dev/null 2>&1; }

log() { echo "[local-install] $*" >&2; }

# Download a file with fallback methods
download() {
    local url="$1" output="$2"
    if have curl; then
        curl -fsSL "$url" -o "$output"
    elif have wget; then
        wget -q "$url" -O "$output"
    else
        log "Error: Need curl or wget to download files"
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

# Install include-what-you-use from pre-built releases
install_iwyu() {
    local tool="iwyu"
    if [[ -f "$LOCAL_BIN/include-what-you-use" && -f "$LOCAL_BIN/iwyu_tool.py" ]]; then
        log "$tool already installed locally"
        return 0
    fi

    log "Installing $tool locally..."
    local tmp_dir="$LOCAL_TMP/$tool"
    rm -rf "$tmp_dir"
    mkdir -p "$tmp_dir"

    # Try to find a pre-built release
    local base_url=""
    if [[ "$OS" == "linux" && "$ARCH" == "x86_64" ]]; then
        # Use Ubuntu/Debian packages if available
        if have dpkg && have apt-cache; then
            local pkg_url=$(apt-cache show iwyu 2>/dev/null | grep -E '^Filename:' | head -1 | cut -d' ' -f2)
            if [[ -n "$pkg_url" ]]; then
                base_url="http://archive.ubuntu.com/ubuntu/$pkg_url"
            fi
        fi
    fi

    if [[ -z "$base_url" ]]; then
        # Build from source as fallback
        log "Building iwyu from source..."
        install_iwyu_from_source
        return
    fi

    download "$base_url" "$tmp_dir/iwyu.deb"
    cd "$tmp_dir"
    ar x iwyu.deb
    tar -xzf data.tar.gz

    # Copy binaries to local bin
    find . -name "include-what-you-use" -type f -executable -exec cp {} "$LOCAL_BIN/" \;
    find . -name "iwyu_tool.py" -type f -exec cp {} "$LOCAL_BIN/" \;
    chmod +x "$LOCAL_BIN/include-what-you-use" "$LOCAL_BIN/iwyu_tool.py" 2>/dev/null || true

    # Create iwyu_tool symlink without .py
    ln -sf iwyu_tool.py "$LOCAL_BIN/iwyu_tool"

    log "$tool installed successfully"
}

install_iwyu_from_source() {
    log "Building iwyu from source (requires clang development headers)..."
    local tmp_dir="$LOCAL_TMP/iwyu-source"
    rm -rf "$tmp_dir"

    if ! have git; then
        log "Error: git required to build iwyu from source"
        return 1
    fi

    if ! have clang++; then
        log "Error: clang++ required to build iwyu from source"
        return 1
    fi

    # Clone IWYU repository
    git clone --depth=1 https://github.com/include-what-you-use/include-what-you-use.git "$tmp_dir"
    cd "$tmp_dir"

    # Try to find clang installation
    local clang_version=$(clang --version | head -1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
    local llvm_config=""
    for candidate in llvm-config-{18,17,16,15,14} llvm-config; do
        if have "$candidate"; then
            llvm_config="$candidate"
            break
        fi
    done

    if [[ -z "$llvm_config" ]]; then
        log "Error: llvm-config not found. Install llvm-dev or clang-tools-extra"
        return 1
    fi

    # Build with cmake if available, otherwise try simple make
    if have cmake && have make; then
        mkdir -p build
        cd build
        cmake .. -DCMAKE_INSTALL_PREFIX="$ROOT_DIR/.llmtk" -DCMAKE_BUILD_TYPE=Release
        make -j$(nproc 2>/dev/null || echo 2)
        cp bin/include-what-you-use "$LOCAL_BIN/"
        cp ../iwyu_tool.py "$LOCAL_BIN/"
    else
        log "Error: cmake and make required to build iwyu from source"
        return 1
    fi

    chmod +x "$LOCAL_BIN/include-what-you-use" "$LOCAL_BIN/iwyu_tool.py"
    ln -sf iwyu_tool.py "$LOCAL_BIN/iwyu_tool"

    log "iwyu built from source successfully"
}

# Install cppcheck from pre-built releases
install_cppcheck() {
    local tool="cppcheck"
    if [[ -f "$LOCAL_BIN/cppcheck" ]]; then
        log "$tool already installed locally"
        return 0
    fi

    log "Installing $tool locally..."
    local tmp_dir="$LOCAL_TMP/$tool"
    rm -rf "$tmp_dir"
    mkdir -p "$tmp_dir"

    # Try GitHub releases first
    local latest_url="https://api.github.com/repos/danmar/cppcheck/releases/latest"
    local release_info=""

    if have curl; then
        release_info=$(curl -fsSL "$latest_url" 2>/dev/null || echo "")
    elif have wget; then
        release_info=$(wget -qO- "$latest_url" 2>/dev/null || echo "")
    fi

    # Look for pre-built binary
    local download_url=""
    if [[ -n "$release_info" ]]; then
        case "$OS-$ARCH" in
            linux-x86_64)
                download_url=$(echo "$release_info" | grep -oE '"browser_download_url"[^"]*"[^"]*linux[^"]*\.tar\.gz"' | cut -d'"' -f4 | head -1)
                ;;
        esac
    fi

    if [[ -n "$download_url" ]]; then
        log "Downloading pre-built $tool from GitHub releases..."
        download "$download_url" "$tmp_dir/cppcheck.tar.gz"
        extract "$tmp_dir/cppcheck.tar.gz" "$tmp_dir/extracted"

        # Find and copy the cppcheck binary
        find "$tmp_dir/extracted" -name "cppcheck" -type f -executable -exec cp {} "$LOCAL_BIN/" \;

        if [[ -f "$LOCAL_BIN/cppcheck" ]]; then
            chmod +x "$LOCAL_BIN/cppcheck"
            log "$tool installed successfully"
            return 0
        fi
    fi

    # Fallback to building from source
    log "Building $tool from source..."
    install_cppcheck_from_source
}

install_cppcheck_from_source() {
    log "Building cppcheck from source..."
    local tmp_dir="$LOCAL_TMP/cppcheck-source"
    rm -rf "$tmp_dir"

    if ! have git; then
        log "Error: git required to build cppcheck from source"
        return 1
    fi

    if ! have make; then
        log "Error: make required to build cppcheck from source"
        return 1
    fi

    # Clone repository
    git clone --depth=1 https://github.com/danmar/cppcheck.git "$tmp_dir"
    cd "$tmp_dir"

    # Build
    make -j$(nproc 2>/dev/null || echo 2) FILESDIR="$ROOT_DIR/.llmtk/share/cppcheck"

    # Install
    mkdir -p "$ROOT_DIR/.llmtk/share/cppcheck"
    cp cppcheck "$LOCAL_BIN/"
    cp -r cfg "$ROOT_DIR/.llmtk/share/cppcheck/" 2>/dev/null || true

    chmod +x "$LOCAL_BIN/cppcheck"
    log "cppcheck built from source successfully"
}

# Install all missing tools
install_missing_tools() {
    log "Checking and installing missing analysis tools..."

    # Update PATH to include local bin
    export PATH="$LOCAL_BIN:$PATH"

    # Install tools if missing
    if ! have include-what-you-use && ! have iwyu_tool; then
        install_iwyu || log "Failed to install iwyu"
    fi

    if ! have cppcheck; then
        install_cppcheck || log "Failed to install cppcheck"
    fi

    log "Local installation complete."
    log "Add to your PATH: export PATH=\"$LOCAL_BIN:\$PATH\""

    # Show what was installed
    log "Locally installed tools:"
    for tool in include-what-you-use iwyu_tool iwyu_tool.py cppcheck; do
        if [[ -f "$LOCAL_BIN/$tool" ]]; then
            log "  ✓ $tool ($("$LOCAL_BIN/$tool" --version 2>/dev/null | head -1 || echo 'installed'))"
        fi
    done
}

# Main execution
case "${1:-install}" in
    install) install_missing_tools ;;
    iwyu) install_iwyu ;;
    cppcheck) install_cppcheck ;;
    *) log "Usage: $0 {install|iwyu|cppcheck}"; exit 1 ;;
esac