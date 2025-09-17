class LlmCppToolkit < Formula
  desc "A comprehensive toolkit for working with LLM C++ implementations"
  homepage "https://github.com/gregvw/llm-cpp-toolkit"
  url "https://github.com/gregvw/llm-cpp-toolkit/archive/v0.1.0.tar.gz"
  sha256 "" # This will need to be updated when you create a release
  license "BSD-3-Clause"
  head "https://github.com/gregvw/llm-cpp-toolkit.git", branch: "main"

  depends_on "python@3.11"

  def install
    # Install the main CLI script
    bin.install "cli/llmtk"

    # Create lib directory for supporting files
    lib_dir = libexec/"lib"
    lib_dir.mkpath

    # Install supporting Python files
    lib_dir.install "build_manager.py"
    lib_dir.install "modules"
    lib_dir.install "presets"
    lib_dir.install "manifest"
    lib_dir.install "VERSION"

    # Update the script to use the correct paths
    inreplace bin/"llmtk",
              "ROOT = pathlib.Path(__file__).resolve().parent.parent",
              "ROOT = pathlib.Path('#{lib_dir}')"

    # Make sure it's executable
    chmod 0755, bin/"llmtk"
  end

  test do
    # Test that the command runs and shows version
    output = shell_output("#{bin}/llmtk --version 2>&1")
    assert_match version.to_s, output
  end
end