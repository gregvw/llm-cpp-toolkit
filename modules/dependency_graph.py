#!/usr/bin/env python3
"""
CMake dependency graph extraction and export module for llmtk.

This module extracts target dependency graphs from CMake codemodel data
and exports them in JSON and Graphviz formats for LLM consumption.
"""

import argparse
import json
import os
import pathlib
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Optional, Set, Tuple


class DependencyGraphExporter:
    """Extract and export dependency graphs from CMake codemodel data."""

    def __init__(self, build_dir: pathlib.Path, exports_dir: pathlib.Path):
        self.build_dir = build_dir
        self.exports_dir = exports_dir
        self.codemodel_data = None
        self.target_graph = {}
        self.symbol_deps = {}

    def load_codemodel(self) -> bool:
        """Load CMake File API codemodel data."""
        api_dir = self.build_dir / ".cmake/api/v1/reply"
        if not api_dir.exists():
            return False

        # Find the codemodel index file
        codemodel_files = list(api_dir.glob("codemodel-*.json"))
        if not codemodel_files:
            return False

        # Load the most recent codemodel file
        codemodel_file = sorted(codemodel_files)[-1]
        try:
            with open(codemodel_file, 'r') as f:
                self.codemodel_data = json.load(f)
            return True
        except (json.JSONDecodeError, IOError):
            return False

    def extract_target_dependencies(self) -> Dict[str, Any]:
        """Extract target-level dependency information from codemodel."""
        if not self.codemodel_data:
            return {}

        targets = {}
        target_files = {}

        # First pass: collect all target files referenced in codemodel
        for config in self.codemodel_data.get("configurations", []):
            for target_ref in config.get("targets", []):
                target_file = target_ref.get("jsonFile")
                if target_file:
                    target_files[target_ref.get("name", "")] = target_file

        # Second pass: load target details and extract dependencies
        api_dir = self.build_dir / ".cmake/api/v1/reply"
        for target_name, target_file in target_files.items():
            target_path = api_dir / target_file
            if target_path.exists():
                try:
                    with open(target_path, 'r') as f:
                        target_data = json.load(f)

                    target_info = {
                        "name": target_name,
                        "type": target_data.get("type", "UNKNOWN"),
                        "sources": [],
                        "link_libraries": [],
                        "dependencies": [],
                        "compile_definitions": [],
                        "include_directories": [],
                        "install_destination": target_data.get("install", {}).get("prefix"),
                    }

                    # Extract sources
                    for source in target_data.get("sources", []):
                        source_path = source.get("path", "")
                        if source_path:
                            target_info["sources"].append(source_path)

                    # Extract link dependencies
                    for dep in target_data.get("dependencies", []):
                        dep_id = dep.get("id")
                        if dep_id and dep_id in target_files:
                            # This is an internal target dependency
                            target_info["dependencies"].append({
                                "name": dep_id,
                                "type": "internal",
                                "path": None
                            })

                    # Extract link libraries (external dependencies)
                    for link_group in target_data.get("link", {}).get("commandFragments", []):
                        if link_group.get("role") == "libraries":
                            fragment = link_group.get("fragment", "")
                            if fragment:
                                target_info["link_libraries"].append(fragment)

                    # Extract compile definitions
                    for compile_group in target_data.get("compileGroups", []):
                        for define in compile_group.get("defines", []):
                            define_text = define.get("define", "")
                            if define_text:
                                target_info["compile_definitions"].append(define_text)

                        # Extract include directories
                        for include in compile_group.get("includes", []):
                            include_path = include.get("path", "")
                            if include_path:
                                target_info["include_directories"].append(include_path)

                    targets[target_name] = target_info

                except (json.JSONDecodeError, IOError):
                    continue

        self.target_graph = targets
        return targets

    def extract_symbol_dependencies(self) -> Dict[str, Any]:
        """Extract symbol-level dependencies using nm and objdump if available."""
        symbol_deps = {}

        for target_name, target_info in self.target_graph.items():
            if target_info["type"] in ["STATIC_LIBRARY", "SHARED_LIBRARY", "EXECUTABLE"]:
                symbols = self._analyze_target_symbols(target_name, target_info)
                if symbols:
                    symbol_deps[target_name] = symbols

        self.symbol_deps = symbol_deps
        return symbol_deps

    def _analyze_target_symbols(self, target_name: str, target_info: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze symbols for a specific target using available tools."""
        # This would require the actual built targets and symbol analysis tools
        # For now, return a placeholder structure
        return {
            "defined_symbols": [],
            "undefined_symbols": [],
            "exported_symbols": [],
            "symbol_dependencies": []
        }

    def detect_package_managers(self) -> Dict[str, Any]:
        """Detect external package manager lock files and configurations."""
        package_info = {
            "vcpkg": None,
            "conan": None,
            "find_package_calls": []
        }

        # Look for vcpkg
        vcpkg_manifest = pathlib.Path("vcpkg.json")
        if vcpkg_manifest.exists():
            try:
                with open(vcpkg_manifest, 'r') as f:
                    package_info["vcpkg"] = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        # Look for conan
        conan_file = pathlib.Path("conanfile.txt")
        if conan_file.exists():
            try:
                with open(conan_file, 'r') as f:
                    package_info["conan"] = {
                        "type": "conanfile.txt",
                        "content": f.read()
                    }
            except IOError:
                pass

        conan_py = pathlib.Path("conanfile.py")
        if conan_py.exists():
            try:
                with open(conan_py, 'r') as f:
                    package_info["conan"] = {
                        "type": "conanfile.py",
                        "content": f.read()
                    }
            except IOError:
                pass

        # Extract find_package calls from CMake files
        cmake_files = list(pathlib.Path(".").glob("**/CMakeLists.txt")) + list(pathlib.Path(".").glob("**/*.cmake"))
        for cmake_file in cmake_files:
            try:
                with open(cmake_file, 'r') as f:
                    content = f.read()
                    # Simple regex to find find_package calls
                    import re
                    find_packages = re.findall(r'find_package\s*\(\s*([^)]+)\)', content, re.IGNORECASE)
                    for pkg in find_packages:
                        package_info["find_package_calls"].append({
                            "package": pkg.strip(),
                            "file": str(cmake_file)
                        })
            except IOError:
                continue

        return package_info

    def export_json(self, output_file: pathlib.Path) -> bool:
        """Export dependency graph as JSON."""
        try:
            graph_data = {
                "_meta": {
                    "generated_at": pathlib.Path(__file__).stat().st_mtime,
                    "build_dir": str(self.build_dir),
                    "codemodel_available": self.codemodel_data is not None,
                    "targets_count": len(self.target_graph),
                    "symbol_analysis_available": len(self.symbol_deps) > 0
                },
                "targets": self.target_graph,
                "symbol_dependencies": self.symbol_deps,
                "package_managers": self.detect_package_managers(),
                "dependency_matrix": self._build_dependency_matrix(),
                "build_order": self._calculate_build_order()
            }

            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w') as f:
                json.dump(graph_data, f, indent=2)
            return True
        except IOError:
            return False

    def export_graphviz(self, output_file: pathlib.Path) -> bool:
        """Export dependency graph as Graphviz DOT format."""
        try:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w') as f:
                f.write("digraph dependency_graph {\n")
                f.write("  rankdir=LR;\n")
                f.write("  node [shape=box];\n\n")

                # Add nodes
                for target_name, target_info in self.target_graph.items():
                    target_type = target_info["type"]
                    color = self._get_target_color(target_type)
                    f.write(f'  "{target_name}" [color="{color}", label="{target_name}\\n({target_type})"];\n')

                f.write("\n")

                # Add edges
                for target_name, target_info in self.target_graph.items():
                    for dep in target_info["dependencies"]:
                        dep_name = dep["name"]
                        if dep["type"] == "internal":
                            f.write(f'  "{target_name}" -> "{dep_name}";\n')

                f.write("}\n")
            return True
        except IOError:
            return False

    def _get_target_color(self, target_type: str) -> str:
        """Get Graphviz color for target type."""
        colors = {
            "EXECUTABLE": "lightblue",
            "STATIC_LIBRARY": "lightgreen",
            "SHARED_LIBRARY": "orange",
            "INTERFACE_LIBRARY": "yellow",
            "MODULE_LIBRARY": "purple",
            "UTILITY": "gray"
        }
        return colors.get(target_type, "white")

    def _build_dependency_matrix(self) -> List[List[str]]:
        """Build a dependency matrix for easy analysis."""
        target_names = list(self.target_graph.keys())
        matrix = []

        for target in target_names:
            row = []
            target_deps = {dep["name"] for dep in self.target_graph[target]["dependencies"] if dep["type"] == "internal"}
            for dep_target in target_names:
                row.append("1" if dep_target in target_deps else "0")
            matrix.append(row)

        return matrix

    def _calculate_build_order(self) -> List[str]:
        """Calculate a valid build order using topological sort."""
        # Simple topological sort implementation
        in_degree = {target: 0 for target in self.target_graph}

        # Calculate in-degrees
        for target_info in self.target_graph.values():
            for dep in target_info["dependencies"]:
                if dep["type"] == "internal" and dep["name"] in in_degree:
                    in_degree[dep["name"]] += 1

        # Topological sort
        queue = [target for target, degree in in_degree.items() if degree == 0]
        build_order = []

        while queue:
            current = queue.pop(0)
            build_order.append(current)

            # Reduce in-degree for dependent targets
            for dep in self.target_graph[current]["dependencies"]:
                if dep["type"] == "internal" and dep["name"] in in_degree:
                    in_degree[dep["name"]] -= 1
                    if in_degree[dep["name"]] == 0:
                        queue.append(dep["name"])

        return build_order


def main():
    """Main entry point for dependency graph extraction."""
    parser = argparse.ArgumentParser(description="Extract and export CMake dependency graphs")
    parser.add_argument("--build-dir", "-b", default="build", help="CMake build directory")
    parser.add_argument("--output-dir", "-o", default="exports/dependency_graphs", help="Output directory")
    parser.add_argument("--json", action="store_true", help="Export JSON format")
    parser.add_argument("--graphviz", action="store_true", help="Export Graphviz format")
    parser.add_argument("--symbols", action="store_true", help="Include symbol-level analysis")

    args = parser.parse_args()

    build_dir = pathlib.Path(args.build_dir)
    exports_dir = pathlib.Path(args.output_dir)

    if not build_dir.exists():
        print(f"Error: Build directory {build_dir} does not exist", file=sys.stderr)
        return 1

    exporter = DependencyGraphExporter(build_dir, exports_dir)

    # Load codemodel data
    if not exporter.load_codemodel():
        print("Warning: Could not load CMake codemodel data. Make sure to run CMake File API query first.", file=sys.stderr)
        return 1

    # Extract dependencies
    exporter.extract_target_dependencies()

    if args.symbols:
        exporter.extract_symbol_dependencies()

    # Export formats
    success = True
    if args.json or (not args.json and not args.graphviz):  # Default to JSON
        json_file = exports_dir / "dependencies.json"
        if exporter.export_json(json_file):
            print(f"JSON export: {json_file}")
        else:
            print(f"Error: Failed to export JSON to {json_file}", file=sys.stderr)
            success = False

    if args.graphviz:
        dot_file = exports_dir / "dependencies.dot"
        if exporter.export_graphviz(dot_file):
            print(f"Graphviz export: {dot_file}")
        else:
            print(f"Error: Failed to export Graphviz to {dot_file}", file=sys.stderr)
            success = False

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())