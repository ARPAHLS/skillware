import os
import yaml
import json
import importlib.util
from typing import Dict, Any, Type, Optional

class SkillLoader:
    """
    Utility to load skills dynamically or by path, bundling their
    manifests, instructions, and logic for LLM usage.
    """

    @staticmethod
    def load_skill(skill_path: str) -> Dict[str, Any]:
        """
        Loads a skill and returns a bundled object with:
        - class: The Python class (uninstantiated)
        - manifest: The YAML metadata
        - instructions: The system prompt content
        - card: The UI card definition
        """
        if not os.path.exists(skill_path):
             # Try relative to repo root if absolute path fails
             base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../skills'))
             skill_path = os.path.join(base_path, skill_path)
        
        if not os.path.exists(skill_path):
            raise FileNotFoundError(f"Skill not found at {skill_path}")

        # Load Manifest
        manifest = {}
        manifest_path = os.path.join(skill_path, 'manifest.yaml')
        if os.path.exists(manifest_path):
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = yaml.safe_load(f)

        # Load Instructions
        instructions = ""
        inst_path = os.path.join(skill_path, 'instructions.md')
        if os.path.exists(inst_path):
             with open(inst_path, 'r', encoding='utf-8') as f:
                 instructions = f.read()

        # Load Card
        card = {}
        card_path = os.path.join(skill_path, 'card.json')
        if os.path.exists(card_path):
             with open(card_path, 'r', encoding='utf-8') as f:
                 card = json.load(f)

        # Load Python Module
        skill_file = os.path.join(skill_path, 'skill.py')
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
                "card": card
            }
        
        return {}

    @staticmethod
    def to_gemini_tool(skill_bundle: Dict[str, Any]) -> Dict[str, Any]:
        """
        Converts a skill manifest to a Gemini function declaration.
        Handles type conversion (lowercase to UPPERCASE) for Gemini Protobuf compatibility.
        """
        manifest = skill_bundle.get('manifest', {})
        name = manifest.get('name', 'unknown_tool')
        description = manifest.get('description', '')
        parameters = manifest.get('parameters', {})
        
        # Helper to recursively upper-case 'type' fields
        def sanitize_schema(schema):
            new_schema = schema.copy()
            if 'type' in new_schema:
                new_schema['type'] = new_schema['type'].upper()
            if 'properties' in new_schema:
                new_schema['properties'] = {
                    k: sanitize_schema(v) for k, v in new_schema['properties'].items()
                }
            return new_schema

        return {
            "name": name,
            "description": description,
            "parameters": sanitize_schema(parameters)
        }

    @staticmethod
    def to_claude_tool(skill_bundle: Dict[str, Any]) -> Dict[str, Any]:
        """
        Converts a skill manifest to an Anthropic Claude tool definition.
        """
        manifest = skill_bundle.get('manifest', {})
        name = manifest.get('name', 'unknown_tool')
        description = manifest.get('description', '')
        parameters = manifest.get('parameters', {})
        
        return {
            "name": name,
            "description": description,
            "input_schema": parameters
        }
