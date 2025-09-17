# Distribution Guide

This document explains how to build and distribute the LLM C++ Toolkit across different package managers and platforms.

## Available Distribution Methods

### 1. npm (Node Package Manager)
**Best for:** JavaScript/Node.js developers, cross-platform CLI installation

```bash
# Install globally
npm install -g llm-cpp-toolkit

# Use directly
npx llm-cpp-toolkit
```

**Building:**
```bash
npm pack
# Or use the unified script
./build-packages.sh --npm
```

### 2. AppImage (Linux)
**Best for:** Linux users wanting portable, self-contained applications

```bash
# Download and run
chmod +x llm-cpp-toolkit-*.AppImage
./llm-cpp-toolkit-*.AppImage
```

**Building:**
```bash
cd appimage && ./build-appimage.sh
# Or use the unified script
./build-packages.sh --appimage
```

### 3. Snap (Linux)
**Best for:** Ubuntu and Snap-enabled Linux distributions

```bash
# Install from Snap Store (when published)
sudo snap install llm-cpp-toolkit

# Install local build
sudo snap install --dangerous *.snap
```

**Building:**
```bash
cd snap && ./build-snap.sh
# Or use the unified script
./build-packages.sh --snap
```

### 4. Flatpak (Linux)
**Best for:** Sandboxed applications on Linux

```bash
# Install from Flathub (when published)
flatpak install flathub io.github.gregvw.llm-cpp-toolkit

# Install local build
flatpak install --user repo io.github.gregvw.llm-cpp-toolkit
```

**Building:**
```bash
cd flatpak && ./build-flatpak.sh
# Or use the unified script
./build-packages.sh --flatpak
```

### 5. Homebrew (macOS/Linux)
**Best for:** macOS users and Linux users preferring Homebrew

```bash
# Add tap and install (when published)
brew tap gregvw/llm-cpp-toolkit
brew install llm-cpp-toolkit
```

**Setting up:**
1. Create a `homebrew-llm-cpp-toolkit` repository
2. Copy `homebrew/llm-cpp-toolkit.rb` to `Formula/llm-cpp-toolkit.rb`
3. Update SHA256 hash for releases

## Building All Packages

Use the unified build script to build all or specific packages:

```bash
# Build all packages
./build-packages.sh --all

# Build specific packages
./build-packages.sh --npm --appimage

# Show help
./build-packages.sh --help
```

## Release Process

### Automated (Recommended)

1. Create a new release on GitHub
2. GitHub Actions will automatically build all packages
3. Packages will be uploaded as release assets
4. npm package will be published automatically

### Manual

1. Update the version in `VERSION` file
2. Run `./build-packages.sh --all`
3. Upload packages to respective distribution channels

## Distribution Channels

### npm
- **Registry:** https://www.npmjs.com/
- **Package:** llm-cpp-toolkit
- **Automated:** Yes (via GitHub Actions)

### Snap Store
- **Store:** https://snapcraft.io/
- **Package ID:** llm-cpp-toolkit
- **Automated:** No (manual upload required)

### Flathub
- **Store:** https://flathub.org/
- **App ID:** io.github.gregvw.llm-cpp-toolkit
- **Automated:** No (PR to flathub required)

### Homebrew
- **Tap:** gregvw/llm-cpp-toolkit
- **Formula:** llm-cpp-toolkit
- **Automated:** No (manual tap maintenance)

## Requirements by Platform

### AppImage
- Linux system with AppImage support
- Python 3.8+
- appimage-builder (`pip install appimage-builder`)

### Snap
- Linux system with snapd
- snapcraft (`snap install snapcraft --classic`)

### Flatpak
- Linux system with Flatpak
- flatpak-builder
- Flatpak runtimes (org.freedesktop.Platform//23.08)

### npm
- Node.js 14+
- npm or yarn

### Homebrew
- macOS or Linux with Homebrew
- Python 3.8+

## Testing Packages

Each package type includes test scripts:

```bash
# Test AppImage
./llm-cpp-toolkit-*.AppImage --version

# Test Snap
llmtk --version

# Test Flatpak
flatpak run io.github.gregvw.llm-cpp-toolkit --version

# Test npm
npx llm-cpp-toolkit --version

# Test Homebrew
llmtk --version
```