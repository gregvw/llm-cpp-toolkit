class Llmtk < Formula
  desc "LLM-friendly C++ development toolkit"
  homepage "https://github.com/gregvw/llm-cpp-toolkit"
  url "https://github.com/gregvw/llm-cpp-toolkit/archive/refs/heads/main.tar.gz"
  version "0.1.0"
  sha256 "PLACEHOLDER_SHA256"

  depends_on "python@3.12"
  depends_on "cmake"
  depends_on "ninja"
  depends_on "llvm"
  depends_on "bear"
  depends_on "ripgrep"
  depends_on "fd"
  depends_on "jq"
  depends_on "yq"

  # Optional but recommended dependencies
  depends_on "cppcheck" => :optional
  depends_on "include-what-you-use" => :optional
  depends_on "universal-ctags" => :optional
  depends_on "fzf" => :optional
  depends_on "bat" => :optional
  depends_on "tokei" => :optional
  depends_on "hyperfine" => :optional

  def install
    # Install the toolkit
    libexec.install Dir["*"]

    # Create wrapper script
    (bin/"llmtk").write <<~EOS
      #!/usr/bin/env bash
      export LLMTK_DIR="#{libexec}"
      exec "#{Formula["python@3.12"].opt_bin}/python3" "#{libexec}/cli/llmtk" "$@"
    EOS

    # Make wrapper executable
    chmod 0755, bin/"llmtk"

    # Install shell completions if available
    if (libexec/"completions").exist?
      bash_completion.install libexec/"completions/llmtk.bash"
      zsh_completion.install libexec/"completions/_llmtk"
      fish_completion.install libexec/"completions/llmtk.fish"
    end
  end

  def post_install
    # Run initial setup
    system bin/"llmtk", "doctor"
  end

  test do
    # Test basic functionality
    assert_match "llmtk", shell_output("#{bin}/llmtk --version")

    # Test doctor command
    system bin/"llmtk", "doctor"

    # Test that exports directory can be created
    system bin/"llmtk", "context", "export", "--build", testpath/"build"
    assert_predicate testpath/"exports/context.json", :exist?
  end

  def caveats
    <<~EOS
      llmtk has been installed!

      To get started:
        llmtk doctor          # Check tool availability
        llmtk install         # Install missing tools locally if needed
        llmtk context export  # Generate compilation database
        llmtk analyze         # Run static analysis

      Add local tools to PATH if needed:
        export PATH="$HOME/.local/share/llm-cpp-toolkit/.llmtk/bin:$PATH"

      Documentation: https://github.com/gregvw/llm-cpp-toolkit
    EOS
  end
end