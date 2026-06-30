import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

from skillware.core.loader import SkillLoader

REPO_ROOT = Path(__file__).resolve().parents[3]
EXAMPLES_DIR = REPO_ROOT / "examples"


def _load_example_module(filename: str):
    path = EXAMPLES_DIR / filename
    spec = importlib.util.spec_from_file_location(filename.replace(".py", ""), path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_loader_loads_token_limiter():
    bundle = SkillLoader.load_skill("monitoring/token_limiter")
    assert bundle["manifest"]["name"] == "monitoring/token_limiter"
    skill = bundle["module"].TokenLimiterSkill()
    result = skill.execute(
        {
            "task_id": "loader-smoke",
            "current_token_count": 10,
            "max_allowed_tokens": 100,
        }
    )
    assert result["status"] == "ready"
    assert result["action"] == "CONTINUE"


def test_local_loop_example_smoke():
    module = _load_example_module("token_limiter_loop.py")
    module.run_demo()


@patch("google.genai.Client")
def test_gemini_example_smoke(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    module = _load_example_module("gemini_token_limiter.py")
    module.run_demo(live_gemini=False)


@patch("anthropic.Anthropic")
def test_claude_example_smoke(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    module = _load_example_module("claude_token_limiter.py")
    module.run_demo(live_claude=False)
