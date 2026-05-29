"""Context export command for llmtk."""

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ..core.context import get_exports_dir, get_project_root
from ..core.dry_run import is_dry_run
from ..core.utils import write_json


_FILE_API_QUERIES = ["codemodel-v2", "cache-v2", "cmakeFiles-v1", "toolchains-v1"]
_IMPORTANT_CACHE_KEYS = [
    "CMAKE_BUILD_TYPE",
    "CMAKE_C_COMPILER",
    "CMAKE_C_COMPILER_ID",
    "CMAKE_C_COMPILER_TARGET",
    "CMAKE_C_STANDARD",
    "CMAKE_CXX_COMPILER",
    "CMAKE_CXX_COMPILER_ID",
    "CMAKE_CXX_COMPILER_TARGET",
    "CMAKE_CXX_STANDARD",
    "CMAKE_EXPORT_COMPILE_COMMANDS",
    "CMAKE_GENERATOR",
    "CMAKE_INSTALL_PREFIX",
    "CMAKE_MAKE_PROGRAM",
    "CMAKE_TOOLCHAIN_FILE",
]


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the context command and subcommands."""
    parser = subparsers.add_parser("context", help="Project context operations")
    ctx_subparsers = parser.add_subparsers(dest="context_cmd", required=True)

    export_parser = ctx_subparsers.add_parser(
        "export",
        help="Collect compile commands and CMake File API data"
    )
    export_parser.add_argument(
        "--build",
        default="build",
        help="Build directory to use when no preset is supplied (default: build)"
    )
    export_parser.add_argument(
        "--preset",
        help="Configure preset to use for cmake --preset"
    )
    export_parser.add_argument(
        "--preview",
        action="store_true",
        help="Show planned actions without running cmake"
    )
    export_parser.add_argument(
        "--deep",
        action="store_true",
        help="Generate expanded context with target and toolchain metadata"
    )

    export_parser.set_defaults(func=_handle_export)


def _handle_export(args: argparse.Namespace) -> int:
    project_root = get_project_root()
    exports_dir = get_exports_dir()
    exports_dir.mkdir(exist_ok=True)

    presets = _load_presets(project_root)
    build_dir = _resolve_build_dir(args, project_root, presets)
    if build_dir is None:
        print("Error: Unable to resolve build directory for preset", file=sys.stderr)
        return 1

    plan = _build_plan(args, build_dir)
    if args.preview:
        print("Planned llmtk context export steps:")
        for item in plan:
            print(f"  - {item}")
        return 0

    try:
        _create_file_api_queries(build_dir)
        _run_cmake_configure(args, project_root, build_dir)
        compile_commands = _copy_compile_commands(project_root, build_dir, exports_dir)
        file_api_files, reply_dir = _copy_file_api_replies(build_dir, exports_dir)

        summary = _build_summary(
            project_root=project_root,
            build_dir=build_dir,
            compile_commands=compile_commands,
            file_api_files=file_api_files,
            presets=presets,
            reply_dir=reply_dir,
            deep=args.deep,
            used_configure_preset=args.preset,
        )

        out_path = exports_dir / "context.json"
        write_json(out_path, summary)
        print(str(out_path))
        return 0
    except subprocess.CalledProcessError as exc:
        print(f"Error: cmake command failed with exit code {exc.returncode}", file=sys.stderr)
        if exc.stderr:
            print(exc.stderr.strip(), file=sys.stderr)
        return exc.returncode or 1
    except Exception as exc:  # noqa: BLE001
        print(f"Error exporting context: {exc}", file=sys.stderr)
        return 1


def _build_plan(args: argparse.Namespace, build_dir: Path) -> List[str]:
    plan = []
    if args.preset:
        plan.append(f"Run cmake --preset {args.preset} (CMAKE_EXPORT_COMPILE_COMMANDS=ON)")
    else:
        plan.append(f"Run cmake -S . -B {build_dir} -G Ninja -DCMAKE_EXPORT_COMPILE_COMMANDS=ON")
    plan.append("Copy compile_commands.json into exports/compile_commands.json")
    plan.append("Copy CMake File API replies into exports/cmake-file-api/")
    if args.deep:
        plan.append("Summarize codemodel/toolchains/cache data into exports/context.json")
    else:
        plan.append("Write exports/context.json with basic paths and timestamps")
    return plan


def _load_presets(project_root: Path) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "schema_version": None,
        "files": [],
        "configure": {},
        "build": {},
        "test": {},
        "errors": [],
    }

    for filename in ("CMakePresets.json", "CMakeUserPresets.json"):
        path = project_root / filename
        if not path.exists():
            continue
        result["files"].append(str(path))
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            result["errors"].append(f"{filename}: {exc}")
            continue

        version = data.get("version")
        if version is not None:
            result["schema_version"] = str(version)

        for src_key, dst_key in (
            ("configurePresets", "configure"),
            ("buildPresets", "build"),
            ("testPresets", "test"),
        ):
            presets = data.get(src_key) or []
            if not isinstance(presets, list):
                continue
            for preset in presets:
                name = preset.get("name")
                if not name:
                    continue
                entry = dict(preset)
                entry["_origin"] = filename
                result[dst_key][name] = entry

    return result


def _resolve_build_dir(args: argparse.Namespace, project_root: Path, presets: Dict[str, Any]) -> Optional[Path]:
    if args.preset:
        preset = presets["configure"].get(args.preset)
        if not preset:
            presets["errors"].append(f"configure preset '{args.preset}' not found")
            return None
        binary_dir = preset.get("binaryDir")
        if not binary_dir:
            presets["errors"].append(f"configure preset '{args.preset}' has no binaryDir")
            return None
        return _expand_preset_path(binary_dir, args.preset, project_root)

    return (project_root / args.build).resolve()


def _expand_preset_path(raw: str, preset_name: str, project_root: Path) -> Path:
    replacements = {
        "${sourceDir}": str(project_root),
        "${sourceParentDir}": str(project_root.parent),
        "${sourceDirName}": project_root.name,
        "${presetName}": preset_name,
    }
    expanded = raw
    for key, value in replacements.items():
        expanded = expanded.replace(key, value)

    env_pattern = re.compile(r"\$env\{([^}]+)\}")

    def _env_replace(match: re.Match[str]) -> str:
        return os.environ.get(match.group(1), "")

    expanded = env_pattern.sub(_env_replace, expanded)
    expanded = os.path.expandvars(expanded)

    path = Path(expanded)
    if not path.is_absolute():
        path = (project_root / path).resolve()
    return path


def _create_file_api_queries(build_dir: Path) -> None:
    if is_dry_run():
        return
    query_dir = build_dir / ".cmake" / "api" / "v1" / "query"
    query_dir.mkdir(parents=True, exist_ok=True)
    for name in _FILE_API_QUERIES:
        (query_dir / name).touch()


def _run_cmake_configure(args: argparse.Namespace, project_root: Path, build_dir: Path) -> None:
    if args.preset:
        cmd = ["cmake", "--preset", args.preset, "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON"]
        cwd = project_root
    else:
        cmd = [
            "cmake",
            "-S",
            str(project_root),
            "-B",
            str(build_dir),
            "-G",
            "Ninja",
            "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
        ]
        cwd = None

    if not is_dry_run():
        build_dir.mkdir(parents=True, exist_ok=True)

    subprocess.run(cmd, cwd=cwd, check=True)


def _copy_compile_commands(project_root: Path, build_dir: Path, exports_dir: Path) -> Optional[Path]:
    candidates = [
        build_dir / "compile_commands.json",
        project_root / "compile_commands.json",
    ]
    for source in candidates:
        if source.exists():
            target = exports_dir / "compile_commands.json"
            if not is_dry_run():
                shutil.copy2(source, target)
            return target
    return None


def _copy_file_api_replies(build_dir: Path, exports_dir: Path) -> Tuple[List[str], Path]:
    reply_dir = build_dir / ".cmake" / "api" / "v1" / "reply"
    export_dir = exports_dir / "cmake-file-api"
    export_dir.mkdir(parents=True, exist_ok=True)

    if not is_dry_run():
        for leftover in export_dir.glob("*.json"):
            try:
                leftover.unlink()
            except OSError:
                pass

    files: List[str] = []
    if reply_dir.exists():
        for item in reply_dir.glob("*.json"):
            files.append(item.name)
            if not is_dry_run():
                shutil.copy2(item, export_dir / item.name)

    files.sort()
    return files, reply_dir


def _build_summary(
    *,
    project_root: Path,
    build_dir: Path,
    compile_commands: Optional[Path],
    file_api_files: List[str],
    presets: Dict[str, Any],
    reply_dir: Path,
    deep: bool,
    used_configure_preset: Optional[str],
) -> Dict[str, Any]:
    exports_dir = get_exports_dir()
    compile_commands_rel = None
    if compile_commands and compile_commands.exists():
        compile_commands_rel = str(compile_commands.relative_to(project_root))

    cmake_api_rel = str((exports_dir / "cmake-file-api").relative_to(project_root))
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

    summary: Dict[str, Any] = {
        "compile_commands": compile_commands_rel,
        "cmake_file_api": {
            "dir": cmake_api_rel,
            "files": file_api_files,
            "queries": list(_FILE_API_QUERIES),
        },
        "generated_at": timestamp,
        "_meta": {
            "mode": "deep" if deep else "basic",
            "project_root": str(project_root),
            "build_dir": str(build_dir),
        },
    }

    if used_configure_preset:
        summary["_meta"]["configure_preset"] = used_configure_preset

    if presets.get("schema_version") or presets.get("files"):
        summary.setdefault("_meta", {})["presets_files"] = presets.get("files", [])
        if presets.get("schema_version"):
            summary.setdefault("presets", {})["schema_version"] = presets["schema_version"]

    if presets.get("errors"):
        summary.setdefault("_warnings", []).extend(presets["errors"])

    if not deep:
        return summary

    index_data, index_file = _load_index(reply_dir)
    if index_data is None:
        summary.setdefault("_warnings", []).append("CMake File API index not found; deep summary incomplete")
        return summary

    summary.setdefault("cmake", {})
    summary["cmake"]["index_file"] = index_file

    cmake_info = index_data.get("cmake", {})
    if cmake_info:
        summary["cmake"].update(
            {
                "version": cmake_info.get("version", {}).get("string"),
                "major": cmake_info.get("version", {}).get("major"),
                "minor": cmake_info.get("version", {}).get("minor"),
                "patch": cmake_info.get("version", {}).get("patch"),
                "generator": cmake_info.get("generator"),
            }
        )

    summary["presets"] = _summarize_presets(presets, project_root, used_configure_preset)

    replies = index_data.get("reply", {})
    codemodel = _load_reply_json(reply_dir, replies, "codemodel")
    cache = _load_reply_json(reply_dir, replies, "cache")
    cmake_files = _load_reply_json(reply_dir, replies, "cmakeFiles")
    toolchains = _load_reply_json(reply_dir, replies, "toolchains")

    if codemodel:
        summary["targets"] = _summarize_targets(reply_dir, codemodel)
        summary["build_configurations"] = [cfg.get("name") for cfg in codemodel.get("configurations", [])]
    else:
        summary.setdefault("_warnings", []).append("CMake codemodel reply not available")

    if toolchains:
        summary["toolchains"] = _summarize_toolchains(toolchains)
    else:
        summary.setdefault("_warnings", []).append("Toolchains reply not available")

    if cache:
        summary["cache"] = _summarize_cache(cache)
    else:
        summary.setdefault("_warnings", []).append("Cache reply not available")

    if cmake_files:
        summary["cmake_files"] = _summarize_cmake_files(cmake_files)

    return summary


def _load_index(reply_dir: Path) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    index_files = sorted(reply_dir.glob("index-*.json"))
    if not index_files:
        return None, None
    latest = index_files[-1]
    try:
        return json.loads(latest.read_text()), latest.name
    except json.JSONDecodeError:
        return None, latest.name


def _load_reply_json(reply_dir: Path, replies: Dict[str, Any], key: str) -> Optional[Dict[str, Any]]:
    entry = replies.get(key)
    if not isinstance(entry, dict):
        return None
    json_file = entry.get("jsonFile")
    if not json_file:
        return None
    path = reply_dir / json_file
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None
    except FileNotFoundError:
        return None


def _summarize_presets(
    presets: Dict[str, Any],
    project_root: Path,
    used_configure: Optional[str],
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "schema_version": presets.get("schema_version"),
        "configure": [],
        "build": [],
        "test": [],
    }

    if used_configure:
        result["used_configure"] = used_configure

    for name, preset in presets.get("configure", {}).items():
        binary_dir = preset.get("binaryDir")
        resolved = str(_expand_preset_path(binary_dir, name, project_root)) if binary_dir else None
        result["configure"].append(
            {
                "name": name,
                "generator": preset.get("generator"),
                "binaryDir": binary_dir,
                "binaryDirResolved": resolved,
                "toolchainFile": preset.get("toolchainFile"),
                "hidden": preset.get("hidden", False),
                "origin": preset.get("_origin"),
                "selected": name == used_configure,
            }
        )

    for collection_key in ("build", "test"):
        for name, preset in presets.get(collection_key, {}).items():
            result[collection_key].append(
                {
                    "name": name,
                    "configurePreset": preset.get("configurePreset"),
                    "inheritConfigureEnvironment": preset.get("inheritConfigureEnvironment"),
                    "origin": preset.get("_origin"),
                }
            )

    result["configure"].sort(key=lambda entry: entry["name"])
    result["build"].sort(key=lambda entry: entry["name"])
    result["test"].sort(key=lambda entry: entry["name"])
    return result


def _summarize_targets(reply_dir: Path, codemodel: Dict[str, Any]) -> List[Dict[str, Any]]:
    targets: List[Dict[str, Any]] = []
    for config in codemodel.get("configurations", []):
        config_name = config.get("name")
        for target_ref in config.get("targets", []):
            json_file = target_ref.get("jsonFile")
            if not json_file:
                continue
            path = reply_dir / json_file
            try:
                target_data = json.loads(path.read_text())
            except (json.JSONDecodeError, FileNotFoundError):
                continue

            sources = _collect_sources(target_data)
            includes = _collect_includes(target_data)
            defines = _collect_defines(target_data)
            languages = sorted({grp.get("language") for grp in target_data.get("compileGroups", []) if grp.get("language")})
            dependencies = _collect_dependencies(target_data)
            link_libraries = _collect_link_libraries(target_data)

            targets.append(
                {
                    "configuration": config_name,
                    "name": target_data.get("name"),
                    "id": target_data.get("id"),
                    "type": target_data.get("type"),
                    "artifacts": [artifact.get("path") for artifact in target_data.get("artifacts", []) if artifact.get("path")],
                    "sources": sources,
                    "source_count": len(sources),
                    "include_directories": includes,
                    "include_count": len(includes),
                    "defines": defines,
                    "define_count": len(defines),
                    "languages": languages,
                    "dependencies": dependencies,
                    "link_libraries": link_libraries,
                }
            )

    targets.sort(key=lambda entry: (entry.get("configuration") or "", entry.get("name") or ""))
    return targets


def _collect_sources(target_data: Dict[str, Any]) -> List[str]:
    sources: List[str] = []
    for source in target_data.get("sources", []) or []:
        path = source.get("path")
        if path:
            sources.append(path)
    return _unique_preserve_order(sources)


def _collect_includes(target_data: Dict[str, Any]) -> List[str]:
    includes: List[str] = []
    for group in target_data.get("compileGroups", []) or []:
        for include in group.get("includes", []) or []:
            path = include.get("path")
            if path:
                includes.append(path)
    return _unique_preserve_order(includes)


def _collect_defines(target_data: Dict[str, Any]) -> List[str]:
    defines: List[str] = []
    for group in target_data.get("compileGroups", []) or []:
        for define in group.get("defines", []) or []:
            text = define.get("define")
            if text:
                defines.append(text)
    return _unique_preserve_order(defines)


def _collect_dependencies(target_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    deps: List[Dict[str, Any]] = []
    for dep in target_data.get("dependencies", []) or []:
        dep_id = dep.get("id")
        if dep_id:
            deps.append({"id": dep_id, "path": dep.get("path")})
    return deps


def _collect_link_libraries(target_data: Dict[str, Any]) -> List[str]:
    libs: List[str] = []
    for fragment in target_data.get("link", {}).get("commandFragments", []) or []:
        if fragment.get("role") == "libraries" and fragment.get("fragment"):
            libs.append(fragment["fragment"])
    return _unique_preserve_order(libs)


def _summarize_toolchains(toolchains: Dict[str, Any]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for entry in toolchains.get("toolchains", []) or []:
        compiler = entry.get("compiler", {})
        target_system = entry.get("targetSystem", {})
        result.append(
            {
                "language": entry.get("language"),
                "compiler_id": compiler.get("id"),
                "compiler_path": compiler.get("path"),
                "compiler_version": compiler.get("version"),
                "is_cross_compiling": entry.get("isCrossCompiling"),
                "target_system": {
                    "name": target_system.get("name"),
                    "version": target_system.get("version"),
                    "platform": target_system.get("platform"),
                },
            }
        )

    result.sort(key=lambda entry: entry.get("language") or "")
    return result


def _summarize_cache(cache: Dict[str, Any]) -> Dict[str, Any]:
    entries = cache.get("entries", []) or []
    cache_map = {entry.get("name"): entry.get("value") for entry in entries if entry.get("name")}
    summary = {key: cache_map.get(key) for key in _IMPORTANT_CACHE_KEYS if key in cache_map}
    summary["entry_count"] = len(entries)
    return summary


def _summarize_cmake_files(cmake_files: Dict[str, Any]) -> Dict[str, Any]:
    inputs = cmake_files.get("inputs", []) or []
    cmake_lists = []
    modules = []
    for entry in inputs:
        kind = entry.get("kind")
        path = entry.get("path")
        if not path:
            continue
        if kind == "cmakeLists":
            cmake_lists.append(path)
        elif kind == "cmake":
            modules.append(path)
    return {
        "cmake_lists": _unique_preserve_order(cmake_lists),
        "modules": _unique_preserve_order(modules),
        "total_inputs": len(inputs),
    }


def _unique_preserve_order(items: Iterable[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered
