import os
import re
import yaml
import json
import importlib.util
from pathlib import Path
from typing import Dict, Any, List, Optional

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
        return [Path(entry).expanduser().resolve() for entry in raw.split(os.pathsep) if entry.strip()]

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
    def load_skill(skill_path: str) -> Dict[str, Any]:
        """
        Loads a skill and returns a bundled object with:
        - class: The Python class (uninstantiated)
        - manifest: The YAML metadata
        - instructions: The system prompt content
        - card: The UI card definition
        """
        resolved_path = SkillLoader._resolve_skill_path(skill_path)
        skill_path = str(resolved_path)

        # Load Manifest
        manifest = {}
        manifest_path = os.path.join(skill_path, "manifest.yaml")
        if os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = yaml.safe_load(f)

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
            # Find the class that inherits from BaseSkill?
            # For now assume the user looks for the exported class or we inspect.
            # We'll just return the module and let the user instantiate the known class name
            # or we could enforce a naming convention.
            return {
                "module": module,
                "manifest": manifest,
                "instructions": instructions,
                "card": card,
            }
        return {}

    @staticmethod
    def to_gemini_tool(skill_bundle: Dict[str, Any]) -> Dict[str, Any]:
        """
        Converts a skill manifest to a Gemini function declaration.
        Handles type conversion (lowercase to UPPERCASE) for Gemini Protobuf compatibility.
        """
        manifest = skill_bundle.get("manifest", {})
        name = manifest.get("name", "unknown_tool")
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

        return {
            "name": name,
            "description": description,
            "parameters": sanitize_schema(parameters),
        }

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
    def _sanitize_openai_tool_name(name: str) -> str:
        return SkillLoader._sanitize_function_tool_name(name)

    @staticmethod
    def _sanitize_deepseek_tool_name(name: str) -> str:
        return SkillLoader._sanitize_function_tool_name(name)

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
