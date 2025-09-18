#!/usr/bin/env bash
set -euo pipefail

# Build AppImage for llm-cpp-toolkit

VERSION=${VERSION:-$(cat ../VERSION)}
export VERSION

echo "Building AppImage for llm-cpp-toolkit v${VERSION}"

# Clean previous build
rm -rf AppDir || true

# Create AppDir structure
mkdir -p AppDir/usr/bin
mkdir -p AppDir/usr/share/llm-cpp-toolkit

# Copy the main scripts
cp ../cli/llmtk AppDir/usr/bin/llmtk
cp ../build_manager AppDir/usr/bin/build_manager
chmod +x AppDir/usr/bin/llmtk
chmod +x AppDir/usr/bin/build_manager

# Point ROOT inside the script to packaged share directory
sed -i "s|ROOT = pathlib.Path(__file__).resolve().parent.parent|ROOT = pathlib.Path('/usr/share/llm-cpp-toolkit')|" AppDir/usr/bin/llmtk

# Copy supporting files
cp -r ../modules AppDir/usr/share/llm-cpp-toolkit/
cp -r ../presets AppDir/usr/share/llm-cpp-toolkit/
cp -r ../manifest AppDir/usr/share/llm-cpp-toolkit/
cp ../VERSION AppDir/usr/share/llm-cpp-toolkit/

# Create desktop file
cat > AppDir/llmtk.desktop << EOF
[Desktop Entry]
Type=Application
Name=LLM C++ Toolkit
Comment=A comprehensive toolkit for working with LLM C++ implementations
Exec=llmtk
Icon=llmtk
Categories=Development;
Terminal=true
EOF

# Create simple icon (you should replace this with a real icon)
mkdir -p AppDir/usr/share/icons/hicolor/256x256/apps
cat > AppDir/usr/share/icons/hicolor/256x256/apps/llmtk.svg << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">
  <rect width="256" height="256" fill="#2E86AB"/>
  <text x="128" y="140" font-family="monospace" font-size="48" fill="white" text-anchor="middle">LLM</text>
  <text x="128" y="180" font-family="monospace" font-size="24" fill="white" text-anchor="middle">C++</text>
</svg>
EOF

# Download and install appimage-builder if not present
if ! command -v appimage-builder &> /dev/null; then
    echo "Installing appimage-builder..."
    pip3 install --user appimage-builder
fi

# Build the AppImage
appimage-builder --recipe AppImageBuilder.yml

echo "AppImage built successfully!"
ls -la *.AppImage
