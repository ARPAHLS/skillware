"""Effect module for data_engineering/semantic_web_proxy.

Split by side effect so the extraction path stays testable offline:
``fetch_html`` is the only function that touches the network; everything else is
pure given its arguments.
"""

import ipaddress
import re
import socket
from importlib.util import find_spec
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests
import trafilatura

HEURISTIC_CHARS_PER_TOKEN = 4

BLOCKED_HOSTNAMES = frozenset({"localhost", "127.0.0.1", "::1", "0.0.0.0"})

OUTPUT_FORMATS = ("markdown", "json", "txt")

MAX_HTML_BYTES = 2_000_000

FETCH_TIMEOUT = 15

MAX_REDIRECTS = 5

USER_AGENT = "Skillware-SemanticWebProxy/0.1 (+https://github.com/ARPAHLS/skillware)"

HTML_CONTENT_TYPES = ("text/html", "application/xhtml+xml", "text/plain", "text/xml")

METADATA_FIELDS = ("title", "author", "date", "sitename", "hostname", "description")

# A page is only suspected of needing a browser when the extracted text is this
# short. Long extractions are self-evidently fine regardless of script volume.
MIN_SEMANTIC_CHARS = 200

# Share of the raw document taken up by inline and referenced script tags above
# which a near-empty extraction is treated as a client-rendered shell.
SCRIPT_BULK_RATIO = 0.35

SCRIPT_BLOCK = re.compile(r"<script\b[^>]*>.*?</script\s*>", re.IGNORECASE | re.DOTALL)

EMPTY_APP_ROOT = re.compile(
    r"""<(?:div|main)\b[^>]*\bid=["']?(?:root|app|__next|__nuxt)["']?[^>]*>\s*</(?:div|main)>""",
    re.IGNORECASE,
)


def _find_spec(name: str):
    """Indirection so tests can simulate a missing optional dependency."""
    return find_spec(name)


def count_tokens(text: str, tokenizer: str) -> Tuple[int, str]:
    """Estimate the token count of ``text``.

    Returns the count and the basis actually used. ``cl100k_base`` degrades to the
    heuristic when tiktoken is not installed, so the skill never fails on an
    optional dependency.
    """
    if not text:
        return 0, "heuristic"

    if tokenizer == "cl100k_base" and _find_spec("tiktoken") is not None:
        try:
            import tiktoken

            return len(tiktoken.get_encoding("cl100k_base").encode(text)), "cl100k_base"
        except Exception:
            pass

    return max(1, len(text) // HEURISTIC_CHARS_PER_TOKEN), "heuristic"


def is_safe_public_url(url: str) -> Tuple[bool, str]:
    """Reject anything that is not a publicly routable http(s) URL.

    Guards against pointing the fetcher at cloud metadata endpoints, loopback
    services, or non-http schemes such as ``file://``.
    """
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in {"http", "https"}:
        return False, "Only http and https URLs are allowed."

    hostname = parsed.hostname
    if not hostname:
        return False, "URL must include a hostname."

    lowered = hostname.lower()
    if lowered in BLOCKED_HOSTNAMES or lowered.endswith(".local"):
        return False, "Local or loopback hosts are blocked."

    try:
        for info in socket.getaddrinfo(hostname, None):
            ip = ipaddress.ip_address(info[4][0])
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_reserved
                or ip.is_multicast
                or ip.is_unspecified
            ):
                return False, "Private or non-public host addresses are blocked."
    except socket.gaierror:
        return False, "Hostname could not be resolved."
    except ValueError:
        return False, "Host address could not be parsed."

    return True, ""


def extract_semantic(
    html: str,
    url: Optional[str] = None,
    output_format: str = "markdown",
    include_comments: bool = False,
    include_tables: bool = True,
    include_links: bool = False,
    with_metadata: bool = True,
) -> Tuple[Optional[str], Dict[str, Any]]:
    """Reduce raw HTML to its semantic core.

    Pure with respect to the network: trafilatura is given the document, never a
    URL to download. ``url`` is passed only as a hint for metadata resolution.
    Returns ``(None, {})`` when nothing meaningful could be extracted.
    """
    payload = trafilatura.extract(
        html,
        url=url,
        output_format=output_format,
        include_comments=include_comments,
        include_tables=include_tables,
        include_links=include_links,
        with_metadata=(output_format == "json"),
    )

    if not payload or not payload.strip():
        return None, {}

    metadata: Dict[str, Any] = {}
    if with_metadata:
        metadata = extract_document_metadata(html, url)

    return payload, metadata


def extract_document_metadata(html: str, url: Optional[str] = None) -> Dict[str, Any]:
    """Return document metadata as a plain JSON-serializable dict."""
    try:
        document = trafilatura.extract_metadata(html, default_url=url)
    except Exception:
        return {}

    if document is None:
        return {}

    return {field: getattr(document, field, None) for field in METADATA_FIELDS}


def looks_like_js_shell(html: str, extracted_text: Optional[str]) -> bool:
    """Detect a page whose content is assembled client side.

    Fetch-only extraction returns almost nothing for these, so the skill warns
    rather than reporting a successful but empty result.
    """
    if extracted_text and len(extracted_text.strip()) >= MIN_SEMANTIC_CHARS:
        return False

    if not html:
        return False

    if EMPTY_APP_ROOT.search(html):
        return True

    script_chars = sum(len(match) for match in SCRIPT_BLOCK.findall(html))
    return (script_chars / len(html)) > SCRIPT_BULK_RATIO


def fetch_html(url: str) -> Tuple[str, str, Optional[int], str]:
    """Download a public web page.

    The only network-touching function in this module. Redirects are followed
    manually so that every hop is re-checked against the SSRF guard: validating
    only the initial URL would let a 302 walk into cloud metadata.

    Returns ``(html, final_url, http_status, reason)`` with ``reason == "ok"`` on
    success. Never raises into the host.
    """
    current_url = (url or "").strip()

    for _ in range(MAX_REDIRECTS + 1):
        ok, guard_reason = is_safe_public_url(current_url)
        if not ok:
            return "", current_url, None, guard_reason

        try:
            response = requests.get(
                current_url,
                timeout=FETCH_TIMEOUT,
                headers={"User-Agent": USER_AGENT},
                allow_redirects=False,
            )
        except requests.RequestException as exc:
            return "", current_url, None, f"Request failed: {exc}"

        location = response.headers.get("Location")
        if 300 <= response.status_code < 400 and location:
            current_url = urljoin(current_url, location)
            continue

        if response.status_code >= 400:
            return (
                "",
                current_url,
                response.status_code,
                f"Fetch returned HTTP {response.status_code}.",
            )

        content_type = response.headers.get("Content-Type", "").split(";")[0].strip()
        if content_type and not content_type.lower().startswith(HTML_CONTENT_TYPES):
            return (
                "",
                current_url,
                response.status_code,
                f"Unsupported content type: {content_type}.",
            )

        body = response.content[:MAX_HTML_BYTES]
        html = body.decode(response.encoding or "utf-8", errors="replace")
        return html, current_url, response.status_code, "ok"

    return "", current_url, None, f"Exceeded {MAX_REDIRECTS} redirects."
