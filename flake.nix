{
  description = "LLM-friendly C++ development toolkit";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};

        # Core tools required for C++ development
        coreTools = with pkgs; [
          cmake
          ninja
          bear
          clang-tools_18  # includes clang-tidy, clang-format
          ripgrep
          fd
          jq
          yq
        ];

        # Recommended tools for enhanced functionality
        recommendedTools = with pkgs; [
          include-what-you-use
          cppcheck
          universal-ctags
          fzf
          zoxide
          bat
          tokei
          hyperfine
          entr
          pre-commit
        ];

        # Optional tools for ergonomics
        optionalTools = with pkgs; [
          eza
          tree
          procs
          bottom
          httpie
          tldr
          difftastic
          delta
        ];

        # Main package
        llmtk = pkgs.stdenv.mkDerivation {
          pname = "llmtk";
          version = "0.1.0";

          src = ./.;

          nativeBuildInputs = [ pkgs.makeWrapper ];

          buildInputs = [ pkgs.python3 ] ++ coreTools;

          installPhase = ''
            runHook preInstall

            # Create directory structure
            mkdir -p $out/share/llmtk
            mkdir -p $out/bin

            # Copy source files
            cp -r . $out/share/llmtk/

            # Create wrapper script
            makeWrapper ${pkgs.python3}/bin/python3 $out/bin/llmtk \
              --add-flags "$out/share/llmtk/cli/llmtk" \
              --set LLMTK_DIR "$out/share/llmtk" \
              --prefix PATH : "${pkgs.lib.makeBinPath (coreTools ++ recommendedTools)}"

            runHook postInstall
          '';

          meta = with pkgs.lib; {
            description = "LLM-friendly C++ development toolkit";
            homepage = "https://github.com/gregvw/llm-cpp-toolkit";
            license = licenses.mit;
            maintainers = [ ];
            platforms = platforms.unix;
          };
        };

      in
      {
        # Default package
        packages.default = llmtk;
        packages.llmtk = llmtk;

        # Development shells
        devShells.default = pkgs.mkShell {
          buildInputs = coreTools ++ recommendedTools ++ [
            pkgs.python3
            pkgs.git
          ];

          shellHook = ''
            echo "🔧 llm-cpp-toolkit development environment"
            echo "Available tools:"
            echo "  Core: cmake, ninja, clang-tidy, bear, ripgrep, fd, jq"
            echo "  Analysis: cppcheck, include-what-you-use"
            echo "  Utils: fzf, bat, tokei, hyperfine"
            echo ""
            echo "Quick start:"
            echo "  python3 cli/llmtk doctor"
            echo "  python3 cli/llmtk context export"
            echo "  python3 cli/llmtk analyze"
            echo ""
          '';
        };

        # Minimal shell with just core tools
        devShells.minimal = pkgs.mkShell {
          buildInputs = coreTools ++ [ pkgs.python3 ];
          shellHook = ''
            echo "🔧 llm-cpp-toolkit minimal environment (core tools only)"
          '';
        };

        # Full shell with all tools
        devShells.full = pkgs.mkShell {
          buildInputs = coreTools ++ recommendedTools ++ optionalTools ++ [
            pkgs.python3
            pkgs.git
          ];
          shellHook = ''
            echo "🔧 llm-cpp-toolkit full environment (all tools)"
          '';
        };

        # CI/automation shell
        devShells.ci = pkgs.mkShell {
          buildInputs = coreTools ++ recommendedTools ++ [
            pkgs.python3
            pkgs.git
            pkgs.curl
            pkgs.wget
          ];
          shellHook = ''
            echo "🔧 llm-cpp-toolkit CI environment"
          '';
        };

        # Apps for direct execution
        apps.default = flake-utils.lib.mkApp {
          drv = llmtk;
          name = "llmtk";
        };

        # Formatter for the flake
        formatter = pkgs.nixpkgs-fmt;
      });
}