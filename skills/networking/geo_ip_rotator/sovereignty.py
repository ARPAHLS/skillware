# Copyright (c) 2026 ARPA Hellenic Logical Systems
# SPDX-License-Identifier: MIT

"""Data sovereignty classification, compliance auditing, and jurisdiction fencing."""

from __future__ import annotations

import datetime
import hashlib
from typing import Any, Dict, Optional, Set, Tuple

# EEA / EU Member States under EU GDPR (Regulation (EU) 2016/679)
EEA_COUNTRIES: Set[str] = {
    "AT",
    "BE",
    "BG",
    "HR",
    "CY",
    "CZ",
    "DK",
    "EE",
    "FI",
    "FR",
    "DE",
    "GR",
    "HU",
    "IE",
    "IT",
    "LV",
    "LT",
    "LU",
    "MT",
    "NL",
    "PL",
    "PT",
    "RO",
    "SK",
    "SI",
    "ES",
    "SE",
    "IS",
    "LI",
    "NO",
}

# Standard high-risk or internationally sanctioned jurisdictions for sovereign guardrails
SANCTIONED_COUNTRIES: Set[str] = {
    "CU",
    "IR",
    "KP",
    "SY",
    "RU",
    "BY",
}

# Legal jurisdiction regime metadata
JURISDICTION_REGIMES: Dict[str, Dict[str, Any]] = {
    "EU_GDPR": {
        "name": "European Union General Data Protection Regulation",
        "citation": "Regulation (EU) 2016/679",
        "adequacy_recognized": True,
        "standard_contractual_clauses_required": False,
    },
    "UK_GDPR": {
        "name": "United Kingdom General Data Protection Regulation",
        "citation": "Data Protection Act 2018 / UK GDPR",
        "adequacy_recognized": True,
        "standard_contractual_clauses_required": False,
    },
    "SWISS_FADP": {
        "name": "Swiss Federal Act on Data Protection",
        "citation": "FADP (SR 235.1)",
        "adequacy_recognized": True,
        "standard_contractual_clauses_required": False,
    },
    "APPI_JAPAN": {
        "name": "Japan Act on the Protection of Personal Information",
        "citation": "Act No. 57 of 2003 as amended",
        "adequacy_recognized": True,
        "standard_contractual_clauses_required": False,
    },
    "PIPEDA_CANADA": {
        "name": "Canada Personal Information Protection and Electronic Documents Act",
        "citation": "S.C. 2000, c. 5",
        "adequacy_recognized": True,
        "standard_contractual_clauses_required": False,
    },
    "US_STATE_PRIVACY": {
        "name": "United States State Privacy Framework",
        "citation": "CCPA/CPRA, VCDPA, CPA and federal sectorial laws",
        "adequacy_recognized": True,
        "standard_contractual_clauses_required": True,
    },
    "LGPD_BRAZIL": {
        "name": "Brazil Lei Geral de Proteção de Dados Pessoais",
        "citation": "Law No. 13.709/2018",
        "adequacy_recognized": False,
        "standard_contractual_clauses_required": True,
    },
    "PDPA_SINGAPORE": {
        "name": "Singapore Personal Data Protection Act",
        "citation": "PDPA 2012 (No. 26 of 2012)",
        "adequacy_recognized": False,
        "standard_contractual_clauses_required": True,
    },
    "DPDP_INDIA": {
        "name": "India Digital Personal Data Protection Act",
        "citation": "Act No. 22 of 2023",
        "adequacy_recognized": False,
        "standard_contractual_clauses_required": True,
    },
    "POPIA_SOUTH_AFRICA": {
        "name": "South Africa Protection of Personal Information Act",
        "citation": "Act No. 4 of 2013",
        "adequacy_recognized": False,
        "standard_contractual_clauses_required": True,
    },
    "PRIVACY_ACT_AUSTRALIA": {
        "name": "Australia Privacy Act 1988",
        "citation": "Privacy Act 1988 (Cth)",
        "adequacy_recognized": False,
        "standard_contractual_clauses_required": True,
    },
    "TERRITORIAL_STANDARD": {
        "name": "Standard Territorial Sovereign Jurisdiction",
        "citation": "Local sovereign commercial laws",
        "adequacy_recognized": False,
        "standard_contractual_clauses_required": True,
    },
}


def classify_jurisdiction(country_code: str) -> Dict[str, Any]:
    """Classify the sovereign regulatory jurisdiction for a given country code."""
    cc = (country_code or "US").upper().strip()

    if cc in EEA_COUNTRIES:
        code = "EU_GDPR"
    elif cc == "GB":
        code = "UK_GDPR"
    elif cc == "CH":
        code = "SWISS_FADP"
    elif cc == "JP":
        code = "APPI_JAPAN"
    elif cc == "CA":
        code = "PIPEDA_CANADA"
    elif cc == "US":
        code = "US_STATE_PRIVACY"
    elif cc == "BR":
        code = "LGPD_BRAZIL"
    elif cc == "SG":
        code = "PDPA_SINGAPORE"
    elif cc == "IN":
        code = "DPDP_INDIA"
    elif cc == "ZA":
        code = "POPIA_SOUTH_AFRICA"
    elif cc == "AU":
        code = "PRIVACY_ACT_AUSTRALIA"
    else:
        code = "TERRITORIAL_STANDARD"

    regime = dict(JURISDICTION_REGIMES[code])
    regime["jurisdiction_code"] = code
    regime["country"] = cc
    regime["is_eea"] = cc in EEA_COUNTRIES
    return regime


def validate_jurisdiction_fence(
    country_code: str,
    fence_policy: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, str]:
    """Enforce enterprise sovereignty allowlist, blocklist, and EEA-only constraints."""
    cc = (country_code or "US").upper().strip()
    policy = fence_policy or {}

    # Check automatic sanctions blocklist unless explicitly waived
    enforce_sanctions = policy.get("enforce_sanctions_blocklist", True)
    if enforce_sanctions and cc in SANCTIONED_COUNTRIES:
        return (
            False,
            f"Egress country '{cc}' is prohibited under international compliance sanctions.",
        )

    # Check custom blocked countries
    blocked = [c.upper().strip() for c in policy.get("blocked_countries", [])]
    if cc in blocked:
        return (
            False,
            f"Egress country '{cc}' is explicitly blocked by enterprise jurisdiction policy.",
        )

    # Check EEA-only constraint
    if policy.get("allow_eea_only", False):
        if cc not in EEA_COUNTRIES:
            return (
                False,
                f"Egress country '{cc}' violates allow_eea_only policy (non-EEA jurisdiction).",
            )

    # Check custom allowed countries
    allowed = [c.upper().strip() for c in policy.get("allowed_countries", [])]
    if allowed and cc not in allowed:
        return (
            False,
            f"Egress country '{cc}' is not in the approved allowed_countries list.",
        )

    return True, ""


def generate_sovereignty_receipt(
    payload: str | bytes,
    country_code: str,
    egress_ip: str,
    target_url: str,
) -> Dict[str, Any]:
    """Generate a verifiable cryptographic audit receipt for multi-jurisdiction compliance."""
    if isinstance(payload, str):
        payload_bytes = payload.encode("utf-8")
    else:
        payload_bytes = payload or b""

    sha256_hash = hashlib.sha256(payload_bytes).hexdigest()
    now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
    jurisdiction = classify_jurisdiction(country_code)

    return {
        "audit_id": f"sovereign_receipt_{sha256_hash[:16]}",
        "timestamp_utc": now_utc,
        "payload_sha256": sha256_hash,
        "payload_size_bytes": len(payload_bytes),
        "target_url": target_url,
        "egress_ip": egress_ip,
        "country": country_code.upper().strip(),
        "is_eea": jurisdiction["is_eea"],
        "jurisdiction_code": jurisdiction["jurisdiction_code"],
        "regime_name": jurisdiction["name"],
        "legal_citation": jurisdiction["citation"],
        "adequacy_recognized": jurisdiction["adequacy_recognized"],
    }
