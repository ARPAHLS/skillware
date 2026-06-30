import importlib.util
import os
from typing import Any, Dict, Optional

from skillware.core.base_skill import BaseSkill


def _import_budget():
    try:
        from . import budget as budget_module  # type: ignore[import-not-found]
    except ImportError:
        budget_path = os.path.join(os.path.dirname(__file__), "budget.py")
        spec = importlib.util.spec_from_file_location(
            "token_limiter_budget", budget_path
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load budget module from {budget_path}")
        budget_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(budget_module)
    return budget_module


_budget = _import_budget()
evaluate_budget = _budget.evaluate_budget
load_pricing = _budget.load_pricing
SCHEMA_VERSION = _budget.SCHEMA_VERSION


class TokenLimiterSkill(BaseSkill):
    """
    Deterministic token budget gate for autonomous agent loops.

    The skill does not terminate host processes or provider sessions itself.
    It returns CONTINUE, WARN, or FORCE_TERMINATE and the host loop must act.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._data_dir = os.path.join(os.path.dirname(__file__), "data")
        self._pricing = load_pricing(self._data_dir)
        self._turn_cache: Dict[str, Dict[str, Any]] = {}

    @property
    def manifest(self) -> Dict[str, Any]:
        manifest_path = os.path.join(os.path.dirname(__file__), "manifest.yaml")
        if os.path.exists(manifest_path):
            import yaml

            with open(manifest_path, "r", encoding="utf-8") as handle:
                return yaml.safe_load(handle)
        return {}

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return evaluate_budget(params, self._pricing, self._turn_cache)
        except Exception as exc:
            return {
                "status": "error",
                "message": f"Token budget evaluation failed: {exc}",
            }
