# Copyright (c) 2026 ARPA Hellenic Logical Systems
# SPDX-License-Identifier: MIT

"""Regional HTTP header synthesis and anti-fingerprinting harmonization."""

from __future__ import annotations

from typing import Dict, Optional

# Locale-specific Accept-Language strings matching sovereign demographics
REGIONAL_LANGUAGES: Dict[str, str] = {
    "US": "en-US,en;q=0.9",
    "GB": "en-GB,en;q=0.9,en-US;q=0.8",
    "DE": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
    "FR": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "JP": "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7",
    "KR": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "BR": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "ES": "es-ES,es;q=0.9,en-US;q=0.8,en;q=0.7",
    "IT": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
    "NL": "nl-NL,nl;q=0.9,en-US;q=0.8,en;q=0.7",
    "SE": "sv-SE,sv;q=0.9,en-US;q=0.8,en;q=0.7",
    "CH": "de-CH,de;q=0.9,fr-CH;q=0.8,en-US;q=0.7",
    "IN": "en-IN,en;q=0.9,hi;q=0.8,en-US;q=0.7",
    "SG": "en-SG,en;q=0.9,zh-SG;q=0.8,en-US;q=0.7",
    "CA": "en-CA,en;q=0.9,fr-CA;q=0.8,en-US;q=0.7",
    "AU": "en-AU,en;q=0.9,en-GB;q=0.8,en-US;q=0.7",
    "ZA": "en-ZA,en;q=0.9,af;q=0.8,en-US;q=0.7",
    "AE": "ar-AE,ar;q=0.9,en-US;q=0.8,en;q=0.7",
}

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
)


def build_regional_headers(
    country_code: str,
    custom_headers: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """Synthesize authentic regional browser headers to minimize anti-bot challenges."""
    cc = (country_code or "US").upper().strip()
    accept_lang = REGIONAL_LANGUAGES.get(cc, "en-US,en;q=0.9")

    headers: Dict[str, str] = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,image/apng,*/*;q=0.8"
        ),
        "Accept-Language": accept_lang,
        "Accept-Encoding": "gzip, deflate, br",
        "Sec-Ch-Ua": '"Google Chrome";v="129", "Not=A?Brand";v="8", "Chromium";v="129"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    }

    if custom_headers:
        for k, v in custom_headers.items():
            headers[k] = str(v)

    return headers
