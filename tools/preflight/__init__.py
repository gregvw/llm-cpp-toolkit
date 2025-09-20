"""
llmtk preflight - Fast syntax and delimiter checking before build operations

This module implements a language-aware sanity pass that audits delimiters,
quotes, and runs cheap syntax checks across changed files, designed to catch
common LLM-induced errors before expensive compilation.
"""

__version__ = "1.0.0"
__author__ = "llmtk contributors"

from .main import main, PreflightArgs
from .fileset import discover_files
from .reporters import Finding, output_json, output_sarif, output_human

__all__ = [
    "main",
    "PreflightArgs",
    "discover_files",
    "Finding",
    "output_json",
    "output_sarif",
    "output_human"
]