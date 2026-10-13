"""Normalize a full OFAC SDN.CSV publication into wallet-screening records.

Re-run (do not hand-edit the JSON):

    python skills/finance/wallet_screening/maintenance/normalize_ofac_sdn.py \
        --input /path/to/SDN.CSV \
        --out-dir skills/finance/wallet_screening/data \
        --source-last-modified 2026-10-13T14:02:04Z

Download the comprehensive SDN.CSV from the Sanctions List Service
(https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN.CSV).
OFAC FAQ 90 says to refresh from the comprehensive file. This parser does not
apply SDN delta XML. A missing address in the new snapshot means it was not
observed in that file, not that OFAC delisted it.

Only currency code ETH with a 40-hex identifier is copied to ``address`` for
the Ethereum sanctions index. Other currencies are stored with their literal
identifier and are not treated as Ethereum, even when the identifier is ``0x``.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

PARSER_VERSION = "1"
SOURCE_NAME = "OFAC SDN"
SOURCE_URL = (
    "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN.CSV"
)
_ETH_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
_MENTION_RE = re.compile(
    r"(?:alt\.\s+)?Digital Currency Address\s*-\s*([A-Za-z0-9]{2,12})(?:\s+(\S+))?"
)


class OfacParseError(ValueError):
    """SDN.CSV could not be parsed. Distinct from an empty wallet set."""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_sdn_csv(text: str) -> Dict[str, Any]:
    """Parse SDN.CSV text into published observations and a quarantine list."""
    if text.startswith("\ufeff"):
        text = text.lstrip("\ufeff")
    if not text.strip():
        raise OfacParseError("SDN.CSV is empty.")

    try:
        rows = list(csv.reader(io.StringIO(text)))
    except csv.Error as exc:
        raise OfacParseError(f"SDN.CSV could not be read: {exc}") from exc

    wide = [row for row in rows if len(row) >= 12]
    if not wide:
        raise OfacParseError(
            "SDN.CSV has no 12-column rows. Refusing to treat this as an empty wallet set."
        )

    records: List[Dict[str, Any]] = []
    quarantine: List[Dict[str, Any]] = []
    raw_occurrences = 0
    seen_distinct = set()

    for row in wide:
        uid = (row[0] or "").strip()
        name = (row[1] or "").strip()
        program = _clean_program(row[3] or "")
        remarks = row[11] or ""
        for match in _MENTION_RE.finditer(remarks):
            raw_occurrences += 1
            currency = match.group(1).upper()
            literal = (match.group(2) or "").rstrip(".;,)")
            published, rejected = _project_identifier(
                uid=uid,
                name=name,
                program=program,
                currency=currency,
                literal=literal,
            )
            if rejected is not None:
                quarantine.append(rejected)
                continue
            assert published is not None
            records.append(published)
            distinct_id = published["extra"]["match_key"] or literal
            seen_distinct.add((currency, distinct_id))

    return {
        "records": records,
        "quarantine": quarantine,
        "raw_occurrences": raw_occurrences,
        "distinct_typed_wallets": len(seen_distinct),
        "empty_wallet_set": raw_occurrences == 0 and not quarantine,
    }


def _clean_program(value: str) -> str:
    """Repair SDN.CSV program fields whose leading ``[`` was consumed as a quote.

    OFAC writes some programs as ``"[IRAN] [SDGT]"``. The CSV parser then
    yields ``IRAN] [SDGT`` because the opening bracket sits inside the quote.
    """
    value = value.strip()
    if "]" in value and not value.startswith("["):
        value = "[" + value
    if value.startswith("[") and not value.endswith("]"):
        value = value + "]"
    return value


def _project_identifier(
    *,
    uid: str,
    name: str,
    program: str,
    currency: str,
    literal: str,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    if not literal:
        return None, _quarantine(uid, name, currency, literal, "missing_identifier")

    indexed = False
    match_key = None
    transform = None
    if currency == "ETH":
        if not _ETH_ADDRESS_RE.match(literal):
            return None, _quarantine(
                uid, name, currency, literal, "invalid_eth_identifier"
            )
        match_key = literal.lower()
        transform = "eth_lowercase"
        indexed = True

    extra = {
        "uid": uid,
        "entity_name": name,
        "programs": program,
        "literal_currency": currency,
        "literal_identifier": literal,
        "match_key": match_key,
        "match_transform": transform,
        "indexed_for_eth_screening": indexed,
    }
    record: Dict[str, Any] = {
        "network": currency,
        "label": name or "OFAC SDN",
        "source": SOURCE_NAME,
        "source_url": SOURCE_URL,
        "reason": program or "SDN",
        "jurisdiction": "US",
        "extra": extra,
    }
    if indexed and match_key:
        record["address"] = match_key
    return record, None


def _quarantine(
    uid: str, name: str, currency: str, literal: str, reason: str
) -> Dict[str, Any]:
    return {
        "uid": uid,
        "entity_name": name,
        "literal_currency": currency,
        "literal_identifier": literal,
        "reason": reason,
    }


def build_manifest(
    *,
    sha256: str,
    downloaded_at: str,
    source_last_modified: Optional[str],
    parsed: Dict[str, Any],
) -> Dict[str, Any]:
    eth_indexed = sum(1 for row in parsed["records"] if row.get("address"))
    return {
        "source": SOURCE_NAME,
        "source_url": SOURCE_URL,
        "sha256": sha256,
        "downloaded_at": downloaded_at,
        "source_last_modified": source_last_modified,
        "parser_version": PARSER_VERSION,
        "raw_currency_identifier_occurrences": parsed["raw_occurrences"],
        "distinct_typed_wallets": parsed["distinct_typed_wallets"],
        "eth_indexed": eth_indexed,
        "published_records": len(parsed["records"]),
        "quarantined": len(parsed["quarantine"]),
        "empty_wallet_set": parsed["empty_wallet_set"],
        "notes": [
            "Full SDN.CSV replacement. Not a delta patch.",
            "Absence from this snapshot is not a delisting or legal clearance.",
            "Only currency code ETH is indexed for Ethereum screening.",
            "Aban Tether is an entity-level designation in the Aug 2026 action "
            "and has no digital-currency identifier in SDN remarks, so address screening cannot hit it.",
        ],
    }


def write_snapshot(
    csv_bytes: bytes,
    out_dir: str,
    *,
    downloaded_at: Optional[str] = None,
    source_last_modified: Optional[str] = None,
) -> Dict[str, Any]:
    import os

    try:
        text = csv_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise OfacParseError("SDN.CSV is not UTF-8.") from exc

    parsed = parse_sdn_csv(text)
    manifest = build_manifest(
        sha256=hashlib.sha256(csv_bytes).hexdigest(),
        downloaded_at=downloaded_at or _now(),
        source_last_modified=source_last_modified,
        parsed=parsed,
    )
    os.makedirs(out_dir, exist_ok=True)
    _dump(os.path.join(out_dir, "normalized_ofac_sdn.json"), parsed["records"])
    _dump(os.path.join(out_dir, "ofac_sdn_quarantine.json"), parsed["quarantine"])
    _dump(os.path.join(out_dir, "ofac_sdn_manifest.json"), manifest)
    return manifest


def _dump(path: str, payload: Any) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", required=True, help="Path to a full SDN.CSV download"
    )
    parser.add_argument("--out-dir", required=True, help="Skill data directory")
    parser.add_argument("--downloaded-at", default=None)
    parser.add_argument("--source-last-modified", default=None)
    args = parser.parse_args()
    with open(args.input, "rb") as handle:
        raw = handle.read()
    manifest = write_snapshot(
        raw,
        args.out_dir,
        downloaded_at=args.downloaded_at,
        source_last_modified=args.source_last_modified,
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
