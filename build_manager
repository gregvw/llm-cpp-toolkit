#!/usr/bin/env python3
"""
Build Manager for C++/CMake projects
Provides LLM-friendly output while preserving full build logs
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class BuildResult:
    def __init__(self, success: bool, summary: str, details: Optional[Dict] = None):
        self.success = success
        self.summary = summary
        self.details = details or {}
        self.timestamp = datetime.now().isoformat()


class BuildManager:
    def __init__(self, source_dir: str = ".", build_dir: str = "build", log_dir: str = "logs"):
        self.source_dir = Path(source_dir).resolve()
        self.build_dir = Path(build_dir).resolve()
        self.log_dir = Path(log_dir).resolve()
        self.log_dir.mkdir(exist_ok=True)

    def _run_command(self, cmd: List[str], cwd: Optional[Path] = None,
                    capture_output: bool = True) -> Tuple[int, str, str]:
        """Run command and capture output"""
        if cwd is None:
            cwd = self.source_dir

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            universal_newlines=True,
            bufsize=1
        )

        stdout, stderr = process.communicate()
        return process.returncode, stdout, stderr

    def _save_log(self, name: str, content: str, structured_data: Optional[Dict] = None):
        """Save log file with timestamp"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save raw log
        log_file = self.log_dir / f"{name}_{timestamp}.log"
        with open(log_file, 'w') as f:
            f.write(content)

        # Save structured data if provided
        if structured_data:
            json_file = self.log_dir / f"{name}_{timestamp}.json"
            with open(json_file, 'w') as f:
                json.dump(structured_data, f, indent=2)

    def _parse_cmake_errors(self, stderr: str) -> List[Dict]:
        """Parse CMake configuration errors"""
        errors = []

        # CMake error patterns
        error_patterns = [
            r"CMake Error.*?: (.+)",
            r"ERROR: (.+)",
            r"FATAL_ERROR: (.+)",
        ]

        for line in stderr.split('\n'):
            line = line.strip()
            if not line:
                continue

            for pattern in error_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    errors.append({
                        'type': 'cmake_error',
                        'message': match.group(1).strip(),
                        'full_line': line
                    })
                    break

        return errors

    def _parse_compiler_errors(self, stderr: str) -> List[Dict]:
        """Parse clang/gcc compiler errors and warnings"""
        errors = []

        # Clang/GCC error pattern: file:line:column: error/warning: message
        error_pattern = r'(.+?):(\d+):(\d+):\s+(error|warning|note):\s+(.+)'

        for line in stderr.split('\n'):
            line = line.strip()
            if not line:
                continue

            match = re.match(error_pattern, line)
            if match:
                file_path, line_num, col_num, severity, message = match.groups()

                errors.append({
                    'type': 'compiler_diagnostic',
                    'severity': severity,
                    'file': file_path,
                    'line': int(line_num),
                    'column': int(col_num),
                    'message': message.strip(),
                    'full_line': line
                })

        return errors

    def _parse_test_results(self, output: str) -> Tuple[List[Dict], Dict]:
        """Parse CTest output for failed tests"""
        failed_tests = []
        summary = {'total': 0, 'passed': 0, 'failed': 0}

        # CTest patterns
        test_result_pattern = r'(\d+/\d+)\s+Test\s+#\d+:\s+(.+?)\s+\.+\s*(Passed|FAILED|.*Exception.*|.*Subprocess aborted.*)'
        summary_pattern = r'(\d+)% tests passed, (\d+) tests failed out of (\d+)'
        failed_test_list_pattern = r'\s*(\d+)\s+-\s+(.+?)\s+\('

        lines = output.split('\n')
        in_failed_section = False

        for line in lines:
            line_stripped = line.strip()

            # Individual test results (running tests)
            match = re.search(test_result_pattern, line)
            if match:
                test_num, test_name, status = match.groups()
                if 'Exception' in status or 'aborted' in status or status == 'FAILED':
                    failed_tests.append({
                        'name': test_name.strip(),
                        'test_number': test_num,
                        'status': 'FAILED',
                        'full_line': line
                    })

            # Summary line
            match = re.search(summary_pattern, line_stripped)
            if match:
                percent_passed, failed_count, total_count = match.groups()
                summary = {
                    'total': int(total_count),
                    'failed': int(failed_count),
                    'passed': int(total_count) - int(failed_count)
                }

            # Check for "The following tests FAILED:" section
            if 'The following tests FAILED:' in line:
                in_failed_section = True
                continue

            # Parse failed test entries in the FAILED section
            if in_failed_section:
                match = re.search(failed_test_list_pattern, line)
                if match:
                    test_id, test_name = match.groups()
                    # Check if we already have this test, if not add it
                    if not any(t.get('name') == test_name.strip() for t in failed_tests):
                        failed_tests.append({
                            'name': test_name.strip(),
                            'test_number': test_id,
                            'status': 'FAILED',
                            'full_line': line.strip()
                        })
                elif line_stripped == "":
                    in_failed_section = False

        return failed_tests, summary

    def configure(self, cmake_args: Optional[List[str]] = None) -> BuildResult:
        """Configure project with CMake"""
        print("🔧 Configuring project...")

        self.build_dir.mkdir(exist_ok=True)

        cmd = ["cmake", "-S", str(self.source_dir), "-B", str(self.build_dir)]
        if cmake_args:
            cmd.extend(cmake_args)

        returncode, stdout, stderr = self._run_command(cmd)

        full_output = f"STDOUT:\n{stdout}\n\nSTDERR:\n{stderr}"
        self._save_log("cmake_configure", full_output)

        if returncode == 0:
            return BuildResult(True, "✅ Configure successful")
        else:
            errors = self._parse_cmake_errors(stderr)
            if errors:
                first_error = errors[0]['message']
                summary = f"❌ Configure failed: {first_error}"
                if len(errors) > 1:
                    summary += f" (and {len(errors)-1} more error{'s' if len(errors)>2 else ''})"
            else:
                summary = "❌ Configure failed (see logs for details)"

            return BuildResult(False, summary, {'errors': errors})

    def build(self, target: Optional[str] = None, jobs: Optional[int] = None) -> BuildResult:
        """Build the project"""
        print("🔨 Building project...")

        cmd = ["cmake", "--build", str(self.build_dir)]
        if target:
            cmd.extend(["--target", target])
        if jobs:
            cmd.extend(["--parallel", str(jobs)])

        returncode, stdout, stderr = self._run_command(cmd)

        full_output = f"STDOUT:\n{stdout}\n\nSTDERR:\n{stderr}"
        self._save_log("build", full_output)

        if returncode == 0:
            return BuildResult(True, "✅ Build successful")
        else:
            errors = self._parse_compiler_errors(stderr)

            # Filter to show only errors (not warnings) for summary
            actual_errors = [e for e in errors if e['severity'] == 'error']

            if actual_errors:
                first_error = actual_errors[0]
                file_ref = f"{Path(first_error['file']).name}:{first_error['line']}"
                summary = f"❌ Build failed: {file_ref}: {first_error['message']}"
                if len(actual_errors) > 1:
                    summary += f" (and {len(actual_errors)-1} more error{'s' if len(actual_errors)>2 else ''})"
            else:
                summary = "❌ Build failed (see logs for details)"

            return BuildResult(False, summary, {'errors': errors})

    def test(self, test_pattern: Optional[str] = None, verbose: bool = False) -> BuildResult:
        """Run tests with CTest"""
        print("🧪 Running tests...")

        cmd = ["ctest", "--test-dir", str(self.build_dir)]
        if test_pattern:
            cmd.extend(["-R", test_pattern])
        if verbose:
            cmd.append("--verbose")

        returncode, stdout, stderr = self._run_command(cmd)

        full_output = f"STDOUT:\n{stdout}\n\nSTDERR:\n{stderr}"
        self._save_log("test", full_output)

        failed_tests, summary = self._parse_test_results(stdout)

        if returncode == 0 and summary['failed'] == 0:
            return BuildResult(True, f"✅ All {summary['total']} tests passed")
        else:
            if failed_tests:
                failed_names = [t['name'] for t in failed_tests[:3]]  # Show first 3
                summary_msg = f"❌ {summary['failed']}/{summary['total']} tests failed: {', '.join(failed_names)}"
                if len(failed_tests) > 3:
                    summary_msg += f" (and {len(failed_tests)-3} more)"
            else:
                summary_msg = f"❌ {summary['failed']}/{summary['total']} tests failed (see logs for details)"

            return BuildResult(False, summary_msg, {
                'failed_tests': failed_tests,
                'summary': summary
            })

    def clean(self) -> BuildResult:
        """Clean build directory"""
        print("🧹 Cleaning build directory...")

        if self.build_dir.exists():
            import shutil
            shutil.rmtree(self.build_dir)

        return BuildResult(True, "✅ Clean successful")

    def full_build(self, cmake_args: Optional[List[str]] = None,
                   build_target: Optional[str] = None,
                   run_tests: bool = True) -> List[BuildResult]:
        """Run full configure -> build -> test cycle"""
        results = []

        # Configure
        config_result = self.configure(cmake_args)
        results.append(config_result)
        if not config_result.success:
            return results

        # Build
        build_result = self.build(build_target)
        results.append(build_result)
        if not build_result.success:
            return results

        # Test (if requested)
        if run_tests:
            test_result = self.test()
            results.append(test_result)

        return results


def main():
    parser = argparse.ArgumentParser(description="LLM-friendly C++/CMake build manager")
    parser.add_argument("--source-dir", default=".", help="Source directory")
    parser.add_argument("--build-dir", default="build", help="Build directory")
    parser.add_argument("--log-dir", default="logs", help="Log directory")

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Configure command
    config_parser = subparsers.add_parser("configure", help="Configure with CMake")
    config_parser.add_argument("cmake_args", nargs="*", help="Additional CMake arguments")

    # Build command
    build_parser = subparsers.add_parser("build", help="Build project")
    build_parser.add_argument("--target", help="Build specific target")
    build_parser.add_argument("--jobs", "-j", type=int, help="Number of parallel jobs")

    # Test command
    test_parser = subparsers.add_parser("test", help="Run tests")
    test_parser.add_argument("--pattern", "-R", help="Test name pattern")
    test_parser.add_argument("--verbose", "-V", action="store_true", help="Verbose output")

    # Clean command
    subparsers.add_parser("clean", help="Clean build directory")

    # Full build command
    full_parser = subparsers.add_parser("full", help="Configure, build, and test")
    full_parser.add_argument("--no-tests", action="store_true", help="Skip running tests")
    full_parser.add_argument("--target", help="Build specific target")
    full_parser.add_argument("cmake_args", nargs="*", help="Additional CMake arguments")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    manager = BuildManager(args.source_dir, args.build_dir, args.log_dir)

    try:
        if args.command == "configure":
            result = manager.configure(args.cmake_args if args.cmake_args else None)
            print(result.summary)
            return 0 if result.success else 1

        elif args.command == "build":
            result = manager.build(args.target, args.jobs)
            print(result.summary)
            return 0 if result.success else 1

        elif args.command == "test":
            result = manager.test(args.pattern, args.verbose)
            print(result.summary)
            return 0 if result.success else 1

        elif args.command == "clean":
            result = manager.clean()
            print(result.summary)
            return 0 if result.success else 1

        elif args.command == "full":
            results = manager.full_build(
                args.cmake_args if args.cmake_args else None,
                args.target,
                not args.no_tests
            )

            for result in results:
                print(result.summary)
                if not result.success:
                    return 1

            return 0

    except KeyboardInterrupt:
        print("\n❌ Build interrupted")
        return 130
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())