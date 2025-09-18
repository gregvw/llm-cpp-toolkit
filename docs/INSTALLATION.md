# Installation Guide

Comprehensive installation options for llm-cpp-toolkit across different platforms and use cases.

## 🎯 Choose Your Installation Method

### Quick Decision Matrix

| Scenario | Recommended Method | Command |
|----------|-------------------|---------|
| **First time user** | One-line script | `curl -sSL ...install.sh \| bash` |
| **No sudo access** | Local install | `llmtk install --local` |
| **CI/CD pipeline** | Docker or Nix | `nix develop` or `docker run` |
| **Team development** | Nix flake | `nix develop github:gregvw/...` |
| **Long-term use** | Package manager | `brew install llmtk` |

## 📦 Installation Methods

### 1. One-Line Script (Recommended for Getting Started)

The fastest way to get llmtk with automatic dependency management:

```bash
curl -sSL https://raw.githubusercontent.com/gregvw/llm-cpp-toolkit/main/install.sh | bash
```

**What it does:**
- Detects your package manager (apt/dnf/pacman/brew)
- Installs core tools via system packages
- Downloads and installs llmtk to `~/.local/share/llm-cpp-toolkit`
- Creates `~/.local/bin/llmtk` wrapper script

**Options:**
```bash
# Install without prompts
curl -sSL ...install.sh | bash -s -- --yes

# Custom installation directory
curl -sSL ...install.sh | bash -s -- --dir ~/tools/llmtk

# Skip system dependencies
curl -sSL ...install.sh | bash -s -- --no-deps
```

### 2. Local Installation (No sudo required)

Perfect for restricted environments:

```bash
git clone https://github.com/gregvw/llm-cpp-toolkit.git
cd llm-cpp-toolkit
python3 cli/llmtk install --local
export PATH="$(pwd)/.llmtk/bin:$PATH"
```

**Features:**
- Downloads pre-built binaries when available
- Falls back to building from source
- Installs tools in `.llmtk/bin/` directory
- No system modifications required

### 3. Package Managers

#### Homebrew (macOS/Linux)

```bash
# Add the tap
brew tap gregvw/llm-cpp-toolkit

# Install llmtk
brew install llmtk

# Verify installation
llmtk doctor
```

**Includes dependencies:**
- cmake, ninja, llvm (clang-tidy, clang-format)
- ripgrep, fd, jq, yq
- Optional: cppcheck, include-what-you-use, fzf, bat

#### Nix (Universal)

**Development shell (temporary):**
```bash
# Enter development environment
nix develop github:gregvw/llm-cpp-toolkit

# Use specific variant
nix develop github:gregvw/llm-cpp-toolkit#full     # All tools
nix develop github:gregvw/llm-cpp-toolkit#minimal  # Core only
nix develop github:gregvw/llm-cpp-toolkit#ci       # CI/automation
```

**Permanent installation:**
```bash
# Install to profile
nix profile install github:gregvw/llm-cpp-toolkit

# Or add to your system config
environment.systemPackages = [
  inputs.llm-cpp-toolkit.packages.${system}.default
];
```

**Features:**
- Reproducible, deterministic builds
- Multiple environment variants
- Automatic tool version pinning
- Works on any Linux distribution

### 4. Container-Based

#### Docker

**Quick analysis:**
```bash
docker run --rm -v $(pwd):/workspace \
  ghcr.io/gregvw/llm-cpp-toolkit:latest \
  analyze /workspace
```

**Development environment:**
```bash
# Build development image
cd llm-cpp-toolkit
docker build -t llmtk-dev --target=dev containers/

# Run interactive session
docker run -it --rm \
  -v $(pwd):/workspace \
  llmtk-dev
```

**Available tags:**
- `latest` - Production build with core tools
- `dev` - Development build with additional tools
- `minimal` - Minimal build for CI

#### Dev Containers (VS Code)

```bash
# Clone repository
git clone https://github.com/gregvw/llm-cpp-toolkit.git
cd llm-cpp-toolkit

# Open in VS Code
code .
# VS Code will prompt to reopen in container
```

**Includes:**
- Pre-configured C++ development environment
- All llmtk tools installed
- VS Code extensions for C++, Python, Git
- clangd integration with compile_commands.json

### 5. Manual Installation

For customization or platform-specific needs:

```bash
# Clone repository
git clone https://github.com/gregvw/llm-cpp-toolkit.git
cd llm-cpp-toolkit

# Run installer with options
./install.sh --prefix /opt/llmtk --no-deps

# Or install dependencies manually
sudo apt install cmake ninja-build clang-tools-extra bear ripgrep fd-find jq
python3 cli/llmtk install --local
```

## 🔧 Post-Installation Setup

### 1. Verify Installation
```bash
llmtk --version
llmtk doctor
```

### 2. Add to PATH (if needed)
```bash
# For script installation
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc

# For local installation
echo 'export PATH="/path/to/llm-cpp-toolkit/.llmtk/bin:$PATH"' >> ~/.bashrc

# Reload shell
source ~/.bashrc
```

### 3. Install Missing Tools
```bash
# Check what's missing
llmtk doctor

# Install missing tools
llmtk install             # Uses system package manager
llmtk install --local     # Local installation only
llmtk install cppcheck    # Install specific tool
```

## 🛠 Troubleshooting

### Common Issues

#### "Command not found: llmtk"
```bash
# Check if installed
which llmtk

# Add to PATH
export PATH="$HOME/.local/bin:$PATH"

# Make permanent
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
```

#### "Tool not found" in llmtk doctor
```bash
# Install missing tools locally
llmtk install --local

# Or install via system package manager
sudo apt install clang-tidy cppcheck include-what-you-use
```

#### Permission denied during installation
```bash
# Use local installation instead
llmtk install --local

# Or fix permissions
sudo chown -R $USER:$USER ~/.local/
```

#### Docker issues
```bash
# Check Docker is running
docker --version

# Pull latest image
docker pull ghcr.io/gregvw/llm-cpp-toolkit:latest

# Build locally if pull fails
cd llm-cpp-toolkit
docker build -t llmtk containers/
```

### Platform-Specific Notes

#### Ubuntu/Debian
```bash
# Install build dependencies first
sudo apt update
sudo apt install build-essential cmake git

# Some tools need newer versions
sudo apt install clang-18 clang-tools-18
sudo ln -sf clang-18 /usr/bin/clang
```

#### CentOS/RHEL/Fedora
```bash
# Install EPEL repository first (CentOS/RHEL)
sudo yum install epel-release

# Install dependencies
sudo dnf install cmake ninja-build clang-tools-extra bear
```

#### macOS
```bash
# Install Xcode command line tools
xcode-select --install

# Use Homebrew for best experience
brew install llmtk
```

#### Arch Linux
```bash
# Most tools available in official repos
sudo pacman -S cmake ninja clang bear ripgrep fd jq

# Some tools from AUR
yay -S cppcheck include-what-you-use
```

## 🎛 Configuration

### Environment Variables

```bash
export LLMTK_DIR=/custom/install/path     # Override install directory
export LLMTK_LOCAL_BIN=/custom/bin        # Override local bin directory
export LLMTK_CACHE_DIR=/custom/cache      # Override cache directory
```

### Tool Configuration

```bash
# Copy default configurations
cp -r llm-cpp-toolkit/presets/ ~/.config/llmtk/

# Use custom clang-tidy config
export LLMTK_CLANG_TIDY_CONFIG=~/.config/llmtk/.clang-tidy
```

## 🔄 Updates

### Script Installation
```bash
# Re-run installer
curl -sSL ...install.sh | bash
```

### Package Managers
```bash
# Homebrew
brew upgrade llmtk

# Nix
nix profile upgrade
```

### Manual Installation
```bash
cd llm-cpp-toolkit
git pull
./install.sh --yes
```

### Container Images
```bash
# Pull latest
docker pull ghcr.io/gregvw/llm-cpp-toolkit:latest

# Rebuild local
docker build -t llmtk containers/
```

## 🚀 Next Steps

After successful installation:

1. **Test basic functionality**: `llmtk doctor`
2. **Set up a project**: `llmtk context export`
3. **Run analysis**: `llmtk analyze`
4. **Read the quick start**: [QUICKSTART.md](../QUICKSTART.md)
5. **Explore examples**: Check `examples/` directory