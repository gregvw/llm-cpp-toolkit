# Quick Start Guide

Get up and running with llm-cpp-toolkit in minutes.

## 🚀 Installation

Choose the method that works best for your environment:

### 1. One-line Install (Recommended)
```bash
curl -sSL https://raw.githubusercontent.com/gregvw/llm-cpp-toolkit/main/install.sh | bash
```

### 2. Package Managers

#### Homebrew/Linuxbrew
```bash
# Add tap (coming soon)
brew tap gregvw/llm-cpp-toolkit
brew install llmtk
```

#### Nix Flake
```bash
# Development shell
nix develop github:gregvw/llm-cpp-toolkit

# Install package
nix profile install github:gregvw/llm-cpp-toolkit
```

#### Docker
```bash
# Quick start
docker run --rm -v $(pwd):/workspace ghcr.io/gregvw/llm-cpp-toolkit:latest

# Development environment
docker build -t llmtk-dev --target=dev containers/
docker run -it --rm -v $(pwd):/workspace llmtk-dev
```

### 3. Manual Installation
```bash
git clone https://github.com/gregvw/llm-cpp-toolkit.git
cd llm-cpp-toolkit
./install.sh --yes
```

### 4. Local Tools Only (No sudo)
```bash
git clone https://github.com/gregvw/llm-cpp-toolkit.git
cd llm-cpp-toolkit
python3 cli/llmtk install --local
export PATH="$(pwd)/.llmtk/bin:$PATH"
```

## 🔧 First Steps

### 1. Verify Installation
```bash
llmtk doctor
```
This checks which tools are available and highlights any missing dependencies.

### 2. Bootstrap or Adopt a Project
```bash
# Create a fresh starter project in a new directory
llmtk init my-cpp-project

# Or adopt an existing project without touching sources
llmtk init --existing path/to/project
```
This drops a `CMakeLists.txt` template for new projects or produces an adoption report for existing ones.

### 3. Generate Context for Your Project
```bash
cd your-cpp-project/
llmtk context export
```
Creates `exports/compile_commands.json` and CMake file API data that LLMs need.

### 4. Run Static Analysis
```bash
llmtk analyze
```
Runs clang-tidy, include-what-you-use, and cppcheck, outputting JSON reports in `exports/reports/`.

## 📁 Project Structure Expected

llmtk works best with projects that have:

```
your-project/
├── CMakeLists.txt          # CMake project (recommended)
├── src/                    # Source files
├── include/                # Header files
└── build/                  # Build directory (created by llmtk)
```

For non-CMake projects, create a minimal `compile_commands.json` manually or use `bear` to capture compilation commands.

## 📋 Common Workflows

### For C++ Development
```bash
# Set up project analysis
llmtk context export
llmtk analyze

# Check reports
cat exports/reports/clang-tidy.json | jq '.diagnostic_counts'
cat exports/reports/cppcheck.json | jq '.summary'
```

### For LLM Agents
```bash
# Generate all context an LLM needs
llmtk context export

# Get machine-readable tool status
llmtk doctor

# Run comprehensive analysis
llmtk analyze src/ include/

# All results are in exports/ directory as JSON
ls exports/
```

### For CI/CD
```bash
# Install tools without interaction
llmtk install --local

# Run analysis and check for issues
llmtk analyze
if jq -e '.diagnostic_counts.error > 0' exports/reports/clang-tidy.json; then
  echo "Errors found in static analysis"
  exit 1
fi
```

## 🛠 Installation Methods Comparison

| Method | Pros | Cons | Use Case |
|--------|------|------|----------|
| **One-line script** | Simple, automatic deps | Requires internet, sudo | Quick start, CI |
| **Nix flake** | Reproducible, hermetic | Requires Nix | Deterministic environments |
| **Docker** | Isolated, consistent | Requires Docker | Containers, CI |
| **Local install** | No sudo required | Limited tool selection | Restricted environments |
| **Package managers** | System integration | Platform-specific | Long-term development |

## 🎯 Next Steps

- Read [AGENTS.md](AGENTS.md) for the full design philosophy
- Check [docs/REFERENCE.md](docs/REFERENCE.md) for complete command reference
- Explore example configurations in `presets/`
- Set up your editor with clangd using the generated `compile_commands.json`

## ❓ Troubleshooting

### Missing Tools
```bash
# Check what's missing
llmtk doctor

# Install missing tools locally
llmtk install --local

# Or install specific tools
llmtk install cppcheck include-what-you-use
```

### Empty compile_commands.json
```bash
# For CMake projects
mkdir -p build
cmake -S . -B build -DCMAKE_EXPORT_COMPILE_COMMANDS=ON

# For other build systems
bear -- make  # or your build command
```

### Permission Issues
```bash
# Use local installation
llmtk install --local
export PATH="$(pwd)/.llmtk/bin:$PATH"
```

### Tool Version Conflicts
```bash
# Use containerized environment
nix develop github:gregvw/llm-cpp-toolkit
# or
docker run -it --rm -v $(pwd):/workspace ghcr.io/gregvw/llm-cpp-toolkit:dev
```

## 📚 Learning Resources

- **Quick demos**: Run `llmtk analyze --help` for examples
- **JSON schemas**: Check `exports/` for the structure agents expect
- **Configuration**: See `presets/` for clang-tidy and formatting configs
- **Integration**: Examples of using llmtk in CI/CD workflows
