#!/usr/bin/env bash
set -euo pipefail

# LLM C++ Toolkit one-line installer
# Usage: curl -sSL https://raw.githubusercontent.com/gregvw/llm-cpp-toolkit/main/install.sh | bash -s -- [--yes] [--prefix ~/.local] [--dir ~/.local/share/llm-cpp-toolkit] [--no-deps]

PREFIX=${PREFIX:-"$HOME/.local"}
INSTALL_DIR=${INSTALL_DIR:-"$HOME/.local/share/llm-cpp-toolkit"}
BRANCH=${BRANCH:-"main"}
AUTO_YES=false
INSTALL_DEPS=true

while [[ $# -gt 0 ]]; do
  case "$1" in
    --yes|-y) AUTO_YES=true; shift ;;
    --prefix) PREFIX="$2"; shift 2 ;;
    --dir) INSTALL_DIR="$2"; shift 2 ;;
    --branch) BRANCH="$2"; shift 2 ;;
    --no-deps) INSTALL_DEPS=false; shift ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

BIN_DIR="$PREFIX/bin"
WRAPPER="$BIN_DIR/llmtk"

have() { command -v "$1" >/dev/null 2>&1; }

detect_pm() {
  if have apt-get; then echo apt; return; fi
  if have dnf; then echo dnf; return; fi
  if have pacman; then echo pacman; return; fi
  if have brew; then echo brew; return; fi
  echo none
}

pm_install() {
  local pm=$1; shift
  case "$pm" in
    apt)
      sudo apt-get update -y && sudo apt-get install -y "$@" ;;
    dnf)
      sudo dnf install -y "$@" ;;
    pacman)
      sudo pacman -Syu --noconfirm "$@" ;;
    brew)
      brew install "$@" ;;
    *) return 1 ;;
  esac
}

ensure_tool() {
  local cmd="$1"; shift
  local pm="$1"; shift
  local -a candidates=("$@")
  if have "$cmd"; then return 0; fi
  [[ "$INSTALL_DEPS" == true ]] || return 0
  for pkg in "${candidates[@]}"; do
    echo "[install] $cmd via $pm: $pkg" >&2
    if pm_install "$pm" "$pkg"; then
      if have "$cmd"; then return 0; fi
    fi
  done
  return 1
}

install_deps() {
  local pm=$(detect_pm)
  if [[ "$pm" == none ]]; then
    echo "[warn] No supported package manager found (apt/dnf/pacman/brew). Skipping deps." >&2
    return 0
  fi
  echo "[info] Using package manager: $pm" >&2

  # Core
  ensure_tool cmake "$pm" cmake || true
  ensure_tool ninja "$pm" ninja-build ninja || true
  ensure_tool bear "$pm" bear || true
  ensure_tool clangd "$pm" clangd-18 clangd clang-tools-extra llvm llvm@18 || true
  ensure_tool clang-format "$pm" clang-format-18 clang-format clang-tools-extra llvm llvm@18 || true
  ensure_tool clang-tidy "$pm" clang-tidy-18 clang-tidy clang-tools-extra llvm llvm@18 || true
  ensure_tool rg "$pm" ripgrep || true
  ensure_tool fd "$pm" fd-find fd || true
  ensure_tool jq "$pm" jq || true
  ensure_tool yq "$pm" yq python3-yq || true
  ensure_tool ccache "$pm" ccache || true
  ensure_tool mold "$pm" mold lld || true

  # Recommended
  ensure_tool include-what-you-use "$pm" include-what-you-use iwyu || true
  ensure_tool iwyu-tool "$pm" iwyu iwyu-tool include-what-you-use || true
  ensure_tool cppcheck "$pm" cppcheck || true
  ensure_tool ctags "$pm" universal-ctags ctags || true
  ensure_tool fzf "$pm" fzf || true
  ensure_tool zoxide "$pm" zoxide || true
  ensure_tool bat "$pm" bat || true
  ensure_tool tokei "$pm" tokei || true
  ensure_tool hyperfine "$pm" hyperfine || true
  ensure_tool entr "$pm" entr watchexec || true
  ensure_tool pre-commit "$pm" pre-commit || true
}

confirm() {
  $AUTO_YES && return 0
  read -r -p "$1 [y/N] " ans
  [[ "$ans" == y || "$ans" == Y ]]
}

fetch_repo() {
  mkdir -p "$INSTALL_DIR"
  if [[ -d "$INSTALL_DIR/.git" ]] && have git; then
    echo "[info] Updating repo in $INSTALL_DIR" >&2
    git -C "$INSTALL_DIR" fetch --depth=1 origin "$BRANCH" && git -C "$INSTALL_DIR" reset --hard FETCH_HEAD
    return 0
  fi
  if [[ -d "$INSTALL_DIR" && -n "$(ls -A "$INSTALL_DIR" 2>/dev/null || true)" ]]; then
    echo "[warn] $INSTALL_DIR exists and is not empty. Skipping fetch." >&2
    return 0
  fi
  if have git; then
    echo "[info] Cloning repo to $INSTALL_DIR" >&2
    git clone --depth=1 --branch "$BRANCH" https://github.com/gregvw/llm-cpp-toolkit "$INSTALL_DIR"
  else
    echo "[info] Downloading tarball to $INSTALL_DIR" >&2
    curl -sSL "https://codeload.github.com/gregvw/llm-cpp-toolkit/tar.gz/refs/heads/$BRANCH" | tar -xz -C "$(dirname "$INSTALL_DIR")"
    mv "$(dirname "$INSTALL_DIR")/llm-cpp-toolkit-$BRANCH" "$INSTALL_DIR"
  fi
}

install_wrapper() {
  mkdir -p "$BIN_DIR"
  cat > "$WRAPPER" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR=${LLMTK_DIR:-"$HOME/.local/share/llm-cpp-toolkit"}
exec python3 "$ROOT_DIR/cli/llmtk" "$@"
EOF
  chmod +x "$WRAPPER"
  echo "[info] Installed wrapper at $WRAPPER" >&2
  case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *) echo "[warn] $BIN_DIR not in PATH. Add: export PATH=\"$BIN_DIR:\$PATH\"" >&2 ;;
  esac
}

main() {
  echo "[llmtk] Installing to $INSTALL_DIR with prefix $PREFIX" >&2
  if $INSTALL_DEPS; then
    if confirm "Install core/recommended dependencies via package manager?"; then
      install_deps || true
    else
      echo "[info] Skipping dependency installation" >&2
    fi
  fi
  fetch_repo
  install_wrapper
  echo "$WRAPPER"
}

main "$@"

