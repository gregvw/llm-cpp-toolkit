"""Jinja2-based project scaffolding for ``llmtk init``.

This renders *scaffold* files only — CMake, sources, .gitignore, CMake presets.
Runtime JSON artifacts, MCP responses, and capabilities output are deliberately
NOT templated; those remain generated in plain Python.

Jinja2 is imported lazily so importing this module never fails; the import error
is only raised (with an actionable message) when a render is actually attempted.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List

from ..core.context import get_root

# Templates live in the toolkit tree (shipped in the release tarball), not in the
# bootstrap wheel.
SCAFFOLD_SUBDIR = "templates/scaffold"

# Maps the existing ``--preset`` choices onto explicit, inspectable build
# profiles. Adding a preset here is the only place that needs to change.
_PRESET_PROFILES: Dict[str, Dict[str, object]] = {
    "minimal": {"target_type": "executable", "enable_tests": False, "enable_sanitizers": False, "pic": False},
    "executable": {"target_type": "executable", "enable_tests": True, "enable_sanitizers": False, "pic": False},
    "library": {"target_type": "library", "enable_tests": True, "enable_sanitizers": False, "pic": True},
    "full": {"target_type": "executable", "enable_tests": True, "enable_sanitizers": True, "pic": False},
}

# Template file -> output path relative to the project root.
_TEMPLATE_OUTPUTS: Dict[str, str] = {
    "CMakeLists.txt.j2": "CMakeLists.txt",
    "main.cpp.j2": "src/main.cpp",
    "gitignore.j2": ".gitignore",
    "CMakePresets.json.j2": "CMakePresets.json",
}


@dataclass(frozen=True)
class ScaffoldContext:
    """The single context model shared by every scaffold template."""

    project_name: str
    cpp_standard: str
    cmake_minimum: str
    target_type: str  # "executable" | "library"
    enable_tests: bool
    enable_sanitizers: bool
    pic: bool

    def as_dict(self) -> Dict[str, object]:
        return asdict(self)


def available_presets() -> List[str]:
    """Return the known ``--preset`` names."""
    return list(_PRESET_PROFILES)


def context_from_preset(
    project_name: str,
    *,
    preset: str = "executable",
    cpp_standard: str = "17",
    cmake_minimum: str = "3.20",
) -> ScaffoldContext:
    """Build a :class:`ScaffoldContext` from the init flags and a preset name."""
    profile = _PRESET_PROFILES.get(preset, _PRESET_PROFILES["executable"])
    return ScaffoldContext(
        project_name=project_name,
        cpp_standard=str(cpp_standard),
        cmake_minimum=str(cmake_minimum),
        target_type=str(profile["target_type"]),
        enable_tests=bool(profile["enable_tests"]),
        enable_sanitizers=bool(profile["enable_sanitizers"]),
        pic=bool(profile["pic"]),
    )


def _build_environment():
    """Create a Jinja2 environment with StrictUndefined over the scaffold dir."""
    try:
        from jinja2 import Environment, FileSystemLoader, StrictUndefined
    except ImportError as exc:  # pragma: no cover - exercised via message
        raise RuntimeError(
            "llmtk init requires Jinja2 for project scaffolding. "
            "Install it with 'pip install jinja2' (it ships as a dependency of "
            "llm-cpp-toolkit)."
        ) from exc

    scaffold_dir = get_root() / SCAFFOLD_SUBDIR
    return Environment(
        loader=FileSystemLoader(str(scaffold_dir)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=False,
    )


def render_scaffold(ctx: ScaffoldContext, dest: Path) -> List[Path]:
    """Render every scaffold template into ``dest`` and return the files written."""
    env = _build_environment()
    values = ctx.as_dict()
    dest = Path(dest)

    written: List[Path] = []
    for template_name, rel_out in _TEMPLATE_OUTPUTS.items():
        rendered = env.get_template(template_name).render(**values)
        out_path = dest / rel_out
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered, encoding="utf-8")
        written.append(out_path)
    return written
