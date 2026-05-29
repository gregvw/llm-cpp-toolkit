"""Tests for the Jinja2-based `llmtk init` scaffolding.

Two layers:
- Pure render tests (no toolchain): render the minimal/executable/library/full
  presets and assert key CMake content.
- One end-to-end test (toolchain-guarded): `llmtk init <project>` renders the
  templates, configures with CMake, builds, and the capabilities output is
  still valid.
"""

import argparse
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from llmtk.commands import init as init_cmd
from llmtk.services.manifest import generate_capabilities_json
from llmtk.services.scaffold import context_from_preset, render_scaffold

_CLANG20_BIN = Path("/opt/homebrew/opt/llvm@20/bin")


def _preferred_compilers():
    cxx, cc = _CLANG20_BIN / "clang++", _CLANG20_BIN / "clang"
    if cxx.exists() and cc.exists():
        return str(cc), str(cxx)
    return None, None


def _have_cxx():
    if _preferred_compilers()[1]:
        return True
    return any(shutil.which(name) for name in ("c++", "clang++", "g++"))


TOOLCHAIN_AVAILABLE = (
    bool(shutil.which("cmake"))
    and bool(shutil.which("ninja"))
    and bool(shutil.which("git"))
    and _have_cxx()
)
REQUIRES_TOOLCHAIN = unittest.skipUnless(
    TOOLCHAIN_AVAILABLE, "requires cmake, ninja, git, and a C++ compiler"
)


def _render(preset, **kwargs):
    """Render a preset into a fresh temp dir and return (dir, cmakelists_text)."""
    dest = Path(tempfile.mkdtemp(prefix="llmtk-scaffold-"))
    ctx = context_from_preset("proj", preset=preset, **kwargs)
    render_scaffold(ctx, dest)
    return dest, (dest / "CMakeLists.txt").read_text(encoding="utf-8")


class ScaffoldRenderTests(unittest.TestCase):
    def setUp(self):
        self._dirs = []

    def tearDown(self):
        for d in self._dirs:
            shutil.rmtree(d, ignore_errors=True)

    def _render(self, preset, **kwargs):
        dest, cmake = _render(preset, **kwargs)
        self._dirs.append(dest)
        return dest, cmake

    def test_all_scaffold_files_written_and_presets_valid_json(self):
        dest, _ = self._render("executable")
        for rel in ("CMakeLists.txt", "src/main.cpp", ".gitignore", "CMakePresets.json"):
            self.assertTrue((dest / rel).exists(), f"missing {rel}")
        # CMakePresets.json must be valid JSON (it is scaffold, not a runtime artifact).
        presets = json.loads((dest / "CMakePresets.json").read_text())
        self.assertEqual(presets["version"], 3)
        self.assertEqual(presets["configurePresets"][0]["name"], "default")

    def test_minimal_preset_is_a_bare_executable(self):
        _, cmake = self._render("minimal")
        self.assertIn("add_executable(proj src/main.cpp)", cmake)
        self.assertNotIn("add_library", cmake)
        self.assertNotIn("enable_testing()", cmake)
        self.assertNotIn("fsanitize", cmake)
        self.assertNotIn("POSITION_INDEPENDENT_CODE", cmake)

    def test_executable_preset_enables_tests(self):
        _, cmake = self._render("executable")
        self.assertIn("add_executable(proj src/main.cpp)", cmake)
        self.assertIn("enable_testing()", cmake)
        self.assertIn("add_test(NAME proj_smoke COMMAND proj)", cmake)
        self.assertNotIn("fsanitize", cmake)

    def test_library_preset_builds_a_library_with_pic(self):
        dest, cmake = self._render("library")
        self.assertIn("add_library(proj src/main.cpp)", cmake)
        self.assertIn("set(CMAKE_POSITION_INDEPENDENT_CODE ON)", cmake)
        self.assertNotIn("add_executable", cmake)
        # A library has no main(); the smoke add_test (which runs the target) is skipped.
        self.assertNotIn("add_test(", cmake)
        self.assertNotIn("int main()", (dest / "src" / "main.cpp").read_text())

    def test_full_preset_enables_sanitizers(self):
        _, cmake = self._render("full")
        self.assertIn("-fsanitize=address,undefined", cmake)
        self.assertIn("enable_testing()", cmake)

    def test_std_and_cmake_minimum_are_interpolated(self):
        _, cmake = self._render("executable", cpp_standard="20", cmake_minimum="3.25")
        self.assertIn("cmake_minimum_required(VERSION 3.25)", cmake)
        self.assertIn("set(CMAKE_CXX_STANDARD 20)", cmake)


@contextlib.contextmanager
def _workspace():
    """A temp cwd with git author + preferred compiler env set."""
    tmp = Path(tempfile.mkdtemp(prefix="llmtk-init-"))
    saved_cwd = os.getcwd()
    saved_env = {k: os.environ.get(k) for k in (
        "CC", "CXX", "GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL",
        "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL",
    )}
    try:
        os.chdir(tmp)
        os.environ.update(
            GIT_AUTHOR_NAME="llmtk-test",
            GIT_AUTHOR_EMAIL="test@llmtk.invalid",
            GIT_COMMITTER_NAME="llmtk-test",
            GIT_COMMITTER_EMAIL="test@llmtk.invalid",
        )
        cc, cxx = _preferred_compilers()
        if cc and cxx:
            os.environ["CC"], os.environ["CXX"] = cc, cxx
        yield tmp.resolve()
    finally:
        os.chdir(saved_cwd)
        for key, value in saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(tmp, ignore_errors=True)


class InitEndToEndTests(unittest.TestCase):
    @REQUIRES_TOOLCHAIN
    def test_init_renders_configures_builds_and_capabilities_valid(self):
        with _workspace() as work:
            args = argparse.Namespace(
                project_name="demoapp", existing=False, path=None,
                std="17", cmake_min="3.20", preset="executable",
            )
            with contextlib.redirect_stdout(io.StringIO()):
                rc = init_cmd.cmd_init(args)
            self.assertEqual(rc, 0)

            project = work / "demoapp"
            for rel in ("CMakeLists.txt", "src/main.cpp", ".gitignore",
                        "CMakePresets.json", "exports/capabilities.json"):
                self.assertTrue((project / rel).exists(), f"missing {rel}")

            # Configure + build the rendered project.
            configure = subprocess.run(
                ["cmake", "-S", str(project), "-B", str(project / "build"), "-G", "Ninja"],
                capture_output=True, text=True,
            )
            self.assertEqual(configure.returncode, 0, configure.stderr)
            build = subprocess.run(
                ["cmake", "--build", str(project / "build")],
                capture_output=True, text=True,
            )
            self.assertEqual(build.returncode, 0, build.stderr)
            self.assertTrue((project / "build" / "demoapp").exists())

            # The init-generated project capabilities are valid JSON.
            project_caps = json.loads((project / "exports" / "capabilities.json").read_text())
            self.assertIn("tools", project_caps)
            self.assertEqual(project_caps["build"]["system"], "cmake")

            # The stable toolkit capabilities output is still well-formed and
            # does not leak planned commands into the supported set.
            caps_file = work / "caps.json"
            generate_capabilities_json(caps_file)
            caps = json.loads(caps_file.read_text())
            self.assertEqual(caps["schema_version"], 1)
            self.assertIn("preflight", caps["commands"])
            self.assertIn("bench", caps["planned_commands"])
            self.assertNotIn("bench", caps["commands"])


@contextlib.contextmanager
def _temp_cwd():
    """chdir into a fresh temp dir, restoring cwd and PATH afterwards."""
    tmp = Path(tempfile.mkdtemp(prefix="llmtk-initgit-"))
    saved_cwd = os.getcwd()
    saved_path = os.environ.get("PATH")
    try:
        os.chdir(tmp)
        yield tmp.resolve()
    finally:
        os.chdir(saved_cwd)
        if saved_path is None:
            os.environ.pop("PATH", None)
        else:
            os.environ["PATH"] = saved_path
        shutil.rmtree(tmp, ignore_errors=True)


class InitGitFallbackTests(unittest.TestCase):
    """`llmtk init` must still produce a usable project when git fails."""

    def _run_init(self, name):
        args = argparse.Namespace(
            project_name=name, existing=False, path=None,
            std="17", cmake_min="3.20", preset="executable",
        )
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = init_cmd.cmd_init(args)
        return rc, out.getvalue()

    def _assert_scaffolded(self, project):
        for rel in ("CMakeLists.txt", "src/main.cpp", ".gitignore",
                    "CMakePresets.json", "exports/capabilities.json"):
            self.assertTrue((project / rel).exists(), f"missing {rel}")

    def test_succeeds_when_git_is_missing(self):
        with _temp_cwd() as work:
            empty_bin = work / "empty-bin"
            empty_bin.mkdir()
            os.environ["PATH"] = str(empty_bin)  # no git on PATH -> FileNotFoundError
            rc, out = self._run_init("nogit")

            self.assertEqual(rc, 0)
            self._assert_scaffolded(work / "nogit")
            self.assertFalse((work / "nogit" / ".git").exists())
            self.assertIn("git", out.lower())

    @unittest.skipUnless(os.name == "posix", "fake git shim needs a POSIX shell")
    def test_succeeds_when_git_commit_fails(self):
        with _temp_cwd() as work:
            fake_bin = work / "fake-bin"
            fake_bin.mkdir()
            shim = fake_bin / "git"
            # init/add succeed (no-ops); commit fails like an unconfigured author would.
            shim.write_text(
                "#!/bin/sh\n"
                "case \"$1\" in\n"
                "  commit) echo 'fatal: empty ident name not allowed' >&2; exit 128 ;;\n"
                "  *) exit 0 ;;\n"
                "esac\n"
            )
            shim.chmod(0o755)
            os.environ["PATH"] = f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}"
            rc, out = self._run_init("commitfail")

            self.assertEqual(rc, 0)
            self._assert_scaffolded(work / "commitfail")
            self.assertIn("git", out.lower())

    @unittest.skipUnless(shutil.which("git"), "requires a real git")
    def test_creates_repo_when_git_succeeds(self):
        with _temp_cwd() as work:
            git_env = dict(
                GIT_AUTHOR_NAME="llmtk-test", GIT_AUTHOR_EMAIL="test@llmtk.invalid",
                GIT_COMMITTER_NAME="llmtk-test", GIT_COMMITTER_EMAIL="test@llmtk.invalid",
            )
            saved = {k: os.environ.get(k) for k in git_env}
            os.environ.update(git_env)
            try:
                rc, _ = self._run_init("withgit")
            finally:
                for key, value in saved.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value

            project = work / "withgit"
            self.assertEqual(rc, 0)
            self._assert_scaffolded(project)
            self.assertTrue((project / ".git").is_dir())
            head = subprocess.run(
                ["git", "-C", str(project), "rev-parse", "HEAD"],
                capture_output=True, text=True,
            )
            self.assertEqual(head.returncode, 0, "expected an initial commit")


if __name__ == "__main__":
    unittest.main()
