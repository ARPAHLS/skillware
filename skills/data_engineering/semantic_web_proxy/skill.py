"""Effect for data_engineering/semantic_web_proxy."""

import os
import sys
from typing import Any, Dict, List, Optional

import yaml

from skillware.core.base_skill import BaseSkill

try:
    from . import proxy
except ImportError:  # pragma: no cover - loader executes skill.py without a package
    sys.path.insert(0, os.path.dirname(__file__))
    import proxy


class SemanticWebProxySkill(BaseSkill):
    """Turn a noisy web page into a token-efficient semantic payload."""

    @property
    def manifest(self) -> Dict[str, Any]:
        manifest_path = os.path.join(os.path.dirname(__file__), "manifest.yaml")
        if os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as handle:
                return yaml.safe_load(handle)
        return {"name": "data_engineering/semantic_web_proxy", "version": "0.1.0"}

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        params = params or {}
        warnings: List[str] = []

        url = (params.get("url") or "").strip()
        html_content = params.get("html_content") or ""
        source = {
            "url": url or None,
            "final_url": None,
            "http_status": None,
            "fetched": False,
        }

        output_format = params.get("output_format") or "markdown"
        if output_format not in proxy.OUTPUT_FORMATS:
            supported = ", ".join(proxy.OUTPUT_FORMATS)
            return self._failure(
                f"Unsupported output_format '{output_format}'. Supported: {supported}.",
                source,
                output_format="markdown",
                warnings=warnings,
            )

        if not html_content and not url:
            return self._failure(
                "Provide either url or html_content.",
                source,
                output_format=output_format,
                warnings=warnings,
            )

        if not html_content:
            html_content, final_url, http_status, reason = proxy.fetch_html(url)
            source["final_url"] = final_url
            source["http_status"] = http_status
            if reason != "ok":
                return self._failure(
                    reason, source, output_format=output_format, warnings=warnings
                )
            source["fetched"] = True

        try:
            payload, metadata = proxy.extract_semantic(
                html_content,
                url=source["final_url"] or url or None,
                output_format=output_format,
                include_comments=bool(params.get("include_comments", False)),
                include_tables=bool(params.get("include_tables", True)),
                include_links=bool(params.get("include_links", False)),
                with_metadata=bool(params.get("with_metadata", True)),
            )
        except Exception as exc:  # pragma: no cover - defensive, never crash the host
            return self._failure(
                f"Extraction failed: {exc}",
                source,
                output_format=output_format,
                warnings=warnings,
            )

        needs_render = proxy.looks_like_js_shell(html_content, payload)

        if payload is None:
            message = (
                "No content could be extracted; the page appears to require a "
                "JavaScript render."
                if needs_render
                else "No extractable content was found in the document."
            )
            result = self._failure(
                message, source, output_format=output_format, warnings=warnings
            )
            if needs_render:
                result["warnings"].append("page_likely_requires_javascript")
            return result

        if needs_render:
            warnings.append("page_likely_requires_javascript")

        token_savings = self._token_savings(
            html_content,
            payload,
            params.get("tokenizer") or "heuristic",
            params.get("context_window"),
            warnings,
        )

        return {
            "status": "warning" if warnings else "success",
            "semantic_payload": payload,
            "output_format": output_format,
            "source": source,
            "metadata": metadata,
            "token_savings": token_savings,
            "warnings": warnings,
            "error": None,
        }

    def _token_savings(
        self,
        html_content: str,
        payload: str,
        tokenizer: str,
        context_window: Optional[int],
        warnings: List[str],
    ) -> Dict[str, Any]:
        original_tokens, basis = proxy.count_tokens(html_content, tokenizer)
        semantic_tokens, _ = proxy.count_tokens(payload, basis)

        if tokenizer != basis and "tokenizer_unavailable" not in warnings:
            warnings.append("tokenizer_unavailable")

        tokens_saved = max(0, original_tokens - semantic_tokens)
        reduction_pct = (
            round(tokens_saved / original_tokens * 100, 2) if original_tokens else 0.0
        )

        context_saved_pct = None
        window = context_window if isinstance(context_window, int) else None
        if window and window > 0:
            context_saved_pct = round(tokens_saved / window * 100, 2)

        return {
            "original_tokens": original_tokens,
            "semantic_tokens": semantic_tokens,
            "tokens_saved": tokens_saved,
            "reduction_pct": reduction_pct,
            "context_window": window,
            "context_saved_pct": context_saved_pct,
            "tokenizer": basis,
            "estimate": True,
        }

    def _failure(
        self,
        message: str,
        source: Dict[str, Any],
        output_format: str,
        warnings: List[str],
    ) -> Dict[str, Any]:
        return {
            "status": "error",
            "semantic_payload": "",
            "output_format": output_format,
            "source": source,
            "metadata": {},
            "token_savings": {
                "original_tokens": 0,
                "semantic_tokens": 0,
                "tokens_saved": 0,
                "reduction_pct": 0.0,
                "context_window": None,
                "context_saved_pct": None,
                "tokenizer": "heuristic",
                "estimate": True,
            },
            "warnings": warnings,
            "error": message,
        }
