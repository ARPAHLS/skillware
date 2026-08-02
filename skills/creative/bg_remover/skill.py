import base64
import io
import os
from pathlib import Path
from typing import Any, Dict

from skillware.core.base_skill import BaseSkill

MAX_IMAGE_BYTES = 25 * 1024 * 1024  # 25 MB


class BackgroundRemover(BaseSkill):
    """Remove image backgrounds locally using rembg."""

    _sessions = {}

    @classmethod
    def _get_session(cls, model: str):
        """Load and reuse rembg sessions across executions."""
        if model not in cls._sessions:
            from rembg import new_session

            cls._sessions[model] = new_session(model)

        return cls._sessions[model]

    @staticmethod
    def _validate_output_path(output_path: str) -> Path:
        output = Path(output_path)

        if ".." in output.parts:
            raise ValueError("Unsafe output_path contains path traversal.")

        return output

    @property
    def manifest(self) -> Dict[str, Any]:
        manifest_path = os.path.join(os.path.dirname(__file__), "manifest.yaml")
        if os.path.exists(manifest_path):
            import yaml

            with open(manifest_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        return {}

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute background removal."""

        try:
            try:
                from PIL import Image
                from rembg import remove
            except ImportError:
                return {
                    "success": False,
                    "error": (
                        "The 'rembg' dependency is not installed. "
                        'Install with: pip install "skillware[creative_bg_remover]" '
                        "(or pip install rembg pillow onnxruntime)."
                    ),
                    "error_code": "MISSING_DEPENDENCY",
                }

            image_b64 = params.get("image")
            input_path = params.get("input_path")
            output_path = params.get("output_path")
            model = params.get("model", "isnet-general-use")
            alpha_matting = params.get("alpha_matting", False)

            if not image_b64 and not input_path:
                return {
                    "success": False,
                    "error": "Either image or input_path must be provided.",
                    "error_code": "INVALID_INPUT",
                }

            # Read image bytes
            if image_b64:
                try:
                    image_bytes = base64.b64decode(image_b64, validate=True)
                except Exception:
                    return {
                        "success": False,
                        "error": "Invalid base64 image.",
                        "error_code": "INVALID_INPUT",
                    }
            else:
                input_file = Path(input_path)

                if input_file.is_dir():
                    return {
                        "success": False,
                        "error": "Input path must be a file, not a directory.",
                        "error_code": "INVALID_INPUT",
                    }

                if not input_file.exists():
                    return {
                        "success": False,
                        "error": f"Input file '{input_path}' was not found.",
                        "error_code": "FILE_NOT_FOUND",
                    }

                image_bytes = input_file.read_bytes()

            if len(image_bytes) > MAX_IMAGE_BYTES:
                return {
                    "success": False,
                    "error": f"Input image exceeds the maximum size of {MAX_IMAGE_BYTES // (1024 * 1024)} MB.",
                    "error_code": "INVALID_INPUT",
                }

            if len(image_bytes) == 0:
                return {
                    "success": False,
                    "error": "Input image is empty.",
                    "error_code": "INVALID_INPUT",
                }

            try:
                image = Image.open(io.BytesIO(image_bytes))
                image.verify()

                # Reopen after verify() because verify() leaves the image unusable.
                image = Image.open(io.BytesIO(image_bytes))
            except Exception:
                return {
                    "success": False,
                    "error": "Input is not a valid image.",
                    "error_code": "INVALID_INPUT",
                }

            session = self._get_session(model)

            output_bytes = remove(
                image_bytes,
                session=session,
                alpha_matting=alpha_matting,
            )

            # Read PNG
            image = Image.open(io.BytesIO(output_bytes))

            # Convert back to base64
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")

            encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")

            # Optional save
            if output_path:
                try:
                    output_file = self._validate_output_path(output_path)
                except ValueError:
                    return {
                        "success": False,
                        "error": "Unsafe output_path.",
                        "error_code": "INVALID_INPUT",
                    }

                output_file.parent.mkdir(parents=True, exist_ok=True)
                output_file.write_bytes(buffer.getvalue())

            return {
                "success": True,
                "image_base64": encoded,
                "mime_type": "image/png",
                "output_path": output_path,
                "width": image.width,
                "height": image.height,
                "model_used": model,
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_code": "PROCESSING_FAILED",
            }
