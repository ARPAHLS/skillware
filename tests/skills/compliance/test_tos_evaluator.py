import json
from unittest.mock import MagicMock, patch

from skillware.core.loader import SkillLoader


def get_skill():
    bundle = SkillLoader.load_skill("compliance/tos_evaluator")
    return bundle["module"].TOSEvaluatorSkill()


def make_response(text="", status_code=200, content_type="text/html; charset=utf-8"):
    response = MagicMock()
    response.text = text
    response.status_code = status_code
    response.headers = {"Content-Type": content_type}
    return response


def test_tos_evaluator_manifest_loads():
    bundle = SkillLoader.load_skill("compliance/tos_evaluator")
    assert bundle["manifest"]["name"] == "compliance/tos_evaluator"
    assert "target_url" in bundle["manifest"]["parameters"]["properties"]
    assert "intended_action" in bundle["manifest"]["parameters"]["properties"]


@patch("skills.compliance.tos_evaluator.skill.requests.Session.get")
def test_tos_evaluator_robots_disallow_returns_unsafe(mock_get):
    mock_get.return_value = make_response(
        text="User-agent: *\nDisallow: /\n", content_type="text/plain"
    )

    skill = get_skill()
    result = skill.execute(
        {
            "target_url": "https://hackernoon.com/tagged/ai",
            "intended_action": "scrape pricing data",
        }
    )

    assert result["verdict"] == "UNSAFE"
    assert result["robots_assessment"]["can_fetch"] is False


@patch("skills.compliance.tos_evaluator.skill.requests.Session.get")
def test_tos_evaluator_missing_robots_and_terms_returns_insufficient_evidence(mock_get):
    mock_get.return_value = make_response(status_code=404, text="not found")

    skill = get_skill()
    result = skill.execute(
        {
            "target_url": "https://hackernoon.com/archive",
            "intended_action": "index documentation pages",
            "max_terms_pages": 2,
        }
    )

    assert result["verdict"] == "INSUFFICIENT_EVIDENCE"
    assert result["tos_assessment"]["status"] == "insufficient_evidence"


@patch("skills.compliance.tos_evaluator.skill.requests.Session.get")
def test_tos_evaluator_policy_clause_blocks_scraping(mock_get):
    html = """
    <html>
      <body>
        <a href="/terms">Terms of Service</a>
        <h1>Terms of Service</h1>
        <h2>Automated Access</h2>
        <p>You may not scrape, crawl, or use automated means to extract content from this site.</p>
      </body>
    </html>
    """

    def side_effect(url, **kwargs):
        if url.endswith("/robots.txt"):
            return make_response(text="User-agent: *\nAllow: /\n", content_type="text/plain")
        return make_response(text=html)

    mock_get.side_effect = side_effect

    skill = get_skill()
    result = skill.execute(
        {
            "target_url": "https://hackernoon.com/tagged/startups",
            "intended_action": "scrape product listings",
        }
    )

    assert result["verdict"] == "UNSAFE"
    assert result["tos_assessment"]["status"] == "blocked"
    assert result["evidence"]


@patch("skills.compliance.tos_evaluator.skill.requests.Session.get")
def test_tos_evaluator_api_only_language_returns_caution(mock_get):
    html = """
    <html>
      <body>
        <a href="/api-terms">API Terms</a>
        <h1>Developer Terms</h1>
        <p>Automated access is permitted only through our official API and is subject to reasonable rate limits.</p>
      </body>
    </html>
    """

    def side_effect(url, **kwargs):
        if url.endswith("/robots.txt"):
            return make_response(text="User-agent: *\nAllow: /\n", content_type="text/plain")
        return make_response(text=html)

    mock_get.side_effect = side_effect

    skill = get_skill()
    result = skill.execute(
        {
            "target_url": "https://hackernoon.com/api",
            "intended_action": "crawl catalog pages with a bot",
        }
    )

    assert result["verdict"] == "CAUTION"
    assert "API" in result["recommended_next_step"]


@patch("skills.compliance.tos_evaluator.skill.requests.Session.get")
def test_tos_evaluator_allowed_policy_can_return_safe(mock_get):
    html = """
    <html>
      <body>
        <a href="/developer-terms">Developer Terms</a>
        <h1>Developer Terms</h1>
        <p>Developers may access our public API for automated integrations.</p>
      </body>
    </html>
    """

    def side_effect(url, **kwargs):
        if url.endswith("/robots.txt"):
            return make_response(text="User-agent: *\nAllow: /\n", content_type="text/plain")
        return make_response(text=html)

    mock_get.side_effect = side_effect

    skill = get_skill()
    result = skill.execute(
        {
            "target_url": "https://hackernoon.com/api/v1/stories",
            "intended_action": "use the api for automated integration",
        }
    )

    assert result["verdict"] == "SAFE"
    assert result["is_safe_to_proceed"] is True


@patch("skills.compliance.tos_evaluator.skill.requests.Session.get")
def test_tos_evaluator_llm_fallback_is_mockable(mock_get):
    html = """
    <html>
      <body>
        <a href="/terms">Terms</a>
        <h1>Terms</h1>
        <p>Automated access may be allowed only with prior written consent.</p>
      </body>
    </html>
    """

    def side_effect(url, **kwargs):
        if url.endswith("/robots.txt"):
            return make_response(text="User-agent: *\nAllow: /\n", content_type="text/plain")
        return make_response(text=html)

    mock_get.side_effect = side_effect

    bundle = SkillLoader.load_skill("compliance/tos_evaluator")
    mock_genai = MagicMock()
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = json.dumps(
        {
            "verdict": "CAUTION",
            "confidence_score": 0.81,
            "rationale": "The clause conditions automation on prior written consent.",
        }
    )
    mock_client.models.generate_content.return_value = mock_response
    mock_genai.Client.return_value = mock_client
    mock_types = MagicMock()
    bundle["module"].genai = mock_genai
    bundle["module"].types = mock_types
    skill = bundle["module"].TOSEvaluatorSkill()
    with patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"}):
        result = skill.execute(
            {
                "target_url": "https://hackernoon.com/tagged/devops",
                "intended_action": "crawl documentation pages",
                "use_llm_evaluator": True,
                "llm_provider": "gemini",
                "llm_model": "gemini-2.5-flash-lite",
            }
        )

    assert result["verdict"] == "CAUTION"
    assert result["llm_assessment"]["status"] == "used"
    assert result["llm_assessment"]["model"] == "gemini-2.5-flash-lite"
