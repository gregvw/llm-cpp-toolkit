#!/usr/bin/env python3
"""
Incremental diff-oriented context module for llmtk.

This module provides:
1. Diff-based context packs that focus on changed files and their dependencies
2. Minimal dependency graphs scoped to specific errors or changes
3. Automated bisect helpers for regression hunting

Designed for LLM agents to efficiently understand changes and their impact.
"""

import argparse
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
from typing import Any, Dict, List, Optional, Set, Tuple, Union


class GitHelper:
    """Helper class for Git operations."""

    def __init__(self, repo_path: pathlib.Path):
        self.repo_path = repo_path
        self.is_git_repo = self._check_git_repo()

    def _check_git_repo(self) -> bool:
        """Check if current directory is a git repository."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def get_changed_files(self, base_ref: str = "HEAD~1", target_ref: str = "HEAD") -> List[str]:
        """Get files changed between two git references."""
        if not self.is_git_repo:
            return []

        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", f"{base_ref}..{target_ref}"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            return [line.strip() for line in result.stdout.splitlines() if line.strip()]
        except subprocess.CalledProcessError:
            return []

    def get_diff_content(self, base_ref: str = "HEAD~1", target_ref: str = "HEAD",
                        file_path: Optional[str] = None) -> str:
        """Get diff content between two references, optionally for a specific file."""
        if not self.is_git_repo:
            return ""

        cmd = ["git", "diff", f"{base_ref}..{target_ref}"]
        if file_path:
            cmd.append("--")
            cmd.append(file_path)

        try:
            result = subprocess.run(
                cmd,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout
        except subprocess.CalledProcessError:
            return ""

    def get_commit_info(self, ref: str = "HEAD") -> Dict[str, Any]:
        """Get commit information for a reference."""
        if not self.is_git_repo:
            return {}

        try:
            result = subprocess.run(
                ["git", "show", "--format=%H|%s|%an|%ae|%at", "--no-patch", ref],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            parts = result.stdout.strip().split("|", 4)
            if len(parts) >= 5:
                return {
                    "hash": parts[0],
                    "subject": parts[1],
                    "author_name": parts[2],
                    "author_email": parts[3],
                    "timestamp": int(parts[4])
                }
        except subprocess.CalledProcessError:
            pass
        return {}

    def get_commits_between(self, base_ref: str, target_ref: str) -> List[Dict[str, Any]]:
        """Get commit list between two references."""
        if not self.is_git_repo:
            return []

        try:
            result = subprocess.run(
                ["git", "rev-list", "--format=%H|%s|%an|%ae|%at", f"{base_ref}..{target_ref}"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )

            commits = []
            lines = result.stdout.strip().split("\n")
            for line in lines:
                if "|" in line and not line.startswith("commit"):
                    parts = line.split("|", 4)
                    if len(parts) >= 5:
                        commits.append({
                            "hash": parts[0],
                            "subject": parts[1],
                            "author_name": parts[2],
                            "author_email": parts[3],
                            "timestamp": int(parts[4])
                        })
            return commits
        except subprocess.CalledProcessError:
            return []


class DependencyTracker:
    """Track dependencies related to specific files and errors."""

    def __init__(self, project_root: pathlib.Path):
        self.project_root = project_root
        self.compile_commands_path = project_root / "build" / "compile_commands.json"
        self.compile_commands = self._load_compile_commands()

    def _load_compile_commands(self) -> List[Dict[str, Any]]:
        """Load compile_commands.json if available."""
        if self.compile_commands_path.exists():
            try:
                with open(self.compile_commands_path, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return []
        return []

    def get_file_dependencies(self, source_file: str) -> Dict[str, Any]:
        """Get dependencies for a specific source file."""
        dependencies = {
            "direct_includes": [],
            "indirect_includes": [],
            "compile_flags": [],
            "linked_targets": []
        }

        # Find compile command for this file
        source_path = str(pathlib.Path(source_file).resolve())
        compile_entry = None
        for entry in self.compile_commands:
            if pathlib.Path(entry.get("file", "")).resolve() == pathlib.Path(source_path):
                compile_entry = entry
                break

        if compile_entry:
            # Extract compile flags
            command = compile_entry.get("command", "")
            dependencies["compile_flags"] = command.split()

            # Extract include directories
            include_dirs = []
            flags = command.split()
            for i, flag in enumerate(flags):
                if flag == "-I" and i + 1 < len(flags):
                    include_dirs.append(flags[i + 1])
                elif flag.startswith("-I"):
                    include_dirs.append(flag[2:])

            # Find direct includes by parsing the source file
            dependencies["direct_includes"] = self._extract_includes(source_file)

        return dependencies

    def _extract_includes(self, source_file: str) -> List[str]:
        """Extract #include statements from a source file."""
        includes = []
        file_path = pathlib.Path(source_file)

        if file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("#include"):
                            # Extract include path
                            if '"' in line:
                                start = line.find('"') + 1
                                end = line.find('"', start)
                                if end > start:
                                    includes.append(line[start:end])
                            elif '<' in line:
                                start = line.find('<') + 1
                                end = line.find('>', start)
                                if end > start:
                                    includes.append(line[start:end])
            except IOError:
                pass

        return includes

    def get_minimal_context_for_files(self, changed_files: List[str]) -> Dict[str, Any]:
        """Get minimal context focusing on changed files and their direct dependencies."""
        context = {
            "changed_files": {},
            "dependency_graph": {},
            "affected_targets": [],
            "include_paths": set(),
            "compile_definitions": set()
        }

        for file_path in changed_files:
            if self._is_source_file(file_path):
                deps = self.get_file_dependencies(file_path)
                context["changed_files"][file_path] = deps

                # Add to dependency graph
                context["dependency_graph"][file_path] = deps["direct_includes"]

                # Track include paths and compile definitions
                for flag in deps["compile_flags"]:
                    if flag.startswith("-I"):
                        context["include_paths"].add(flag[2:] if len(flag) > 2 else "")
                    elif flag.startswith("-D"):
                        context["compile_definitions"].add(flag[2:] if len(flag) > 2 else "")

        # Convert sets to lists for JSON serialization
        context["include_paths"] = list(context["include_paths"])
        context["compile_definitions"] = list(context["compile_definitions"])

        return context

    def _is_source_file(self, file_path: str) -> bool:
        """Check if file is a C++ source file."""
        extensions = {'.cpp', '.cxx', '.cc', '.c', '.hpp', '.hxx', '.hh', '.h'}
        return pathlib.Path(file_path).suffix.lower() in extensions


class ErrorContextAnalyzer:
    """Analyze errors and provide minimal context for fixes."""

    def __init__(self, project_root: pathlib.Path):
        self.project_root = project_root
        self.dependency_tracker = DependencyTracker(project_root)

    def analyze_build_errors(self, error_log: str) -> Dict[str, Any]:
        """Analyze build errors and provide focused context."""
        errors = self._parse_build_errors(error_log)
        context = {
            "errors": errors,
            "affected_files": set(),
            "minimal_dependencies": {},
            "suggested_fixes": []
        }

        for error in errors:
            file_path = error.get("file")
            if file_path:
                context["affected_files"].add(file_path)

                # Get minimal dependencies for this file
                deps = self.dependency_tracker.get_file_dependencies(file_path)
                context["minimal_dependencies"][file_path] = {
                    "direct_includes": deps["direct_includes"][:5],  # Limit to top 5
                    "key_flags": [flag for flag in deps["compile_flags"]
                                if flag.startswith(('-I', '-D', '-std='))]
                }

        context["affected_files"] = list(context["affected_files"])
        return context

    def _parse_build_errors(self, error_log: str) -> List[Dict[str, Any]]:
        """Parse build error log to extract structured error information."""
        errors = []
        lines = error_log.split('\n')

        for line in lines:
            if ':' in line and ('error:' in line or 'Error:' in line):
                # Try to parse GCC/Clang style errors
                parts = line.split(':', 4)
                if len(parts) >= 4:
                    try:
                        file_path = parts[0].strip()
                        line_num = int(parts[1].strip()) if parts[1].strip().isdigit() else None
                        col_num = int(parts[2].strip()) if parts[2].strip().isdigit() else None
                        message = ':'.join(parts[3:]).strip()

                        errors.append({
                            "file": file_path,
                            "line": line_num,
                            "column": col_num,
                            "message": message,
                            "type": "error"
                        })
                    except (ValueError, IndexError):
                        # If parsing fails, just store the raw line
                        errors.append({
                            "file": None,
                            "line": None,
                            "column": None,
                            "message": line.strip(),
                            "type": "error"
                        })

        return errors


class AutoBisectHelper:
    """Automated bisect helper for regression hunting."""

    def __init__(self, repo_path: pathlib.Path):
        self.repo_path = repo_path
        self.git_helper = GitHelper(repo_path)

    def setup_bisect(self, good_ref: str, bad_ref: str, test_command: str) -> Dict[str, Any]:
        """Set up a git bisect session."""
        if not self.git_helper.is_git_repo:
            return {"error": "Not a git repository"}

        bisect_info = {
            "good_ref": good_ref,
            "bad_ref": bad_ref,
            "test_command": test_command,
            "commits_to_test": [],
            "estimated_steps": 0,
            "current_commit": None
        }

        # Get commits between good and bad
        commits = self.git_helper.get_commits_between(good_ref, bad_ref)
        bisect_info["commits_to_test"] = commits
        bisect_info["estimated_steps"] = len(commits).bit_length()  # log2(n) steps

        return bisect_info

    def create_bisect_script(self, test_command: str, output_file: pathlib.Path) -> bool:
        """Create a bisect script that can be used with git bisect run."""
        script_content = f"""#!/bin/bash
# Auto-generated bisect script for llmtk
set -e

echo "Testing commit: $(git rev-parse --short HEAD)"

# Run the test command
{test_command}

# If we get here, the test passed
echo "Test passed"
exit 0
"""

        try:
            with open(output_file, 'w') as f:
                f.write(script_content)
            os.chmod(output_file, 0o755)
            return True
        except IOError:
            return False

    def analyze_bisect_results(self, bisect_log: str) -> Dict[str, Any]:
        """Analyze bisect results and provide context about the regression."""
        # This would parse git bisect log output and provide structured results
        return {
            "regression_commit": None,
            "analysis": "Bisect analysis not yet implemented",
            "affected_files": [],
            "recommended_actions": []
        }


class DiffContextExporter:
    """Main class for exporting diff-oriented context."""

    def __init__(self, project_root: pathlib.Path):
        self.project_root = project_root
        self.git_helper = GitHelper(project_root)
        self.dependency_tracker = DependencyTracker(project_root)
        self.error_analyzer = ErrorContextAnalyzer(project_root)
        self.bisect_helper = AutoBisectHelper(project_root)

    def export_diff_context(self, base_ref: str = "HEAD~1", target_ref: str = "HEAD",
                           include_deps: bool = True, include_errors: bool = False,
                           error_log_path: Optional[str] = None) -> Dict[str, Any]:
        """Export comprehensive diff-oriented context."""

        context = {
            "_meta": {
                "generated_at": time.time(),
                "base_ref": base_ref,
                "target_ref": target_ref,
                "is_git_repo": self.git_helper.is_git_repo,
                "include_dependencies": include_deps,
                "include_errors": include_errors
            },
            "git_info": {},
            "changed_files": [],
            "diffs": {},
            "dependencies": {},
            "errors": {},
            "bisect_info": {}
        }

        if self.git_helper.is_git_repo:
            # Get git information
            context["git_info"] = {
                "base_commit": self.git_helper.get_commit_info(base_ref),
                "target_commit": self.git_helper.get_commit_info(target_ref),
                "commits_between": self.git_helper.get_commits_between(base_ref, target_ref)
            }

            # Get changed files
            changed_files = self.git_helper.get_changed_files(base_ref, target_ref)
            context["changed_files"] = changed_files

            # Get diffs for each file
            for file_path in changed_files:
                diff_content = self.git_helper.get_diff_content(base_ref, target_ref, file_path)
                context["diffs"][file_path] = {
                    "content": diff_content,
                    "size": len(diff_content),
                    "is_source": self.dependency_tracker._is_source_file(file_path)
                }

            # Get minimal dependencies if requested
            if include_deps:
                context["dependencies"] = self.dependency_tracker.get_minimal_context_for_files(changed_files)

        # Analyze errors if provided
        if include_errors and error_log_path:
            try:
                with open(error_log_path, 'r') as f:
                    error_log = f.read()
                context["errors"] = self.error_analyzer.analyze_build_errors(error_log)
            except IOError:
                context["errors"] = {"error": f"Could not read error log: {error_log_path}"}

        return context

    def export_incremental_context(self, cache_file: Optional[str] = None) -> Dict[str, Any]:
        """Export context that focuses only on changes since last export."""
        # Load previous context if cache exists
        previous_context = {}
        if cache_file and pathlib.Path(cache_file).exists():
            try:
                with open(cache_file, 'r') as f:
                    previous_context = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        # Get current HEAD
        current_head = "HEAD"
        if self.git_helper.is_git_repo:
            current_commit = self.git_helper.get_commit_info("HEAD")
            current_head = current_commit.get("hash", "HEAD")

        # Compare with previous head
        previous_head = previous_context.get("_meta", {}).get("current_head")
        base_ref = previous_head if previous_head else "HEAD~1"

        # Export diff context
        context = self.export_diff_context(base_ref, "HEAD", include_deps=True)
        context["_meta"]["current_head"] = current_head
        context["_meta"]["previous_head"] = previous_head
        context["_meta"]["is_incremental"] = True

        # Save cache if requested
        if cache_file:
            try:
                with open(cache_file, 'w') as f:
                    json.dump(context, f, indent=2)
            except IOError:
                pass

        return context


def main():
    """Main entry point for diff context operations."""
    parser = argparse.ArgumentParser(description="Export diff-oriented context for LLM consumption")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Diff context command
    diff_parser = subparsers.add_parser("diff", help="Export diff-based context")
    diff_parser.add_argument("--base", default="HEAD~1", help="Base reference for diff")
    diff_parser.add_argument("--target", default="HEAD", help="Target reference for diff")
    diff_parser.add_argument("--output", "-o", default="exports/diff_context/diff.json", help="Output file")
    diff_parser.add_argument("--include-deps", action="store_true", default=True, help="Include dependency analysis")
    diff_parser.add_argument("--include-errors", action="store_true", help="Include error analysis")
    diff_parser.add_argument("--error-log", help="Path to error log file")

    # Incremental context command
    incr_parser = subparsers.add_parser("incremental", help="Export incremental context")
    incr_parser.add_argument("--cache", default="exports/diff_context/incremental.cache", help="Cache file path")
    incr_parser.add_argument("--output", "-o", default="exports/diff_context/incremental.json", help="Output file")

    # Bisect setup command
    bisect_parser = subparsers.add_parser("bisect", help="Set up automated bisect")
    bisect_parser.add_argument("--good", required=True, help="Good reference")
    bisect_parser.add_argument("--bad", required=True, help="Bad reference")
    bisect_parser.add_argument("--test-cmd", required=True, help="Test command to run")
    bisect_parser.add_argument("--output", "-o", default="exports/diff_context/bisect.json", help="Output file")
    bisect_parser.add_argument("--script", help="Generate bisect script at this path")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    project_root = pathlib.Path.cwd()
    exporter = DiffContextExporter(project_root)

    try:
        if args.command == "diff":
            context = exporter.export_diff_context(
                args.base, args.target,
                args.include_deps, args.include_errors,
                args.error_log
            )

            output_path = pathlib.Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                json.dump(context, f, indent=2)
            print(f"Diff context exported to: {output_path}")

        elif args.command == "incremental":
            context = exporter.export_incremental_context(args.cache)

            output_path = pathlib.Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                json.dump(context, f, indent=2)
            print(f"Incremental context exported to: {output_path}")

        elif args.command == "bisect":
            bisect_info = exporter.bisect_helper.setup_bisect(args.good, args.bad, args.test_cmd)

            output_path = pathlib.Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                json.dump(bisect_info, f, indent=2)
            print(f"Bisect info exported to: {output_path}")

            if args.script:
                script_path = pathlib.Path(args.script)
                if exporter.bisect_helper.create_bisect_script(args.test_cmd, script_path):
                    print(f"Bisect script created at: {script_path}")
                else:
                    print(f"Failed to create bisect script at: {script_path}")

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())