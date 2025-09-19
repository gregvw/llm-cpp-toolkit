# LLM C++ Toolkit Cookbook

## 🍲 Optimizing for Token Budgets

When working with Large Language Models, managing the size of your input (the "context window") is critical. `llmtk` provides tools to help you generate concise, relevant context for your AI assistant.

### Context Reduction Benchmarks

| Command | Typical Output Size | Use Case |
|---|---|---|
| `llmtk doctor` | 1-5 KB | Initial environment check |
| `llmtk context export` | 5-50 KB | Basic build information |
| `llmtk context export --deep` | 50-500 KB | Detailed build analysis |
| `llmtk analyze` | 10-1000 KB | Static analysis results |

### Strategies for Reducing Context

1.  **Use `.gitignore`**: `llmtk` respects `.gitignore`, so a well-maintained ignore file is your first line of defense.
2.  **Scope analysis**: Instead of running `llmtk analyze` on your entire project, target specific directories or files:
    ```bash
    llmtk analyze src/my-feature/
    ```
3.  **Use `context pack --redact`**: When sharing context, use the `--redact` flag to strip out sensitive or irrelevant information (note: redaction is not yet fully implemented).

## 🍳 Recipes

### Recipe 1: Debugging a build error

1.  **Export the build context**:
    ```bash
    llmtk context export
    ```
2.  **Run a lint build**:
    ```bash
    cmake --build build --target lint
    ```
3.  **Provide the context and error to your LLM**:
    - `exports/context.json`
    - `build/lint/*.json` (the specific error file)

### Recipe 2: Pre-commit analysis

1.  **Install pre-commit hooks**:
    ```bash
    pre-commit install
    ```
2.  **Run analysis on staged files**:
    ```bash
    llmtk analyze $(git diff --name-only --cached)
    ```
This can be integrated into your CI/CD pipeline to catch issues before they're merged.
