"""
LLM C++ Toolkit - A comprehensive CLI toolkit for AI-assisted C++ development.

This package provides standardized environment checks, context export, code analysis,
and repro reduction with JSON outputs optimized for AI consumption.
"""

__version__ = "1.0.0"
__author__ = "Greg VanWoerkom"
__email__ = "greg@vanwoerkom.org"

from .cli import main

__all__ = ["main"]