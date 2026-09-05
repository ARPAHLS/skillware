"""Bundle tests for data_engineering/semantic_web_proxy.

Fully offline: every test drives the pure extraction path or patches the single
network entry point on the effect module.
"""

import os

import pytest
import yaml

from . import proxy as proxy_module
from .skill import SemanticWebProxySkill

ARTICLE_HTML = """<html><head><title>Quarterly Results</title>
<meta name="author" content="Jane Doe">
<meta property="article:published_time" content="2026-01-15">
<script>var tracker = 1; window.ads.load();</script>
<style>.banner { color: red; }</style></head>
<body>
<nav><a href="/home">Home</a><a href="/about">About</a><a href="/jobs">Careers</a></nav>
<div class="advert">SPONSORED - BUY NOW - LIMITED TIME OFFER</div>
<article>
<h1>Quarterly Results</h1>
<p>Revenue grew by eleven percent across the period, driven mainly by renewals in
the enterprise segment and a modest recovery in new logo acquisition.</p>
<h2>Outlook</h2>
<p>Management reaffirmed guidance for the full year and pointed to margin expansion
in the second half as the primary driver of operating leverage.</p>
</article>
<footer>Copyright 2026 Example Corp. All rights reserved. Privacy. Terms.</footer>
</body></html>"""


@pytest.fixture
def skill():
    return SemanticWebProxySkill()


@pytest.fixture
def manifest():
    manifest_path = os.path.join(os.path.dirname(__file__), "manifest.yaml")
    with open(manifest_path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


class TestCountTokens:
    def test_heuristic_uses_four_characters_per_token(self):
        count, basis = proxy_module.count_tokens("a" * 400, "heuristic")
        assert count == 100
        assert basis == "heuristic"

    def test_heuristic_never_returns_zero_for_non_empty_text(self):
        count, _ = proxy_module.count_tokens("hi", "heuristic")
        assert count == 1

    def test_empty_text_counts_as_zero(self):
        count, _ = proxy_module.count_tokens("", "heuristic")
        assert count == 0

    def test_cl100k_falls_back_to_heuristic_when_tiktoken_missing(self, monkeypatch):
        monkeypatch.setattr(proxy_module, "_find_spec", lambda name: None)
        count, basis = proxy_module.count_tokens("a" * 400, "cl100k_base")
        assert count == 100
        assert basis == "heuristic"


class TestIsSafePublicUrl:
    @pytest.mark.parametrize(
        "url",
        [
            "file:///etc/passwd",
            "ftp://example.com/x",
            "gopher://example.com/",
            "http://localhost/admin",
            "http://127.0.0.1/admin",
            "http://[::1]/admin",
            "http://printer.local/status",
            "http://169.254.169.254/latest/meta-data/",
            "http://10.0.0.5/internal",
            "http://192.168.1.1/router",
            "https://",
        ],
    )
    def test_rejects_unsafe_urls(self, url):
        ok, reason = proxy_module.is_safe_public_url(url)
        assert ok is False
        assert reason

    def test_accepts_public_https_url(self, monkeypatch):
        monkeypatch.setattr(
            proxy_module.socket,
            "getaddrinfo",
            lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 0))],
        )
        ok, reason = proxy_module.is_safe_public_url("https://example.com/page")
        assert ok is True
        assert reason == ""

    def test_rejects_host_that_does_not_resolve(self, monkeypatch):
        def boom(*args, **kwargs):
            raise proxy_module.socket.gaierror("nope")

        monkeypatch.setattr(proxy_module.socket, "getaddrinfo", boom)
        ok, reason = proxy_module.is_safe_public_url("https://no-such-host.example")
        assert ok is False
        assert "resolve" in reason.lower()


THREAD_HTML = """<html><head><title>Ask HN: favourite editor</title></head><body>
<nav><a href="/newest">new</a><a href="/threads">threads</a></nav>
<article><h1>Ask HN: favourite editor</h1>
<p>I have been bouncing between editors for a year now and I would like to hear what
other people have settled on for long term maintenance work on large codebases.</p>
</article>
<div id="comments" class="comments">
<div class="comment"><p>alice: I moved back to vim after a decade away and the muscle
memory came back within about a week, which surprised me quite a lot.</p></div>
<div class="comment"><p>bob: The editor matters far less than the language server you
put behind it, in my honest experience across several very different teams.</p></div>
</div></body></html>"""

JS_SHELL_HTML = """<html><head><title>Dashboard</title>
<script src="/static/app.bundle.js"></script>
<script>window.__STATE__={"user":null};function boot(){/* a lot of application code */}
var padding="%s";</script></head>
<body><div id="root"></div><noscript>You need JavaScript.</noscript></body></html>""" % (
    "x" * 4000
)


class TestExtractSemantic:
    def test_drops_navigation_ads_and_footer_boilerplate(self):
        payload, _ = proxy_module.extract_semantic(ARTICLE_HTML)
        assert "Revenue grew by eleven percent" in payload
        assert "SPONSORED" not in payload
        assert "Careers" not in payload
        assert "All rights reserved" not in payload

    def test_markdown_preserves_heading_structure(self):
        payload, _ = proxy_module.extract_semantic(
            ARTICLE_HTML, output_format="markdown"
        )
        assert "# Quarterly Results" in payload
        assert "## Outlook" in payload

    def test_txt_format_drops_markdown_markers(self):
        payload, _ = proxy_module.extract_semantic(ARTICLE_HTML, output_format="txt")
        assert "Revenue grew by eleven percent" in payload
        assert "## Outlook" not in payload

    def test_json_format_returns_parseable_json(self):
        import json

        payload, _ = proxy_module.extract_semantic(ARTICLE_HTML, output_format="json")
        assert json.loads(payload)["title"] == "Quarterly Results"

    def test_metadata_is_extracted_when_requested(self):
        _, metadata = proxy_module.extract_semantic(ARTICLE_HTML, with_metadata=True)
        assert metadata["title"] == "Quarterly Results"
        assert metadata["author"] == "Jane Doe"
        assert metadata["date"] == "2026-01-15"

    def test_metadata_is_empty_when_not_requested(self):
        _, metadata = proxy_module.extract_semantic(ARTICLE_HTML, with_metadata=False)
        assert metadata == {}

    def test_comments_excluded_by_default(self):
        payload, _ = proxy_module.extract_semantic(THREAD_HTML)
        assert "bouncing between editors" in payload
        assert "muscle" not in payload

    def test_comments_included_when_requested(self):
        payload, _ = proxy_module.extract_semantic(THREAD_HTML, include_comments=True)
        assert "muscle" in payload

    def test_returns_none_when_nothing_extractable(self):
        payload, metadata = proxy_module.extract_semantic("<html><body></body></html>")
        assert payload is None
        assert metadata == {}


class TestLooksLikeJsShell:
    def test_detects_empty_spa_root_with_script_bulk(self):
        assert proxy_module.looks_like_js_shell(JS_SHELL_HTML, "") is True

    def test_real_article_is_not_flagged(self):
        payload, _ = proxy_module.extract_semantic(ARTICLE_HTML)
        assert proxy_module.looks_like_js_shell(ARTICLE_HTML, payload) is False

    def test_short_page_without_script_bulk_is_not_flagged(self):
        html = "<html><body><p>Tiny but honest page.</p></body></html>"
        assert proxy_module.looks_like_js_shell(html, "Tiny but honest page.") is False


class FakeResponse:
    def __init__(self, status_code=200, body=b"<html></html>", headers=None):
        self.status_code = status_code
        self.content = body
        self.headers = headers or {"Content-Type": "text/html; charset=utf-8"}
        self.encoding = "utf-8"


@pytest.fixture
def allow_public_dns(monkeypatch):
    """Resolve every host to a public address unless the test says otherwise."""
    monkeypatch.setattr(
        proxy_module.socket,
        "getaddrinfo",
        lambda host, *a, **k: [(2, 1, 6, "", ("93.184.216.34", 0))],
    )


class TestFetchHtml:
    def test_returns_body_and_status_on_success(self, monkeypatch, allow_public_dns):
        monkeypatch.setattr(
            proxy_module.requests,
            "get",
            lambda *a, **k: FakeResponse(body=b"<html><p>hello</p></html>"),
        )
        html, final_url, status, reason = proxy_module.fetch_html(
            "https://example.com/a"
        )
        assert "hello" in html
        assert final_url == "https://example.com/a"
        assert status == 200
        assert reason == "ok"

    def test_does_not_request_an_unsafe_url(self, monkeypatch):
        def boom(*args, **kwargs):
            raise AssertionError("network must not be touched for a blocked URL")

        monkeypatch.setattr(proxy_module.requests, "get", boom)
        html, _, status, reason = proxy_module.fetch_html("http://127.0.0.1/admin")
        assert html == ""
        assert status is None
        assert "blocked" in reason.lower()

    def test_follows_a_public_redirect_and_reports_the_final_url(
        self, monkeypatch, allow_public_dns
    ):
        responses = [
            FakeResponse(302, b"", {"Location": "https://example.com/final"}),
            FakeResponse(200, b"<html><p>arrived</p></html>"),
        ]
        monkeypatch.setattr(
            proxy_module.requests, "get", lambda *a, **k: responses.pop(0)
        )
        html, final_url, status, reason = proxy_module.fetch_html(
            "https://example.com/start"
        )
        assert "arrived" in html
        assert final_url == "https://example.com/final"
        assert status == 200
        assert reason == "ok"

    def test_rejects_a_redirect_into_link_local_metadata(self, monkeypatch):
        """The pre-flight check alone would miss this; every hop is revalidated."""

        def resolve(host, *args, **kwargs):
            if host == "169.254.169.254":
                return [(2, 1, 6, "", ("169.254.169.254", 0))]
            return [(2, 1, 6, "", ("93.184.216.34", 0))]

        monkeypatch.setattr(proxy_module.socket, "getaddrinfo", resolve)
        monkeypatch.setattr(
            proxy_module.requests,
            "get",
            lambda *a, **k: FakeResponse(
                302, b"", {"Location": "http://169.254.169.254/latest/meta-data/"}
            ),
        )
        html, _, _, reason = proxy_module.fetch_html("https://example.com/redirector")
        assert html == ""
        assert "blocked" in reason.lower()

    def test_stops_after_the_redirect_limit(self, monkeypatch, allow_public_dns):
        monkeypatch.setattr(
            proxy_module.requests,
            "get",
            lambda *a, **k: FakeResponse(
                302, b"", {"Location": "https://example.com/loop"}
            ),
        )
        html, _, _, reason = proxy_module.fetch_html("https://example.com/loop")
        assert html == ""
        assert "redirect" in reason.lower()

    def test_rejects_non_html_content_type(self, monkeypatch, allow_public_dns):
        monkeypatch.setattr(
            proxy_module.requests,
            "get",
            lambda *a, **k: FakeResponse(headers={"Content-Type": "application/zip"}),
        )
        html, _, _, reason = proxy_module.fetch_html("https://example.com/a.zip")
        assert html == ""
        assert "content type" in reason.lower()

    def test_truncates_oversized_bodies(self, monkeypatch, allow_public_dns):
        oversized = b"<html>" + b"x" * (proxy_module.MAX_HTML_BYTES + 5000)
        monkeypatch.setattr(
            proxy_module.requests, "get", lambda *a, **k: FakeResponse(body=oversized)
        )
        html, _, _, reason = proxy_module.fetch_html("https://example.com/big")
        assert len(html) <= proxy_module.MAX_HTML_BYTES
        assert reason == "ok"

    def test_reports_http_errors_without_raising(self, monkeypatch, allow_public_dns):
        monkeypatch.setattr(
            proxy_module.requests, "get", lambda *a, **k: FakeResponse(404, b"nope")
        )
        html, _, status, reason = proxy_module.fetch_html("https://example.com/missing")
        assert html == ""
        assert status == 404
        assert "404" in reason

    def test_reports_transport_failures_without_raising(
        self, monkeypatch, allow_public_dns
    ):
        def boom(*args, **kwargs):
            raise proxy_module.requests.RequestException("connection reset")

        monkeypatch.setattr(proxy_module.requests, "get", boom)
        html, _, _, reason = proxy_module.fetch_html("https://example.com/flaky")
        assert html == ""
        assert "connection reset" in reason


class TestManifestContract:
    def test_manifest_identity_matches_registry_layout(self, skill, manifest):
        assert manifest["name"] == "data_engineering/semantic_web_proxy"
        assert skill.manifest["name"] == manifest["name"]
        assert skill.manifest["version"] == manifest["version"]

    def test_execute_returns_every_declared_output_key(self, skill, manifest):
        result = skill.execute({"html_content": ARTICLE_HTML})
        for key in manifest["outputs"]:
            assert key in result, f"missing declared output: {key}"

    def test_declared_parameters_validate(self, skill):
        assert skill.validate_params(
            {"url": "https://example.com/a", "output_format": "markdown"}
        )


class TestExecuteOfflinePath:
    def test_extracts_from_supplied_html(self, skill):
        result = skill.execute({"html_content": ARTICLE_HTML})
        assert result["status"] == "success"
        assert result["error"] is None
        assert "Revenue grew by eleven percent" in result["semantic_payload"]
        assert result["source"]["fetched"] is False
        assert result["metadata"]["title"] == "Quarterly Results"

    def test_html_content_wins_over_url_and_skips_the_network(self, skill, monkeypatch):
        def boom(*args, **kwargs):
            raise AssertionError("fetch must not run when html_content is supplied")

        monkeypatch.setattr(proxy_module, "fetch_html", boom)
        result = skill.execute(
            {"html_content": ARTICLE_HTML, "url": "https://example.com/a"}
        )
        assert result["status"] == "success"
        assert result["source"]["fetched"] is False

    def test_missing_both_inputs_is_a_structured_error(self, skill):
        result = skill.execute({})
        assert result["status"] == "error"
        assert result["semantic_payload"] == ""
        assert "url" in result["error"] and "html_content" in result["error"]

    def test_unextractable_html_is_a_structured_error(self, skill):
        result = skill.execute({"html_content": "<html><body></body></html>"})
        assert result["status"] == "error"
        assert result["error"]

    def test_rejects_unknown_output_format(self, skill):
        result = skill.execute({"html_content": ARTICLE_HTML, "output_format": "yaml"})
        assert result["status"] == "error"
        assert "output_format" in result["error"]

    def test_javascript_shell_warns_instead_of_reporting_success(self, skill):
        result = skill.execute({"html_content": JS_SHELL_HTML})
        assert result["status"] == "warning"
        assert "page_likely_requires_javascript" in result["warnings"]


class TestExecuteFetchPath:
    def test_uses_the_guarded_fetcher_and_records_provenance(self, skill, monkeypatch):
        monkeypatch.setattr(
            proxy_module,
            "fetch_html",
            lambda url: (ARTICLE_HTML, "https://example.com/final", 200, "ok"),
        )
        result = skill.execute({"url": "https://example.com/start"})
        assert result["status"] == "success"
        assert result["source"] == {
            "url": "https://example.com/start",
            "final_url": "https://example.com/final",
            "http_status": 200,
            "fetched": True,
        }

    def test_blocked_url_surfaces_as_an_error(self, skill, monkeypatch):
        def boom(*args, **kwargs):
            raise AssertionError("network must not be touched for a blocked URL")

        monkeypatch.setattr(proxy_module.requests, "get", boom)
        result = skill.execute({"url": "http://169.254.169.254/latest/meta-data/"})
        assert result["status"] == "error"
        assert "blocked" in result["error"].lower()

    def test_fetch_failure_surfaces_as_an_error(self, skill, monkeypatch):
        monkeypatch.setattr(
            proxy_module,
            "fetch_html",
            lambda url: ("", url, 404, "Fetch returned HTTP 404."),
        )
        result = skill.execute({"url": "https://example.com/missing"})
        assert result["status"] == "error"
        assert "404" in result["error"]
        assert result["source"]["http_status"] == 404


class TestTokenSavings:
    def test_reports_reduction_against_the_raw_document(self, skill):
        savings = skill.execute({"html_content": ARTICLE_HTML})["token_savings"]
        assert savings["original_tokens"] > savings["semantic_tokens"]
        assert (
            savings["tokens_saved"]
            == savings["original_tokens"] - savings["semantic_tokens"]
        )
        assert 0 < savings["reduction_pct"] <= 100
        assert savings["estimate"] is True
        assert savings["tokenizer"] == "heuristic"

    def test_context_share_is_absent_without_a_context_window(self, skill):
        savings = skill.execute({"html_content": ARTICLE_HTML})["token_savings"]
        assert savings["context_window"] is None
        assert savings["context_saved_pct"] is None

    def test_context_share_is_reported_when_the_host_supplies_a_window(self, skill):
        savings = skill.execute({"html_content": ARTICLE_HTML, "context_window": 1000})[
            "token_savings"
        ]
        assert savings["context_window"] == 1000
        expected = round(savings["tokens_saved"] / 1000 * 100, 2)
        assert savings["context_saved_pct"] == expected

    def test_tokenizer_fallback_is_reported_as_a_warning(self, skill, monkeypatch):
        monkeypatch.setattr(proxy_module, "_find_spec", lambda name: None)
        result = skill.execute(
            {"html_content": ARTICLE_HTML, "tokenizer": "cl100k_base"}
        )
        assert result["token_savings"]["tokenizer"] == "heuristic"
        assert "tokenizer_unavailable" in result["warnings"]


class TestEmptyJavascriptShell:
    """A shell with no noscript fallback extracts nothing at all."""

    EMPTY_SHELL = (
        '<html><head><script>var a="%s";</script></head>'
        '<body><div id="root"></div></body></html>' % ("y" * 3000)
    )

    def test_empty_shell_errors_but_still_names_the_cause(self, skill):
        result = skill.execute({"html_content": self.EMPTY_SHELL})
        assert result["status"] == "error"
        assert "JavaScript" in result["error"]
        assert "page_likely_requires_javascript" in result["warnings"]
