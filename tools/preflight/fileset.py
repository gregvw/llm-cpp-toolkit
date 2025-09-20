"""
File discovery module for llmtk preflight

Handles file discovery based on --diff, --since, and --paths options.
"""

import pathlib
import subprocess
import sys
from typing import List, Set, Optional


def run_git_command(cmd: List[str], cwd: Optional[pathlib.Path] = None) -> List[str]:
    """Run a git command and return output lines, or empty list on failure."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd or pathlib.Path.cwd(),
            capture_output=True,
            text=True,
            check=True
        )
        return [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []


def get_git_diff_files(base_ref: str, target_ref: Optional[str] = None, cwd: Optional[pathlib.Path] = None) -> List[str]:
    """Get list of files that differ between git references."""
    if target_ref:
        cmd = ["git", "diff", "--name-only", f"{base_ref}...{target_ref}"]
    else:
        cmd = ["git", "diff", "--name-only", base_ref]
    return run_git_command(cmd, cwd)


def get_git_changed_files_since(since_ref: str, cwd: Optional[pathlib.Path] = None) -> List[str]:
    """Get list of files changed since a reference."""
    cmd = ["git", "diff", "--name-only", f"{since_ref}..HEAD"]
    return run_git_command(cmd, cwd)


def get_git_status_files(cwd: Optional[pathlib.Path] = None) -> List[str]:
    """Get list of modified files in working directory."""
    cmd = ["git", "status", "--porcelain=v1"]
    lines = run_git_command(cmd, cwd)
    files = []
    for line in lines:
        if len(line) >= 3:
            # Format: XY filename
            # Skip deleted files (D), focus on modified/added/renamed
            status = line[:2]
            if 'D' not in status:
                files.append(line[3:])
    return files


def filter_existing_files(files: List[str], cwd: Optional[pathlib.Path] = None) -> List[pathlib.Path]:
    """Filter to only existing files and return as Path objects."""
    base_path = cwd or pathlib.Path.cwd()
    existing = []
    for file_str in files:
        file_path = base_path / file_str
        if file_path.exists() and file_path.is_file():
            existing.append(file_path)
    return existing


def filter_by_extensions(files: List[pathlib.Path], extensions: Set[str]) -> List[pathlib.Path]:
    """Filter files by file extensions."""
    if not extensions:
        return files

    filtered = []
    for file_path in files:
        suffix = file_path.suffix.lower()
        if suffix in extensions:
            filtered.append(file_path)
    return filtered


def discover_files(
    diff_base: Optional[str] = None,
    diff_target: Optional[str] = None,
    since_ref: Optional[str] = None,
    explicit_paths: Optional[List[str]] = None,
    include_working_changes: bool = True,
    max_files: Optional[int] = None,
    extensions: Optional[Set[str]] = None
) -> List[pathlib.Path]:
    """
    Discover files to check based on the provided criteria.

    Args:
        diff_base: Base reference for git diff
        diff_target: Target reference for git diff (optional)
        since_ref: Reference to get changes since
        explicit_paths: Explicit list of file paths
        include_working_changes: Include unstaged/staged changes
        max_files: Maximum number of files to return
        extensions: Set of file extensions to include (e.g., {'.cpp', '.h', '.py'})

    Returns:
        List of Path objects for files to check
    """
    files: Set[str] = set()
    cwd = pathlib.Path.cwd()

    # Explicit paths take precedence
    if explicit_paths:
        for path_str in explicit_paths:
            path = pathlib.Path(path_str)
            if path.is_file():
                files.add(str(path.relative_to(cwd) if path.is_absolute() else path))
            elif path.is_dir():
                # Add all files in directory recursively
                for file_path in path.rglob('*'):
                    if file_path.is_file():
                        files.add(str(file_path.relative_to(cwd)))

    # Git diff between references
    elif diff_base:
        git_files = get_git_diff_files(diff_base, diff_target, cwd)
        files.update(git_files)

    # Git changes since reference
    elif since_ref:
        git_files = get_git_changed_files_since(since_ref, cwd)
        files.update(git_files)

    # Include working directory changes if requested
    if include_working_changes and not explicit_paths:
        working_files = get_git_status_files(cwd)
        files.update(working_files)

    # Default: check working directory changes only
    if not files and not explicit_paths and not diff_base and not since_ref:
        working_files = get_git_status_files(cwd)
        files.update(working_files)

        # If no git changes, fallback to common source patterns
        if not working_files:
            common_patterns = ['src/**/*', 'include/**/*', '*.cpp', '*.h', '*.hpp', '*.c']
            for pattern in common_patterns:
                for path in cwd.glob(pattern):
                    if path.is_file():
                        files.add(str(path.relative_to(cwd)))

    # Filter to existing files and convert to Path objects
    existing_files = filter_existing_files(list(files), cwd)

    # Filter by extensions if specified
    if extensions:
        existing_files = filter_by_extensions(existing_files, extensions)

    # Apply max files limit
    if max_files and len(existing_files) > max_files:
        existing_files = existing_files[:max_files]

    return existing_files


def get_supported_extensions() -> Set[str]:
    """Return set of file extensions supported by preflight checkers."""
    return {
        # C/C++
        '.c', '.cpp', '.cxx', '.cc', '.C', '.c++',
        '.h', '.hpp', '.hxx', '.hh', '.H', '.h++',

        # CMake
        '.cmake', '.txt',  # CMakeLists.txt will be caught by name

        # Data formats
        '.json', '.yaml', '.yml', '.toml',

        # Documentation
        '.md', '.rst',

        # Scripts
        '.sh', '.bash', '.py',

        # Config files
        '.ini', '.cfg', '.conf'
    }


def should_check_file(file_path: pathlib.Path) -> bool:
    """Determine if a file should be checked by preflight."""
    # Check by extension
    if file_path.suffix.lower() in get_supported_extensions():
        return True

    # Check by name patterns
    name = file_path.name.lower()
    name_patterns = {
        'cmakelists.txt',
        'makefile',
        'dockerfile',
        '.clang-tidy',
        '.clang-format'
    }

    return name in name_patterns