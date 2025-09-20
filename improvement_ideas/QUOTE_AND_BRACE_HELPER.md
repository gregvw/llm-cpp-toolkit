# Helper Script for Quotes and Braces 

LLMs can struggle with writing and editing code that contains complex nested (single and double) quotes as well as lots of nested braces
(),[],<>,{}. I propose making a utility that can check for unmatched pairs before compilations as part of the `build_manager`. 

**`llmtk preflight`** — a fast, language-aware sanity pass that:

1. audits **delimiters/quotes** across changed files,
2. runs **cheap syntax checks** per file type,
3. returns **machine-readable** findings (JSON/SARIF) and a terse human summary,
4. **fails fast** (non-zero exit) so `build_manager` can stop before expensive work.

# How it plugs in

* `build_manager` calls:

  1. `llmtk preflight --diff <rev>` (or `--paths …`)
  2. if exit ≠ 0 → print findings and abort
  3. else → proceed to configure/build/test

Example hook:

```bash
# build_manager.sh
set -euo pipefail
llmtk preflight --diff HEAD || {
  echo "[llmtk] Preflight failed. Fix delimiters/syntax before building."
  exit 1
}
# safe to proceed
llmtk analyze --sarif
cmake --build build -j
```

# CLI shape (suggested)

```
llmtk preflight [--diff <rev>|--since <rev>|--paths <...>]
                [--json out.json] [--sarif out.sarif]
                [--strict] [--max-lines 200000]
                [--no-tree-sitter] [--no-syntax]
```

* **`--diff/--since`**: only check changed files (default).
* **`--paths`**: explicit whitelist.
* **`--strict`**: treat warnings as errors.
* **`--json/--sarif`**: artifacts for agents/CI.

# What it checks (fast + layered)

## A) Delimiter & quote audit (Tree-sitter, then fallbacks)

* Use **Tree-sitter** when available to lex tokens and ignore comments/strings; run a simple **stack machine** per file to validate:

  * `() [] {} <>` (angle brackets only when tokenized as operators, not templates in comments/strings)
  * single `'` and double `"` quotes (multi-line aware)
  * backticks for Markdown code fences (triple \`\`\`), and balanced fence languages
* Supported grammars to start: `cpp`, `c`, `cmake`, `json`, `toml`, `yaml`, `markdown`, `python`.
* If Tree-sitter isn’t present, **fallback** to quick mode:

  * line scanner that ignores regions between tokenized comment/string spans discovered by simple heuristics (good enough for a guard).

**Finding schema (JSON):**

````json
{
  "tool": "llmtk-preflight",
  "version": "1",
  "findings": [
    {
      "file": "src/foo.cpp",
      "line": 127,
      "col": 18,
      "rule": "unbalanced_paren",
      "symbol": "(",
      "message": "Opening '(' without matching ')'",
      "severity": "error",
      "near": "call(x, y"
    },
    {
      "file": "docs/README.md",
      "line": 88,
      "rule": "md_fence_unclosed",
      "message": "Unclosed ``` code fence (lang=cpp)",
      "severity": "error"
    }
  ]
}
````

(We can map this 1-to-1 to SARIF too.)

## B) Cheap syntax probes (per file type)

* **C/C++**: `clang -fsyntax-only` per TU (use compdb to pick flags); abort early if unterminated strings or brace mismatches.
* **JSON**: `jq .`
* **TOML**: `taplo check`
* **YAML**: `yamllint` (structured output)
* **CMake**: `cmake-format --check` (or `cmakelint` as a fallback)
* **Shell**: `bash -n`; **PowerShell**: `pwsh -NoProfile -Command { Set-StrictMode -Version Latest; [ScriptBlock]::Create((gc file)).CheckSyntax() }`
* **Markdown**: fence balance + optional `markdownlint`

Only run against **changed files**; bail out after N findings per file (configurable) to stay fast.

# Exit codes

* `0` = clean
* `2` = warnings only (strict off)
* `3` = errors found (fail build)
* `10` = internal error (misconfig)

# Performance notes

* By default, cap scan to **max changed lines** (`--max-lines`) so huge vendor drops don’t block.
* Tree-sitter parsing is \~ms per file; cache grammar instances across files in the same process.
* `clang -fsyntax-only` can be parallelized; consider `-j` based on CPU count.

# Implementation sketch (Python)

Keep it as a small module so it’s portable and easy to vendor:

```
tools/
  preflight/
    __init__.py
    main.py
    fileset.py           # diff detection (git), path filters
    delimiters.py        # tree-sitter + fallback stack checker
    syntax_probes.py     # jq/taplo/yamllint/clang -fsyntax-only
    reporters.py         # JSON/SARIF/human/table (tabulate)
```

**Delimiter stack outline (fallback mode):**

```python
PAIRS = {'(': ')', '[': ']', '{': '}'}
OPEN = set(PAIRS.keys()); CLOSE = set(PAIRS.values())

def check_linewise(text):
  stack = []
  for i, line in enumerate(text.splitlines(), 1):
    j = 0
    in_s = None  # "'", '"'
    esc = False
    while j < len(line):
      c = line[j]
      if in_s:
        if not esc and c == in_s:
          in_s = None
        esc = (c == '\\' and not esc)
      else:
        if c in "'\"":
          in_s = c
        elif c in OPEN:
          stack.append((c, i, j+1))
        elif c in CLOSE:
          if not stack or PAIRS[stack[-1][0]] != c:
            yield {"line": i, "col": j+1, "rule": "unbalanced_paren",
                   "symbol": c, "message": "Closing without opener"}
          else:
            stack.pop()
      j += 1
  for c, i, j in stack:
    yield {"line": i, "col": j, "rule": "unbalanced_paren",
           "symbol": c, "message": "Opening without closer"}
```

Tree-sitter mode replaces the raw scan: iterate token nodes outside comments/strings.

# Human output (but still agent-safe)

When TTY, print a tiny table before exiting:

````
File               Issue                    L:C    Near
src/foo.cpp        Opening '(' no ')'       127:18 call(x, y
docs/README.md     Unclosed ``` fence       88
````

Always mirror to `--json` / `--sarif` for agents.

# `build_manager` integration

Add a single line to the “pre-build” stage:

```bash
llmtk preflight --diff HEAD~1 --json exports/reports/preflight.json \
  || { llmtk summarize preflight exports/reports/preflight.json; exit 1; }
```

(`llmtk summarize preflight` can just pretty-print the JSON into a human digest using `tabulate`.)

# Optional: pre-commit & PR guard

* Ship a **pre-commit** config that runs `llmtk preflight --paths $(git diff --name-only --cached)`.
* In CI, fail fast and attach the **SARIF** so platforms like GitHub can annotate diffs inline.

# Why this works for agents

* It catches the class of errors LLMs commonly introduce (but compilers might only reveal after a full TU compile).
* It’s **language-aware**, so comments/strings don’t confuse it.
* It’s **fast** and patch-scoped → perfect as an automatic `build_manager` gate.

# Leveraging PEGTL

Absolutely—**PEGTL** is a solid way to build a fast, embeddable, language-aware pre-build guard. It gives you precise control over what counts as “code” vs “comment/string,” which is exactly where naive stack checkers fall over.

Here’s how I’d use it, without boiling the ocean:

# Recommended split of responsibility

* **C/C++**: keep using `clang -fsyntax-only` (or libclang tokens). C++ angle-brackets (`< >`) and preprocessor rules are not worth re-implementing.
* **Everything else** (where agents often break quoting/delimiters): implement **PEGTL micro-grammars**:

  * Markdown (\`\`\` fences, inline/code blocks)
  * JSON (or call `jq`), TOML (or `taplo`), YAML (or `yamllint`) — PEGTL is fine here but external tools are faster to add
  * CMake subset (quotes, parens, bracket comments/strings)
  * INI/CFG, simple domain files
  * Optional: a **generic mode** (treat only ()\[]{} and '"/\`\`\` outside comments) for unknown text files

# Tool shape

Create a tiny C++ binary (header-only deps): `llmtk-preflight-pegtl` that:

1. Given files (or a `--diff` list), chooses a grammar by extension.
2. Uses PEGTL to **tokenize and skip** comments/strings.
3. Runs a **delimiter/quote stack** only in code regions.
4. Emits **JSON (and optional SARIF)** findings.
5. Returns non-zero on errors so `build_manager` aborts before building.

# Minimal PEGTL skeleton (balanced quotes/parens outside comments)

```cpp
// llmtk_preflight_pegtl.cpp
#include <tao/pegtl.hpp>
#include <string>
#include <vector>
#include <iostream>

namespace pegtl = tao::pegtl;

struct Finding {
  std::string file; int line=0, col=0;
  std::string rule, symbol, message, near;
};

// -------- Generic lexer-ish pieces (C-like) ----------
namespace lex {
// Single-line comment: //...
struct sl_comment : pegtl::seq< pegtl::string<'/','/'>, pegtl::until< pegtl::eolf > > {};
// Multi-line comment: /* ... */
struct ml_comment : pegtl::seq< pegtl::string<'/','*'>, pegtl::until< pegtl::string<'*','/'> > > {};
// String literals (naive but works for many: " ... ")
struct dq_char : pegtl::sor< pegtl::string<'\\','\"'>, pegtl::string<'\\','\\'>, pegtl::not_one<'"'> > {};
struct dquote_str : pegtl::seq< pegtl::one<'"'>, pegtl::star< dq_char >, pegtl::one<'"'> > {};
struct sq_char : pegtl::sor< pegtl::string<'\\','\''>, pegtl::string<'\\','\\'>, pegtl::not_one<'\''> > {};
struct squote_str : pegtl::seq< pegtl::one<'\''>, pegtl::star< sq_char >, pegtl::one<'\''> > {};

// Delimiters to track
struct open_delim  : pegtl::one<'(','[','{'> {};
struct close_delim : pegtl::one<')',']','}'> {};

// Tokens we *skip* (strings/comments)
struct skip : pegtl::sor< sl_comment, ml_comment, dquote_str, squote_str > {};

// Anything else = one byte (advance)
struct any1_not_skip : pegtl::not_at<skip, open_delim, close_delim>, pegtl::any {};

// The stream: repeatedly either skip, record delimiters, or advance
struct grammar : pegtl::star< pegtl::sor< skip, open_delim, close_delim, any1_not_skip > > {};
} // namespace lex

// -------- Delimiter stack state & actions ------------
struct State {
  std::vector<std::tuple<char,int,int>> stack; // (symbol,line,col)
  std::vector<Finding> findings;
  const std::string* file = nullptr;
};

template<typename Rule> struct action : pegtl::nothing<Rule> {};

template<> struct action<lex::open_delim> {
  template<typename Input>
  static void apply(const Input& in, State& st) {
    st.stack.emplace_back(in.string()[0], in.position().line, in.position().byte_in_line);
  }
};

static inline char match(char c) {
  return c=='(' ? ')' : c=='[' ? ']' : c== '{' ? '}' : '\0';
}

template<> struct action<lex::close_delim> {
  template<typename Input>
  static void apply(const Input& in, State& st) {
    char c = in.string()[0];
    if (st.stack.empty() || match(std::get<0>(st.stack.back())) != c) {
      st.findings.push_back(Finding{
        *st.file, (int)in.position().line, (int)in.position().byte_in_line,
        "unbalanced_paren", std::string(1,c),
        "Closing delimiter without matching opener", {}
      });
    } else {
      st.stack.pop_back();
    }
  }
};

// -------- Driver ------------------------------------
std::vector<Finding> check_file(const std::string& path, pegtl::memory_input<>& in) {
  State st; st.file = &path;
  try {
    pegtl::parse<lex::grammar, action>(in, st);
  } catch(const pegtl::parse_error& e) {
    auto p = e.positions().empty() ? pegtl::position() : e.positions().front();
    st.findings.push_back(Finding{ path, (int)p.line, (int)p.byte_in_line,
                                   "parse_error", "", e.what(), {}});
  }
  // Any leftover openers → errors
  for (auto& [sym, line, col] : st.stack) {
    st.findings.push_back(Finding{
      path, line, col, "unbalanced_paren", std::string(1, sym),
      "Opening delimiter without matching closer", {}
    });
  }
  return st.findings;
}

int main(int argc, char** argv) {
  if (argc < 2) { std::cerr << "usage: preflight-pegtl <file>...\n"; return 2; }
  std::vector<Finding> all;
  for (int i=1;i<argc;++i) {
    pegtl::file_input in(argv[i]);
    auto v = check_file(argv[i], in);
    all.insert(all.end(), v.begin(), v.end());
  }
  if (!all.empty()) {
    // JSON-ish output (trimmed for brevity)
    std::cout << "{ \"findings\": [\n";
    for (size_t i=0;i<all.size();++i) {
      auto& f = all[i];
      std::cout << " {\"file\":\""<<f.file<<"\",\"line\":"<<f.line
                <<",\"col\":"<<f.col<<",\"rule\":\""<<f.rule
                <<"\",\"symbol\":\""<<f.symbol<<"\",\"message\":\""<<f.message<<"\"}"
                << (i+1<all.size() ? ",\n" : "\n");
    }
    std::cout << "]}\n";
  }
  return all.empty() ? 0 : 3;
}
```

### Notes

* That grammar **skips** `// …`, `/* … */`, and proper `'...'` / `"..."` sequences, so the stack never “sees” delimiters inside strings/comments.
* Extend per language: for **Markdown**, add a rule that detects fenced blocks (`…`) and treats their interiors as “skipped”; for **CMake**, add bracket comments/strings (`#[[ … ]]`, `[[ … ]]`).
* Angle brackets are **not** tracked (on purpose). In C/C++, let Clang judge templates/includes.

# CMake wiring

```cmake
add_executable(llmtk-preflight-pegtl tools/preflight/llmtk_preflight_pegtl.cpp)
target_compile_features(llmtk-preflight-pegtl PRIVATE cxx_std_20)
# PEGTL is header-only; either FetchContent or a package:
# find_package(taocpp-pegtl CONFIG QUIET) / add_subdirectory(3rdparty/PEGTL)
target_link_libraries(llmtk-preflight-pegtl PRIVATE taocpp::pegtl)
```

# Integrate with `build_manager`

* Add a pre-build step:

  ```bash
  llmtk-preflight-pegtl $(git diff --name-only HEAD) \
    | tee exports/reports/preflight.json
  test ${PIPESTATUS[0]} -eq 0 || exit 1
  ```
* Or wrap it as `llmtk preflight --pegtl` and merge findings into your existing JSON/SARIF.

# When to prefer PEGTL vs. existing tools

* **Use PEGTL** to cover *lightweight, language-aware* balance checks (Markdown/CMake/INI/other docs), where external linters aren’t already standard.
* **Keep external tools** for formats with great validators (JSON/TOML/YAML) and **keep Clang** for C/C++.


