"""Bootstrap helper for installing and running llmtk from verified releases."""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("llm-cpp-toolkit")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0.dev0"

__all__ = ["__version__"]
