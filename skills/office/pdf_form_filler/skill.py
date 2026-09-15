from typing import Dict, Any
import os
import json
import anthropic
import yaml
from skillware.core.base_skill import BaseSkill


class PDFFormFillerSkill(BaseSkill):
    """
    A skill that fills PDF forms based on natural language instructions.
    """

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        api_key = self.credential("ANTHROPIC_API_KEY")
        self.client = anthropic.Anthropic(api_key=api_key) if api_key else None

    @property
    def manifest(self) -> Dict[str, Any]:
        # Helper to load manifest from this directory
        manifest_path = os.path.join(os.path.dirname(__file__), "manifest.yaml")
        if os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        return {}

    def execute(self, params: Dict[str, Any]) -> Any:
        # Import here to avoid top-level linter issues with relative imports
        try:
            from .utils import detect_form_fields, apply_edits, FieldEdit
        except ImportError:
            import sys

            sys.path.append(os.path.dirname(__file__))
            from utils import detect_form_fields, apply_edits, FieldEdit

        # 1. Parse Inputs
        pdf_path = params.get("pdf_path")
        instructions = params.get("instructions")
        output_path = params.get("output_path")

        if not pdf_path or not os.path.exists(pdf_path):
            return {"error": f"PDF file not found: {pdf_path}"}

        if not instructions:
            return {"error": "No instructions provided."}

        # 2. Analyze PDF
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        fields = detect_form_fields(pdf_bytes)
        if not fields:
            return {"status": "warning", "message": "No fillable fields found in PDF."}

        # 3. Construct LLM Prompt
        # Load system instructions
        inst_path = os.path.join(os.path.dirname(__file__), "instructions.md")
        system_prompt = "You are a form filling assistant."
        if os.path.exists(inst_path):
            with open(inst_path, "r", encoding="utf-8") as f:
                system_prompt = f.read()

        # Prepare field context for LLM
        fields_context = [f.to_dict() for f in fields]

        user_message = f"""
        User Instructions: {instructions}

        Detected Fields:
        {json.dumps(fields_context, indent=2)}

        Return a JSON object mapping field_ids to values.
        """

        # 4. Call LLM to map instructions -> fields
        if self.client is None:
            return {"error": "Missing ANTHROPIC_API_KEY environment variable."}

        try:
            message = self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
            response_text = message.content[0].text

            # Extract JSON from response
            json_str = response_text.strip()
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0]
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0]

            edits = json.loads(json_str)

        except Exception as e:
            return {"error": f"LLM processing failed: {str(e)}"}

        # 5. Apply Edits
        if not edits:
            return {
                "status": "no_change",
                "message": "LLM determined no fields needed to be changed.",
            }

        try:
            # Convert dict to List[FieldEdit]
            edits_list = [FieldEdit(field_id=k, value=v) for k, v in edits.items()]
            filled_pdf_bytes = apply_edits(pdf_bytes, edits_list)

            # Determine output location
            if not output_path:
                base, ext = os.path.splitext(pdf_path)
                output_path = f"{base}_filled{ext}"

            with open(output_path, "wb") as f:
                f.write(filled_pdf_bytes)

            return {
                "status": "success",
                "output_path": output_path,
                "filled_fields": list(edits.keys()),
                "message": f"Successfully filled {len(edits)} fields.",
            }

        except Exception as e:
            return {"error": f"Failed to apply edits to PDF: {str(e)}"}
