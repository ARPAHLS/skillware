"""
Mocked Document API flow demo for finance/uk_companies_house_handler (v1.4.0).

Demonstrates discover -> pick -> download without a live API key:
  list_downloadable_documents -> get_document_metadata -> fetch_document
including redirect-without-auth and document_too_large.

Usage:
  python examples/uk_companies_house_document_flow_demo.py
"""

from __future__ import annotations

import base64
from contextlib import contextmanager
from typing import Any, Iterator
from unittest.mock import MagicMock, patch

from skillware.core.loader import SkillLoader

SKILL_ID = "finance/uk_companies_house_handler"

MOCK_FILINGS = {
    "total_count": 2,
    "filing_history_status": "filing-history-available",
    "items": [
        {
            "date": "2024-03-15",
            "category": "accounts",
            "type": "AA",
            "description": "accounts-with-accounts-type-full",
            "transaction_id": "tx-accounts-001",
            "barcode": "B1",
            "links": {
                "document_metadata": (
                    "https://document-api.company-information.service.gov.uk"
                    "/document/doc-accounts-001"
                )
            },
        },
        {
            "date": "2023-06-01",
            "category": "officers",
            "type": "AP01",
            "description": "appointment",
            "transaction_id": "tx-no-doc",
            "barcode": "B2",
            "links": {},
        },
    ],
}

MOCK_METADATA = {
    "id": "doc-accounts-001",
    "created_at": "2024-03-16T10:00:00Z",
    "pages": 3,
    "resources": {
        "application/pdf": {
            "content_length": 64,
            "created_at": "2024-03-16T10:00:00Z",
        }
    },
}

PDF_BYTES = b"%PDF-1.4 demo accounts filing"


def _resp(json_data=None, status=200, headers=None, raw=b""):
    resp = MagicMock()
    resp.status_code = status
    resp.headers = headers or {}
    if json_data is not None:
        resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    if status >= 400:
        import requests

        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
            f"HTTP {status}", response=resp
        )

    def iter_content(chunk_size=8192):
        for i in range(0, len(raw), chunk_size):
            yield raw[i : i + chunk_size]

    resp.iter_content = iter_content
    resp.close = MagicMock()
    return resp


@contextmanager
def demo_skill() -> Iterator[Any]:
    bundle = SkillLoader.load_skill(SKILL_ID)
    skill = bundle["module"].UkCompaniesHouseHandlerSkill(
        config={"COMPANIES_HOUSE_API_KEY": "demo_key"}
    )

    def side_effect(method, url, **kwargs):
        if "/filing-history" in url:
            return _resp(MOCK_FILINGS)
        if url.endswith("/document/doc-accounts-001") and not url.endswith("/content"):
            return _resp(MOCK_METADATA)
        if url.endswith("/document/doc-accounts-001/content"):
            assert kwargs.get("auth") is not None
            assert kwargs.get("allow_redirects") is False
            return _resp(
                status=302,
                headers={"Location": "https://s3.example.com/presigned/doc.pdf"},
            )
        if url.startswith("https://s3.example.com/"):
            assert kwargs.get("auth") is None
            return _resp(status=200, raw=PDF_BYTES)
        if url.endswith("/company/00102498"):
            return _resp({"company_name": "BP P.L.C."})
        raise AssertionError(f"Unexpected URL: {url}")

    with patch(
        "skills.finance.uk_companies_house_handler.skill.requests.request",
        side_effect=side_effect,
    ):
        yield skill


def main() -> None:
    print("DEMO MODE: mocked Document API flow — no live API key required.\n")
    with demo_skill() as skill:
        print("=== Flow A: list_downloadable_documents ===")
        listed = skill.execute(
            {
                "action": "list_downloadable_documents",
                "company_number": "00102498",
                "category": "accounts",
                "latest_only": True,
            }
        )
        print(f"status={listed['status']} documents={len(listed['documents'])}")
        assert listed["status"] == "ready"
        doc = listed["documents"][0]
        print(f"picked transaction_id={doc['transaction_id']}")

        print("\n=== Flow B: get_document_metadata ===")
        meta = skill.execute(
            {
                "action": "get_document_metadata",
                "transaction_id": doc["transaction_id"],
                "metadata_url": doc["metadata_url"],
                "context": listed["context"],
            }
        )
        print(
            f"status={meta['status']} mime_types={meta['mime_types']} "
            f"content_length={meta['content_length']}"
        )

        print("\n=== Flow C: fetch_document (redirect drops auth) ===")
        fetched = skill.execute(
            {
                "action": "fetch_document",
                "transaction_id": doc["transaction_id"],
                "metadata_url": doc["metadata_url"],
                "context": listed["context"],
            }
        )
        print(
            f"status={fetched['status']} size_bytes={fetched['size_bytes']} "
            f"filename={fetched['filename']}"
        )
        assert base64.b64decode(fetched["content_base64"]) == PDF_BYTES

        print("\n=== Flow D: document_too_large from declared content_length ===")

        def oversize_side_effect(method, url, **kwargs):
            if url.endswith("/document/doc-accounts-001") and not url.endswith(
                "/content"
            ):
                big = dict(MOCK_METADATA)
                big["resources"] = {
                    "application/pdf": {
                        "content_length": 12_582_912,
                        "created_at": "2024-03-16T10:00:00Z",
                    }
                }
                return _resp(big)
            raise AssertionError(url)

        with patch(
            "skills.finance.uk_companies_house_handler.skill.requests.request",
            side_effect=oversize_side_effect,
        ):
            too_big = skill.execute(
                {
                    "action": "fetch_document",
                    "metadata_url": doc["metadata_url"],
                    "max_bytes": 5_242_880,
                }
            )
        print(
            f"status={too_big['status']} error_code={too_big['error_code']} "
            f"size_bytes={too_big['size_bytes']}"
        )
        assert too_big["error_code"] == "document_too_large"

    print("\n=== flow complete ===")


if __name__ == "__main__":
    main()
