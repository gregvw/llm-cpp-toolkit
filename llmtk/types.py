"""Common type definitions for llmtk."""

from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple, Union
import pathlib

# Common type aliases
PathLike = Union[str, pathlib.Path]
JsonValue = Union[str, int, float, bool, None, Dict[str, Any], List[Any]]
JsonDict = Dict[str, JsonValue]
CommandArgs = Union[List[str], Tuple[str, ...]]