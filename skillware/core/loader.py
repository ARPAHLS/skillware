import inspect
import os
import re
import warnings
import yaml
import json
import importlib.util
from pathlib import Path
from typing import Dict, Any, List, Optional, Type


class SkillwareIdentityWarning(UserWarning):
    """Emitted when manifest.name does not match the registry folder path (warn-only in v1)."""


SKILLWARE_SKILL_PATH_ENV = "SKILLWARE_SKILL_PATH"
_MAX_PARENT_WALK = 6

# PyPI distribution names that differ from their import paths.
_REQUIREMENT_IMPORT_ALIASES = {
    "google-genai": "google.genai",
    "google-generativeai": "google.generativeai",
    "pymupdf": "fitz",
    "beautifulsoup4": "bs4",
    "pyyaml": "yaml",
}


class SkillLoader:
    """
    Utility to load skills dynamically or by path, bundling their
    manifests, instructions, and logic for LLM usage.
    """

    @staticmethod
    def _requirement_import_name(requirement: str) -> str:
        pkg_name = requirement.split(">")[0].split("<")[0].split("=")[0].strip()
        return _REQUIREMENT_IMPORT_ALIASES.get(pkg_name, pkg_name)

    @staticmethod
    def _is_skill_dir(path: Path) -> bool:
        return path.is_dir() and (path / "skill.py").is_file()

    @staticmethod
    def _bundled_skills_root() -> Path:
        return Path(__file__).resolve().parent.parent.parent / "skills"

    @staticmethod
    def _env_skill_roots() -> List[Path]:
        raw = os.environ.get(SKILLWARE_SKILL_PATH_ENV, "").strip()
        if not raw:
            return []
        return [
            Path(entry).expanduser().resolve()
            for entry in raw.split(os.pathsep)
            if entry.strip()
        ]

    @staticmethod
    def _all_skill_roots() -> List[Path]:
        roots: List[Path] = []
        seen: set[str] = set()
        for root in (
            SkillLoader._env_skill_roots()
            + SkillLoader._cwd_skill_roots()
            + [SkillLoader._bundled_skills_root()]
        ):
            resolved = root.resolve()
            key = str(resolved)
            if key not in seen:
                seen.add(key)
                roots.append(resolved)
        return roots

    @staticmethod
    def _expected_registry_id(skill_dir: Path) -> Optional[str]:
        """
        Return category/skill_name when the skill directory uses registry layout
        ({skill_root}/{category}/{skill_name}/). Flat layouts ({skill_root}/{skill_name}/)
        and arbitrary absolute paths outside skill roots return None.
        """
        resolved = skill_dir.resolve()
        parent = resolved.parent
        for root in SkillLoader._all_skill_roots():
            try:
                relative_parent = parent.relative_to(root)
            except ValueError:
                continue
            if len(relative_parent.parts) == 1:
                return f"{relative_parent.parts[0]}/{resolved.name}"
        return None

    @staticmethod
    def _validate_manifest_identity(
        skill_dir: Path, manifest: Dict[str, Any]
    ) -> Optional[str]:
        """
        Warn when manifest.name diverges from the path-derived registry ID.
        Returns the expected registry ID for registry-layout skills, else None.
        """
        expected = SkillLoader._expected_registry_id(skill_dir)
        if expected is None:
            return None

        manifest_name = manifest.get("name")
        if not manifest_name or not str(manifest_name).strip():
            warnings.warn(
                f"Skill at {skill_dir}: manifest.yaml is missing 'name'; "
                f"expected {expected!r} for registry layout (category/skill_name).",
                SkillwareIdentityWarning,
                stacklevel=4,
            )
            return expected

        manifest_name = str(manifest_name).strip()
        if manifest_name != expected:
            warnings.warn(
                f"Skill at {skill_dir}: manifest.yaml name {manifest_name!r} does not "
                f"match registry path {expected!r}. Set name to the full ID "
                f"(category/skill_name) or use a flat layout (<skill_root>/<skill_name>/) "
                f"for private local skills. See CONTRIBUTING.md.",
                SkillwareIdentityWarning,
                stacklevel=4,
            )
        return expected

    @staticmethod
    def _cwd_skill_roots() -> List[Path]:
        roots: List[Path] = []
        current = Path.cwd().resolve()
        for _ in range(_MAX_PARENT_WALK):
            candidate = current / "skills"
            if candidate.is_dir():
                resolved = candidate.resolve()
                if resolved not in roots:
                    roots.append(resolved)
            parent = current.parent
            if parent == current:
                break
            current = parent
        return roots

    @staticmethod
    def _resolve_skill_path(skill_path: str) -> Path:
        """
        Resolve a skill directory from an absolute path, a path relative to cwd,
        or a registry skill id (category/skill_name).

        Search order when the path is not an existing skill directory:
        1. SKILLWARE_SKILL_PATH entries (os.pathsep-separated roots)
        2. ./skills/ under cwd and parent directories
        3. Bundled skills shipped with the skillware package
        """
        raw = skill_path.strip()
        if not raw:
            raise FileNotFoundError("Skill path must not be empty.")

        direct = Path(raw)
        if direct.exists():
            resolved = direct.resolve()
            if SkillLoader._is_skill_dir(resolved):
                return resolved

        skill_id = raw.replace("\\", "/").strip("/")
        searched: List[str] = []

        def try_roots(roots: List[Path]) -> Optional[Path]:
            for root in roots:
                attempt = (root / skill_id).resolve()
                searched.append(str(attempt))
                if SkillLoader._is_skill_dir(attempt):
                    return attempt
            return None

        for roots in (
            SkillLoader._env_skill_roots(),
            SkillLoader._cwd_skill_roots(),
            [SkillLoader._bundled_skills_root()],
        ):
            found = try_roots(roots)
            if found is not None:
                return found

        raise FileNotFoundError(
            f"Skill not found: {skill_id!r}. Searched:\n  "
            + "\n  ".join(searched)
            + f"\nSet {SKILLWARE_SKILL_PATH_ENV} or pass an absolute path to the skill directory."
        )

    @staticmethod
    def _discover_skill_class(module: Any, skill_file: str) -> Type[Any]:
        """
        Return the single BaseSkill subclass defined in the loaded skill module.
        """
        from skillware.core.base_skill import BaseSkill

        skill_classes = [
            obj
            for _, obj in inspect.getmembers(module, inspect.isclass)
            if issubclass(obj, BaseSkill)
            and obj is not BaseSkill
            and obj.__module__ == module.__name__
        ]
        if len(skill_classes) == 1:
            return skill_classes[0]
        if not skill_classes:
            raise ImportError(
                f"Expected exactly one BaseSkill subclass in {skill_file}, found none."
            )
        names = [cls.__name__ for cls in skill_classes]
        raise ImportError(
            f"Expected exactly one BaseSkill subclass in {skill_file}, "
            f"found: {names}"
        )

    @staticmethod
    def get_skill_class(skill_bundle: Dict[str, Any]) -> Type[Any]:
        """Return the BaseSkill subclass from a bundle produced by load_skill()."""
        skill_class = skill_bundle.get("class")
        if skill_class is None:
            raise KeyError(
                "Skill bundle has no 'class' key; load with SkillLoader.load_skill() first."
            )
        return skill_class

    @staticmethod
    def load_skill(skill_path: str) -> Dict[str, Any]:
        """
        Loads a skill and returns a bundled object with:
        - module: The loaded skill.py module
        - class: The BaseSkill subclass (uninstantiated)
        - manifest: The YAML metadata
        - instructions: The system prompt content
        - card: The UI card definition
        - registry_id: Path-derived registry ID when validation applies
        """
        resolved_path = SkillLoader._resolve_skill_path(skill_path)
        skill_path = str(resolved_path)

        # Load Manifest
        manifest = {}
        manifest_path = os.path.join(skill_path, "manifest.yaml")
        if os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = yaml.safe_load(f) or {}

        registry_id = SkillLoader._validate_manifest_identity(resolved_path, manifest)

        # Check Dependencies
        if "requirements" in manifest:
            missing = []
            for req in manifest["requirements"]:
                import_name = SkillLoader._requirement_import_name(req)
                if not importlib.util.find_spec(import_name):
                    missing.append(req)

            if missing:
                raise ImportError(
                    f"Skill '{manifest.get('name')}' requires missing packages: {', '.join(missing)}. "
                    f"Please run: pip install {' '.join(missing)}"
                )

        # Load Instructions
        instructions = ""
        inst_path = os.path.join(skill_path, "instructions.md")
        if os.path.exists(inst_path):
            with open(inst_path, "r", encoding="utf-8") as f:
                instructions = f.read()

        # Load Card
        card = {}
        card_path = os.path.join(skill_path, "card.json")
        if os.path.exists(card_path):
            with open(card_path, "r", encoding="utf-8") as f:
                card = json.load(f)

        # Load Python Module
        skill_file = os.path.join(skill_path, "skill.py")
        spec = importlib.util.spec_from_file_location("skill_module", skill_file)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            skill_class = SkillLoader._discover_skill_class(module, skill_file)
            return {
                "module": module,
                "class": skill_class,
                "manifest": manifest,
                "instructions": instructions,
                "card": card,
                "registry_id": registry_id,
            }
        return {}

    @staticmethod
    def to_claude_tool(skill_bundle: Dict[str, Any]) -> Dict[str, Any]:
        """
        Converts a skill manifest to an Anthropic Claude tool definition.
        """
        manifest = skill_bundle.get("manifest", {})
        name = manifest.get("name", "unknown_tool")
        description = manifest.get("description", "")
        parameters = manifest.get("parameters", {})

        return {"name": name, "description": description, "input_schema": parameters}

    @staticmethod
    def _sanitize_function_tool_name(name: str) -> str:
        """
        Normalizes manifest tool IDs for OpenAI-compatible function-calling APIs.
        Allows letters, digits, underscores, and hyphens (max 64 characters).
        """
        if not name or not str(name).strip():
            return "unknown_tool"
        safe = re.sub(r"[^a-zA-Z0-9_-]", "_", str(name).replace("/", "_"))
        safe = re.sub(r"_+", "_", safe).strip("_")
        if not safe:
            return "unknown_tool"
        return safe[:64]

    @staticmethod
    def _sanitize_gemini_tool_name(name: str) -> str:
        return SkillLoader._sanitize_function_tool_name(name)

    @staticmethod
    def _sanitize_openai_tool_name(name: str) -> str:
        return SkillLoader._sanitize_function_tool_name(name)

    @staticmethod
    def _sanitize_deepseek_tool_name(name: str) -> str:
        return SkillLoader._sanitize_function_tool_name(name)

    @staticmethod
    def to_gemini_tool(skill_bundle: Dict[str, Any]) -> Any:
        """
        Converts a skill manifest to a Gemini function declaration.
        Handles type conversion (lowercase to UPPERCASE) for Gemini Protobuf compatibility.
        See: https://ai.google.dev/gemini-api/docs/generate-content/function-calling#how-it-works
        """
        try:
            from google.genai import types
        except ImportError:
            raise ImportError(
                "google-genai is required for to_gemini_tool. Install with: pip install google-genai"
            )

        manifest = skill_bundle.get("manifest", {})
        raw_name = manifest.get("name", "unknown_tool")
        name = SkillLoader._sanitize_gemini_tool_name(raw_name)
        description = manifest.get("description", "")
        parameters = manifest.get("parameters", {})

        # Helper to recursively upper-case 'type' fields
        def sanitize_schema(schema):
            new_schema = schema.copy()
            if "type" in new_schema:
                new_schema["type"] = new_schema["type"].upper()
            if "properties" in new_schema:
                new_schema["properties"] = {
                    k: sanitize_schema(v) for k, v in new_schema["properties"].items()
                }
            return new_schema

        return types.Tool(
            function_declarations=[
                {
                    "name": name,
                    "description": description,
                    "parameters": sanitize_schema(parameters),
                }
            ]
        )

    @staticmethod
    def to_openai_tool(skill_bundle: Dict[str, Any]) -> Dict[str, Any]:
        """
        Converts a skill manifest to an OpenAI Chat Completions tool definition.
        See: https://platform.openai.com/docs/guides/function-calling
        """
        manifest = skill_bundle.get("manifest", {})
        raw_name = manifest.get("name", "unknown_tool")
        description = manifest.get("description", "")
        parameters = manifest.get("parameters", {})

        return {
            "type": "function",
            "function": {
                "name": SkillLoader._sanitize_openai_tool_name(raw_name),
                "description": description,
                "parameters": parameters,
            },
        }

    @staticmethod
    def to_deepseek_tool(skill_bundle: Dict[str, Any]) -> Dict[str, Any]:
        """
        Converts a skill manifest to a DeepSeek API tool definition.
        DeepSeek uses an OpenAI-compatible tools schema; this adapter is separate from
        to_openai_tool() by design. See: https://api-docs.deepseek.com/
        """
        manifest = skill_bundle.get("manifest", {})
        raw_name = manifest.get("name", "unknown_tool")
        description = manifest.get("description", "")
        parameters = manifest.get("parameters", {})

        return {
            "type": "function",
            "function": {
                "name": SkillLoader._sanitize_deepseek_tool_name(raw_name),
                "description": description,
                "parameters": parameters,
            },
        }

    @staticmethod
    def to_ollama_prompt(skill_bundle: Dict[str, Any]) -> str:
        """
        Converts a skill manifest to a textual description suitable for a system prompt.
        This allows older models (like Llama 3) running via Ollama without native tool-calling
        API support to understand and utilize the skill via text generation.
        """
        manifest = skill_bundle.get("manifest", {})
        name = manifest.get("name", "unknown_tool")
        description = manifest.get("description", "").strip()
        parameters = manifest.get("parameters", {})

        prompt = f"### Tool: `{name}`\n"
        prompt += f"**Description:** {description}\n"
        prompt += "**Parameters:**\n"

        props = parameters.get("properties", {})
        required = parameters.get("required", [])

        if not props:
            prompt += "- None\n"
        else:
            for k, v in props.items():
                req_str = "Required" if k in required else "Optional"
                prompt += f"- `{k}` ({v.get('type', 'any')}): {v.get('description', '')} [{req_str}]\n"

        return prompt
