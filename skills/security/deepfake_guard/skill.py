"""security/deepfake_guard — Air-gapped media & document authenticity guard."""

from __future__ import annotations

import os
from typing import Any, Callable, Dict, Optional, Tuple

from skillware.core.base_skill import BaseSkill

try:
    from .document import parse_and_validate_mrz
    from .forensics import load_image
    from .guard import analyze_asset
    from .provenance import extract_metadata_and_provenance
except (ImportError, ValueError):
    import sys

    _pkg_dir = os.path.dirname(os.path.abspath(__file__))
    if _pkg_dir not in sys.path:
        sys.path.insert(0, _pkg_dir)
    from document import parse_and_validate_mrz
    from forensics import load_image
    from guard import analyze_asset
    from provenance import extract_metadata_and_provenance


class DeepfakeGuardSkill(BaseSkill):
    """
    Air-gapped media & document authenticity guard with ELA, noise residuals,
    C2PA provenance, and ICAO 9303 MRZ checksum validation.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        credential_fn: Optional[Callable[[str], Optional[str]]] = None,
        **kwargs: Any,
    ) -> None:
        try:
            super().__init__(config=config, credential_fn=credential_fn)
        except TypeError:
            super().__init__(config=config)

    @property
    def manifest(self) -> Dict[str, Any]:
        """Loads manifest.yaml from the skill bundle directory."""
        if hasattr(self, "load_manifest_from_dir"):
            return self.load_manifest_from_dir(os.path.dirname(__file__))
        import yaml

        manifest_path = os.path.join(os.path.dirname(__file__), "manifest.yaml")
        with open(manifest_path, "r", encoding="utf-8") as handle:
            return yaml.safe_load(handle)

    def execute(
        self,
        params: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Executes local deterministic media or document authenticity inspection.
        Never calls external networks or leaks sensitive document data.
        """
        merged_params = dict(params or {})
        merged_params.update(kwargs)

        try:
            self.validate_params(merged_params)
        except Exception as exc:
            return {
                "status": "error",
                "error_code": "validation_error",
                "message": f"Parameter validation failed: {exc}",
            }

        action = str(merged_params.get("action", "analyze")).strip().lower()
        if not action:
            action = "analyze"

        try:
            if action == "analyze":
                return self._action_analyze(merged_params)
            elif action == "inspect_document":
                return self._action_inspect_document(merged_params)
            elif action == "inspect_media":
                return self._action_inspect_media(merged_params)
            elif action == "verify_provenance":
                return self._action_verify_provenance(merged_params)
            elif action == "validate_mrz":
                return self._action_validate_mrz(merged_params)
            else:
                return {
                    "status": "error",
                    "error_code": "unsupported_action",
                    "message": (
                        f"Unsupported action '{action}'. Supported actions: "
                        "'analyze', 'inspect_document', 'inspect_media', "
                        "'verify_provenance', 'validate_mrz'."
                    ),
                }
        except Exception as exc:
            return {
                "status": "error",
                "error_code": "execution_failed",
                "message": f"Forensic analysis failed: {exc}",
            }

    # -------------------------------------------------------------------------
    # Internal Action Handlers
    # -------------------------------------------------------------------------

    def _fetch_url_image(self, url: str) -> Tuple[Optional[bytes], str]:
        import ipaddress
        import socket
        from urllib.parse import urlparse
        import requests

        parsed = urlparse(url.strip())
        if parsed.scheme not in {"http", "https"}:
            return None, "Only http and https URLs are allowed."
        hostname = parsed.hostname
        if not hostname:
            return None, "URL must include a valid hostname."
        lowered = hostname.lower()
        if lowered in {"localhost", "127.0.0.1", "::1"} or lowered.endswith(".local"):
            return None, "Local or loopback hosts are blocked."
        try:
            for info in socket.getaddrinfo(hostname, None):
                ip = ipaddress.ip_address(info[4][0])
                if (
                    ip.is_private
                    or ip.is_loopback
                    or ip.is_link_local
                    or ip.is_reserved
                    or ip.is_multicast
                ):
                    return None, "Private or non-public IP addresses are blocked."
        except socket.gaierror:
            return None, "Hostname could not be resolved."

        try:
            resp = requests.get(
                url,
                timeout=10,
                headers={"User-Agent": "Skillware-DeepfakeGuard/1.0"},
                allow_redirects=True,
            )
            resp.raise_for_status()
            return resp.content[: 15 * 1024 * 1024], "ok"
        except Exception as exc:
            return None, f"Failed to fetch image from URL: {exc}"

    def _resolve_source_and_bytes(
        self, params: Dict[str, Any]
    ) -> Tuple[Optional[Any], Optional[bytes], bool]:
        raw_b64 = params.get("media_bytes_b64") or params.get("image_base64")
        if raw_b64:
            b64_str = str(raw_b64).strip()
            if ";base64," in b64_str:
                b64_str = b64_str.split(";base64,", 1)[1]
            try:
                import base64

                raw_bytes = base64.b64decode(b64_str)
                return raw_bytes, raw_bytes, False
            except Exception:
                pass

        file_src = (
            params.get("media_path")
            or params.get("image_path")
            or params.get("file_path")
        )
        if file_src:
            path_str = str(file_src).strip()
            if os.path.isfile(path_str):
                try:
                    with open(path_str, "rb") as f:
                        raw_bytes = f.read()
                    return path_str, raw_bytes, False
                except Exception:
                    pass
            return path_str, None, False

        url_src = params.get("url") or params.get("image_url")
        if url_src:
            url_str = str(url_src).strip()
            raw_bytes, _ = self._fetch_url_image(url_str)
            if raw_bytes is not None:
                return raw_bytes, raw_bytes, True

        return None, None, False

    def _action_analyze(self, params: Dict[str, Any]) -> Dict[str, Any]:
        source, raw_bytes, is_url = self._resolve_source_and_bytes(params)
        raw_mrz = params.get("raw_mrz") or params.get("mrz_string") or params.get("mrz")
        mode = str(params.get("mode", "auto")).strip().lower()
        claimed_doc_type = params.get("claimed_doc_type") or params.get(
            "expected_document_type"
        )
        claimed_country = params.get("claimed_country")
        strictness = str(params.get("strictness", "balanced")).strip().lower()

        if source is None and raw_mrz is None:
            return {
                "status": "error",
                "error_code": "missing_input",
                "message": (
                    "Either 'image_path', 'media_path', 'image_base64', "
                    "'media_bytes_b64', 'url', or 'mrz_string' must be provided."
                ),
            }

        result = analyze_asset(
            source=source,
            raw_mrz=raw_mrz,
            raw_bytes=raw_bytes,
            mode=mode,
            claimed_doc_type=claimed_doc_type,
            claimed_country=claimed_country,
            strictness=strictness,
        )

        detected_doc_type = None
        if result.get("doc"):
            detected_doc_type = result["doc"].get("detected_type")

        return {
            "status": "ok",
            "action": "analyze",
            "offline": not is_url,
            "verdict": result["verdict"],
            "summary": result.get("summary", ""),
            "confidence_score": result["confidence_score"],
            "is_synthetic_likely": result["is_synthetic_likely"],
            "is_tampered_likely": result["is_tampered_likely"],
            "detected_doc_type": detected_doc_type,
            "artifacts_detected": result["artifacts_detected"],
            "signals": result["signals"],
            "doc": result.get("doc"),
            "provenance": result.get("provenance"),
            "limitations": result["limitations"],
        }

    def _action_inspect_document(self, params: Dict[str, Any]) -> Dict[str, Any]:
        params_copy = dict(params)
        params_copy["mode"] = "document"
        return self._action_analyze(params_copy)

    def _action_inspect_media(self, params: Dict[str, Any]) -> Dict[str, Any]:
        params_copy = dict(params)
        params_copy["mode"] = "media_only"
        return self._action_analyze(params_copy)

    def _action_verify_provenance(self, params: Dict[str, Any]) -> Dict[str, Any]:
        source, raw_bytes, is_url = self._resolve_source_and_bytes(params)
        if source is None:
            return {
                "status": "error",
                "error_code": "missing_input",
                "message": (
                    "Parameter 'image_path', 'media_path', 'image_base64', "
                    "'media_bytes_b64', or 'url' is required."
                ),
            }

        image = load_image(source)
        prov = extract_metadata_and_provenance(image, raw_bytes=raw_bytes)

        is_suspicious = (
            prov["has_manipulation_software"] or prov["has_ai_provenance_cues"]
        )
        verdict = "suspicious" if is_suspicious else "authentic_likely"

        if prov["has_manipulation_software"]:
            summary = (
                f"Manipulation software metadata detected: "
                f"{', '.join(prov['manipulation_tools'])}."
            )
        elif prov["has_ai_provenance_cues"]:
            summary = (
                f"AI generator provenance cues detected: "
                f"{', '.join(prov['ai_generation_cues'])}."
            )
        else:
            summary = "Metadata and provenance clean: no editing tools or synthetic cues detected."

        return {
            "status": "ok",
            "action": "verify_provenance",
            "offline": not is_url,
            "verdict": verdict,
            "summary": summary,
            "has_manipulation_software": prov["has_manipulation_software"],
            "manipulation_tools": prov["manipulation_tools"],
            "has_ai_provenance_cues": prov["has_ai_provenance_cues"],
            "ai_generation_cues": prov["ai_generation_cues"],
            "c2pa": prov["c2pa"],
            "exif": {
                "camera_make": prov["camera_make"],
                "camera_model": prov["camera_model"],
                "software": prov["software"],
                "date_original": prov["date_original"],
            },
        }

    def _action_validate_mrz(self, params: Dict[str, Any]) -> Dict[str, Any]:
        raw_mrz = params.get("raw_mrz") or params.get("mrz_string") or params.get("mrz")
        if not raw_mrz:
            return {
                "status": "error",
                "error_code": "missing_mrz",
                "message": "Parameter 'mrz_string' or 'raw_mrz' string or line array is required.",
            }

        eval_res = parse_and_validate_mrz(raw_mrz)
        verdict = "authentic_likely" if eval_res["mrz_valid"] else "tampered_likely"

        if eval_res["mrz_valid"]:
            doc_type = eval_res.get("fields", {}).get("document_type", "document")
            country = eval_res.get("fields", {}).get("issuer", "")
            summary = f"ICAO 9303 MRZ checksums valid for {country} {doc_type}."
        else:
            failures = ", ".join(eval_res.get("checksum_failures", []))
            summary = f"ICAO 9303 MRZ checksum verification failed: {failures}."

        return {
            "status": "ok",
            "action": "validate_mrz",
            "offline": True,
            "verdict": verdict,
            "summary": summary,
            "format": eval_res.get("format"),
            "mrz_valid": eval_res["mrz_valid"],
            "checksum_failures": eval_res["checksum_failures"],
            "fields": eval_res.get("fields", {}),
        }
