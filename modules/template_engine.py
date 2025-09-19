#!/usr/bin/env python3
"""
Template Engine for LLM C++ Toolkit
Handles template loading, inheritance, and configuration resolution.
"""

import yaml
import pathlib
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
import copy


@dataclass
class TemplateConfig:
    """Configuration for a template"""
    name: str
    description: str
    type: str  # base, security, domain
    inherits: Optional[str] = None
    settings: Dict[str, Any] = field(default_factory=dict)
    overrides: Dict[str, Any] = field(default_factory=dict)
    compiler_flags: List[str] = field(default_factory=list)
    linker_flags: List[str] = field(default_factory=list)
    cmake_options: List[str] = field(default_factory=list)
    cmake_template: Optional[str] = None
    cmake_template_additions: Optional[str] = None
    files: List[Dict[str, str]] = field(default_factory=list)
    libraries: Dict[str, List[str]] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    clang_tidy_checks: Dict[str, List[str]] = field(default_factory=dict)
    documentation: Optional[str] = None


class TemplateEngine:
    """Engine for loading and resolving template configurations"""

    def __init__(self, template_dir: pathlib.Path, manifest_dir: pathlib.Path):
        self.template_dir = template_dir
        self.manifest_dir = manifest_dir
        self.templates: Dict[str, TemplateConfig] = {}
        self.toggles: Dict[str, Dict[str, Any]] = {}
        self._load_templates()
        self._load_toggles()

    def _load_templates(self):
        """Load all template files from the templates directory"""
        template_paths = [
            self.template_dir / "base",
            self.template_dir / "security",
            self.template_dir / "domain"
        ]

        for template_path in template_paths:
            if template_path.exists():
                for yaml_file in template_path.glob("*.yaml"):
                    self._load_template_file(yaml_file)

    def _load_template_file(self, yaml_file: pathlib.Path):
        """Load a single template file"""
        try:
            with open(yaml_file, 'r') as f:
                data = yaml.safe_load(f)

            template = TemplateConfig(
                name=data.get('name', yaml_file.stem),
                description=data.get('description', ''),
                type=data.get('type', 'base'),
                inherits=data.get('inherits'),
                settings=data.get('settings', {}),
                overrides=data.get('overrides', {}),
                compiler_flags=data.get('compiler_flags', []),
                linker_flags=data.get('linker_flags', []),
                cmake_options=data.get('cmake_options', []),
                cmake_template=data.get('cmake_template'),
                cmake_template_additions=data.get('cmake_template_additions'),
                files=data.get('files', []),
                libraries=data.get('libraries', {}),
                dependencies=data.get('dependencies', []),
                clang_tidy_checks=data.get('clang_tidy_checks', {}),
                documentation=data.get('documentation')
            )

            self.templates[template.name] = template

        except Exception as e:
            print(f"Warning: Failed to load template {yaml_file}: {e}")

    def _load_toggles(self):
        """Load toggle definitions from templates.yaml manifest"""
        templates_manifest = self.manifest_dir / "templates.yaml"
        if templates_manifest.exists():
            try:
                with open(templates_manifest, 'r') as f:
                    data = yaml.safe_load(f)
                self.toggles = data.get('toggles', {})
            except Exception as e:
                print(f"Warning: Failed to load toggles from {templates_manifest}: {e}")

    def get_available_presets(self) -> List[str]:
        """Get list of all available preset names"""
        # Include legacy presets for backwards compatibility
        legacy = ["minimal", "full", "library"]
        custom = list(self.templates.keys())
        return legacy + [name for name in custom if name not in legacy]

    def resolve_template(self, preset_name: str, user_overrides: Optional[Dict[str, Any]] = None) -> TemplateConfig:
        """Resolve a template with inheritance and user overrides"""
        user_overrides = user_overrides or {}

        # Handle legacy presets
        if preset_name in ["minimal", "full", "library"]:
            return self._create_legacy_template(preset_name, user_overrides)

        if preset_name not in self.templates:
            raise ValueError(f"Unknown preset: {preset_name}")

        # Build inheritance chain
        inheritance_chain = self._build_inheritance_chain(preset_name)

        # Resolve template by merging inheritance chain
        resolved = self._merge_templates(inheritance_chain)

        # Apply user overrides
        self._apply_user_overrides(resolved, user_overrides)

        return resolved

    def _build_inheritance_chain(self, preset_name: str) -> List[str]:
        """Build the inheritance chain for a preset"""
        chain = []
        current = preset_name

        while current:
            if current in chain:
                raise ValueError(f"Circular inheritance detected: {' -> '.join(chain + [current])}")

            chain.append(current)

            if current not in self.templates:
                # Check if it's a legacy preset
                if current in ["minimal", "full", "library"]:
                    break
                raise ValueError(f"Template not found: {current}")

            current = self.templates[current].inherits

        return list(reversed(chain))  # Base template first

    def _merge_templates(self, inheritance_chain: List[str]) -> TemplateConfig:
        """Merge templates in inheritance order"""
        if not inheritance_chain:
            raise ValueError("Empty inheritance chain")

        # Start with base template
        base_name = inheritance_chain[0]
        if base_name in self.templates:
            result = copy.deepcopy(self.templates[base_name])
        else:
            # Legacy template
            result = self._create_legacy_template(base_name)

        # Merge each template in the chain
        for template_name in inheritance_chain[1:]:
            if template_name in self.templates:
                template = self.templates[template_name]
                result = self._merge_template_configs(result, template)

        return result

    def _merge_template_configs(self, base: TemplateConfig, overlay: TemplateConfig) -> TemplateConfig:
        """Merge two template configurations"""
        # Merge settings (overlay overrides base)
        base.settings.update(overlay.settings)
        base.settings.update(overlay.overrides)  # overrides take precedence

        # Merge lists (concatenate)
        base.compiler_flags.extend(overlay.compiler_flags)
        base.linker_flags.extend(overlay.linker_flags)
        base.cmake_options.extend(overlay.cmake_options)
        base.dependencies.extend(overlay.dependencies)
        base.files.extend(overlay.files)

        # Merge dictionaries
        for key, value in overlay.libraries.items():
            if key in base.libraries:
                base.libraries[key].extend(value)
            else:
                base.libraries[key] = value

        # Merge clang-tidy checks
        for action, checks in overlay.clang_tidy_checks.items():
            if action in base.clang_tidy_checks:
                base.clang_tidy_checks[action].extend(checks)
            else:
                base.clang_tidy_checks[action] = checks

        # Template additions (concatenate)
        if overlay.cmake_template_additions:
            if base.cmake_template_additions:
                base.cmake_template_additions += "\n\n" + overlay.cmake_template_additions
            else:
                base.cmake_template_additions = overlay.cmake_template_additions

        # Use overlay template if provided
        if overlay.cmake_template:
            base.cmake_template = overlay.cmake_template

        # Update metadata (overlay takes precedence)
        base.name = overlay.name  # Use the overlay template's name
        base.description = overlay.description or base.description
        base.documentation = overlay.documentation or base.documentation

        return base

    def _apply_user_overrides(self, template: TemplateConfig, user_overrides: Dict[str, Any]):
        """Apply user-specified overrides to template"""
        # Apply toggle values
        for toggle_name, value in user_overrides.items():
            if toggle_name in self.toggles:
                self._apply_toggle(template, toggle_name, value)
            else:
                # Direct setting override
                template.settings[toggle_name] = value

    def _apply_toggle(self, template: TemplateConfig, toggle_name: str, value: Any):
        """Apply a specific toggle to template configuration"""
        toggle_config = self.toggles[toggle_name]

        # Validate toggle value
        valid_values = toggle_config.get('values', [])
        if valid_values and value not in valid_values:
            raise ValueError(f"Invalid value '{value}' for toggle '{toggle_name}'. Valid values: {valid_values}")

        # Apply toggle effects
        template.settings[toggle_name] = value

        # Apply compiler flags
        if 'compiler_flags' in toggle_config:
            flags = toggle_config['compiler_flags']
            if isinstance(flags, dict):
                if value in flags:
                    template.compiler_flags.extend(flags[value])
            else:
                template.compiler_flags.extend(flags)

        # Apply CMake options
        if 'cmake_flag' in toggle_config:
            cmake_flag = toggle_config['cmake_flag']
            template.cmake_options.append(f"{cmake_flag}={'ON' if value else 'OFF'}")

        # Apply dependencies
        if 'dependencies' in toggle_config:
            deps = toggle_config['dependencies']
            if isinstance(deps, dict):
                if value in deps:
                    template.dependencies.extend(deps[value])
            else:
                template.dependencies.extend(deps)

    def _create_legacy_template(self, preset_name: str, user_overrides: Optional[Dict[str, Any]] = None) -> TemplateConfig:
        """Create a legacy template for backwards compatibility"""
        user_overrides = user_overrides or {}

        base_settings = {
            "sanitizers": preset_name != "minimal",
            "target_type": "library" if preset_name == "library" else "executable",
            "lint_support": preset_name != "minimal",
            "testing": preset_name != "minimal",
            "pic": preset_name == "library",
            "rtti": True,
            "exceptions": True
        }

        # Apply user overrides to settings
        base_settings.update(user_overrides)

        return TemplateConfig(
            name=preset_name,
            description=f"Legacy {preset_name} template",
            type="base",
            settings=base_settings
        )

    def generate_cmake_content(self, template: TemplateConfig, project_name: str,
                              cmake_min_version: str = "3.28", cxx_standard: str = "23") -> str:
        """Generate CMakeLists.txt content from resolved template"""

        # Use custom template if provided
        if template.cmake_template:
            content = template.cmake_template.format(
                project_name=project_name,
                cmake_min_version=cmake_min_version,
                cxx_standard=cxx_standard
            )
        else:
            # Generate default template based on settings
            content = self._generate_default_cmake(template, project_name, cmake_min_version, cxx_standard)

        # Add template additions
        if template.cmake_template_additions:
            try:
                additions = template.cmake_template_additions.format(project_name=project_name)
            except (KeyError, ValueError):
                # Fallback: use simple replacement for problematic templates
                additions = template.cmake_template_additions.replace('{project_name}', project_name)
            content += "\n\n" + additions

        return content

    def _generate_default_cmake(self, template: TemplateConfig, project_name: str,
                               cmake_min_version: str, cxx_standard: str) -> str:
        """Generate default CMakeLists.txt based on template settings"""
        content = f"""cmake_minimum_required(VERSION {cmake_min_version})
project({project_name} LANGUAGES CXX)

set(CMAKE_CXX_STANDARD {cxx_standard})
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
"""

        # Add dependencies
        for dep in template.dependencies:
            content += f"{dep}\n"

        if template.dependencies:
            content += "\n"

        # Add CMake options
        for option in template.cmake_options:
            if "=" in option:
                content += f"set({option})\n"
            else:
                content += f"option({option} ON)\n"

        if template.cmake_options:
            content += "\n"

        # Add compiler warnings
        content += """# Compiler warnings
add_library(project_warnings INTERFACE)
target_compile_options(project_warnings INTERFACE
  $<$<CXX_COMPILER_ID:GNU,Clang>:-Wall -Wextra"""

        # Add additional compiler flags
        for flag in template.compiler_flags:
            content += f" {flag}"

        content += """>
  $<$<CXX_COMPILER_ID:MSVC>:/W4>
)
"""

        # Add linker flags if any
        if template.linker_flags:
            content += "\ntarget_link_options(project_warnings INTERFACE"
            for flag in template.linker_flags:
                content += f"\n  {flag}"
            content += "\n)\n"

        # Add target based on type
        target_type = template.settings.get('target_type', 'executable')
        if target_type == 'library':
            content += f"""
# Library target
add_library({project_name} src/{project_name}.cpp)
target_include_directories({project_name} PUBLIC include)
target_link_libraries({project_name} PRIVATE project_warnings)

# Example executable
add_executable({project_name}_example examples/main.cpp)
target_link_libraries({project_name}_example PRIVATE {project_name} project_warnings)
"""
        else:
            content += f"""
# Executable target
add_executable({project_name} main.cpp)
target_link_libraries({project_name} PRIVATE project_warnings)
"""

        return content


def main():
    """Test the template engine"""
    template_dir = pathlib.Path(__file__).parent.parent / "templates"
    manifest_dir = pathlib.Path(__file__).parent.parent / "manifest"

    engine = TemplateEngine(template_dir, manifest_dir)

    print("Available presets:")
    for preset in engine.get_available_presets():
        print(f"  - {preset}")

    # Test resolving a template
    try:
        template = engine.resolve_template("oss-hardening")
        print(f"\nResolved template: {template.name}")
        print(f"Description: {template.description}")
        print(f"Compiler flags: {template.compiler_flags}")
    except Exception as e:
        print(f"Error resolving template: {e}")


if __name__ == "__main__":
    main()