import base64
import io
from pathlib import Path
from typing import Any, Dict

from skillware.core.base_skill import BaseSkill


class BackgroundRemover(BaseSkill):
    """Remove image backgrounds locally using rembg."""

    @property
    def manifest(self) -> Dict[str, Any]:
        return {
            "name": "creative/bg_remover",
            "version": "0.1.0",
            "description": (
                "Remove image backgrounds locally using rembg "
                "and return a transparent PNG."
            ),
        }

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute background removal."""

        try:
            try:
                from PIL import Image
                from rembg import new_session, remove
            except ImportError:
                return {
                    "success": False,
                    "error": (
                        "The 'rembg' dependency is not installed. "
                        "Install it with: pip install rembg pillow onnxruntime"
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
                image_bytes = base64.b64decode(image_b64)
            else:
                image_bytes = Path(input_path).read_bytes()

            session = new_session(model)

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
                Path(output_path).write_bytes(buffer.getvalue())

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
