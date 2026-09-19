import importlib.util
import os
from typing import Any, Dict, Optional

from skillware.core.base_skill import BaseSkill


def _import_lexicon():
    try:
        from . import lexicon as lexicon_module  # type: ignore[import-not-found]
    except ImportError:
        lexicon_path = os.path.join(os.path.dirname(__file__), "lexicon.py")
        spec = importlib.util.spec_from_file_location(
            "korean_slang_lexicon", lexicon_path
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load lexicon module from {lexicon_path}")
        lexicon_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(lexicon_module)
    return lexicon_module


_lexicon = _import_lexicon()
execute_pack = _lexicon.execute_pack
load_pack = _lexicon.load_pack


class KoreanSlangSkill(BaseSkill):
    """
    Offline Korean Gen-Z slang lexicon: interpret, suggest, and lookup.

    execute() is deterministic. It never calls a model or the network.
    """

    _pack_cache: Optional[Dict[str, Any]] = None

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._pack = self._load_pack()

    @classmethod
    def _load_pack(cls) -> Dict[str, Any]:
        if cls._pack_cache is None:
            kb_dir = os.path.join(os.path.dirname(__file__), "kb")
            cls._pack_cache = load_pack(kb_dir)
        return cls._pack_cache

    @property
    def manifest(self) -> Dict[str, Any]:
        manifest_path = os.path.join(os.path.dirname(__file__), "manifest.yaml")
        if os.path.exists(manifest_path):
            import yaml

            with open(manifest_path, "r", encoding="utf-8") as handle:
                return yaml.safe_load(handle)
        return {"name": "linguistics/korean_slang", "version": "0.1.0"}

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        payload = params if isinstance(params, dict) else {}
        try:
            return execute_pack(self._pack, payload)
        except Exception as exc:
            return {
                "status": "error",
                "error": {"code": "PACK_FAILURE", "detail": str(exc)},
                "message": f"Korean slang pack failed: {exc}",
            }
