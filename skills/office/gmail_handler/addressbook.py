"""Deterministic address book loading and recipient resolution."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True)
class ResolvedRecipient:
    input_query: str
    email: str
    display_name: str
    source: str
    contact_id: Optional[str] = None


@dataclass(frozen=True)
class AmbiguousRecipient:
    input_query: str
    candidates: List[Dict[str, Any]]
    agent_hint: str


class AddressBookResolver:
    """Resolve names, aliases, and explicit emails against a YAML address book."""

    def __init__(self, addressbook: Dict[str, Any]):
        self._book = addressbook if isinstance(addressbook, dict) else {}
        self._contacts = self._book.get("contacts") or {}
        if not isinstance(self._contacts, dict):
            self._contacts = {}
        self._org_domains = self._book.get("org_domains") or {}
        if not isinstance(self._org_domains, dict):
            self._org_domains = {}

    @staticmethod
    def normalize(text: str) -> str:
        return " ".join((text or "").casefold().split())

    @staticmethod
    def is_email(value: str) -> bool:
        return bool(_EMAIL_RE.match((value or "").strip()))

    def resolve_queries(
        self,
        queries: Sequence[str],
        match_mode: str = "best_effort",
    ) -> Tuple[List[ResolvedRecipient], List[AmbiguousRecipient], List[str]]:
        resolved: List[ResolvedRecipient] = []
        ambiguous: List[AmbiguousRecipient] = []
        unresolved: List[str] = []
        seen_emails = set()

        for raw in queries:
            query = (raw or "").strip()
            if not query:
                continue

            if self.is_email(query):
                email = query.casefold()
                match = self._lookup_email(email)
                if match:
                    rec = ResolvedRecipient(
                        input_query=query,
                        email=match["email"],
                        display_name=match.get("display_name") or query,
                        source=f"addressbook:{match['contact_id']}",
                        contact_id=match["contact_id"],
                    )
                else:
                    rec = ResolvedRecipient(
                        input_query=query,
                        email=query,
                        display_name=query,
                        source="explicit",
                    )
                if rec.email.casefold() not in seen_emails:
                    resolved.append(rec)
                    seen_emails.add(rec.email.casefold())
                continue

            hits = self._match_contacts(query)
            org_hits = self._match_org_domains(query)
            combined = self._dedupe_contact_hits(hits + org_hits)

            if not combined:
                unresolved.append(query)
                continue

            if len(combined) == 1 or match_mode == "first":
                contact = combined[0]
                email = contact["primary_email"]
                rec = ResolvedRecipient(
                    input_query=query,
                    email=email,
                    display_name=contact.get("display_name") or query,
                    source=f"addressbook:{contact['contact_id']}",
                    contact_id=contact["contact_id"],
                )
                if rec.email.casefold() not in seen_emails:
                    resolved.append(rec)
                    seen_emails.add(rec.email.casefold())
                continue

            ambiguous.append(
                AmbiguousRecipient(
                    input_query=query,
                    candidates=[
                        {
                            "contact_id": c["contact_id"],
                            "email": c["primary_email"],
                            "display_name": c.get("display_name") or c["contact_id"],
                            "label": c["contact_id"],
                        }
                        for c in combined
                    ],
                    agent_hint=(
                        f"Multiple contacts match {query!r}. "
                        "Ask the user which recipient to use, or pass an explicit email."
                    ),
                )
            )

        return resolved, ambiguous, unresolved

    def resolve_to_emails(
        self,
        queries: Sequence[str],
        explicit_emails: Optional[Sequence[str]] = None,
    ) -> Tuple[List[str], List[AmbiguousRecipient], List[str], List[ResolvedRecipient]]:
        all_queries = list(queries or [])
        for email in explicit_emails or []:
            if email and email not in all_queries:
                all_queries.append(email)
        resolved, ambiguous, unresolved = self.resolve_queries(all_queries)
        emails = [r.email for r in resolved]
        return emails, ambiguous, unresolved, resolved

    def _lookup_email(self, email: str) -> Optional[Dict[str, Any]]:
        target = email.casefold()
        for contact_id, contact in self._contacts.items():
            if not isinstance(contact, dict):
                continue
            for entry in contact.get("emails") or []:
                if isinstance(entry, str) and entry.casefold() == target:
                    return {
                        "contact_id": contact_id,
                        "email": entry,
                        "display_name": contact.get("display_name") or contact_id,
                    }
        return None

    def _match_contacts(self, query: str) -> List[Dict[str, Any]]:
        norm_query = self.normalize(query)
        if not norm_query:
            return []

        exact: List[Dict[str, Any]] = []
        fuzzy: List[Dict[str, Any]] = []

        for contact_id, contact in self._contacts.items():
            if not isinstance(contact, dict):
                continue
            display = self.normalize(str(contact.get("display_name") or ""))
            aliases = [
                self.normalize(str(a))
                for a in (contact.get("aliases") or [])
                if isinstance(a, str)
            ]
            emails = [e for e in (contact.get("emails") or []) if isinstance(e, str)]
            if not emails:
                continue

            primary_email = emails[0]
            payload = {
                "contact_id": contact_id,
                "display_name": contact.get("display_name") or contact_id,
                "primary_email": primary_email,
            }

            if norm_query == display or norm_query in aliases:
                exact.append(payload)
                continue

            if norm_query in display or any(norm_query in alias for alias in aliases):
                fuzzy.append(payload)
                continue

            tokens = norm_query.split()
            display_tokens = display.split()
            if tokens and all(t in display_tokens for t in tokens):
                fuzzy.append(payload)

        return exact if exact else fuzzy

    def _match_org_domains(self, query: str) -> List[Dict[str, Any]]:
        norm_query = self.normalize(query)
        hits: List[Dict[str, Any]] = []

        for _org_id, org in self._org_domains.items():
            if not isinstance(org, dict):
                continue
            keywords = [
                self.normalize(str(k))
                for k in (org.get("keywords") or [])
                if isinstance(k, str)
            ]
            domains = [
                d.casefold() for d in (org.get("domains") or []) if isinstance(d, str)
            ]
            if norm_query not in keywords and not any(
                kw in norm_query or norm_query in kw for kw in keywords
            ):
                continue

            for contact_id, contact in self._contacts.items():
                if not isinstance(contact, dict):
                    continue
                contact_org = self.normalize(str(contact.get("org") or ""))
                emails = [
                    e for e in (contact.get("emails") or []) if isinstance(e, str)
                ]
                if not emails:
                    continue
                email_domains = [
                    e.split("@")[-1].casefold() for e in emails if "@" in e
                ]
                if domains and any(d in email_domains for d in domains):
                    hits.append(
                        {
                            "contact_id": contact_id,
                            "display_name": contact.get("display_name") or contact_id,
                            "primary_email": emails[0],
                        }
                    )
                elif contact_org and contact_org in norm_query:
                    hits.append(
                        {
                            "contact_id": contact_id,
                            "display_name": contact.get("display_name") or contact_id,
                            "primary_email": emails[0],
                        }
                    )

        return hits

    @staticmethod
    def _dedupe_contact_hits(hits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = set()
        out: List[Dict[str, Any]] = []
        for hit in hits:
            key = hit.get("contact_id")
            if key in seen:
                continue
            seen.add(key)
            out.append(hit)
        return out

    def apply_update(self, operation: str, entry: Dict[str, Any]) -> Dict[str, Any]:
        op = (operation or "").strip().lower()
        contact_id = (entry.get("contact_id") or entry.get("id") or "").strip()
        if not contact_id:
            raise ValueError("contact_id is required for address book updates")

        contacts = dict(self._contacts)
        if op in {"add", "update", "upsert"}:
            existing = contacts.get(contact_id, {})
            if not isinstance(existing, dict):
                existing = {}
            merged = {**existing, **entry}
            merged["contact_id"] = contact_id
            emails = merged.get("emails") or existing.get("emails") or []
            if not emails:
                raise ValueError("At least one email is required")
            merged["emails"] = emails
            contacts[contact_id] = merged
        elif op == "remove":
            if contact_id not in contacts:
                raise ValueError(f"Unknown contact_id {contact_id!r}")
            del contacts[contact_id]
        else:
            raise ValueError(f"Unknown address book operation {operation!r}")

        return {"contacts": contacts, "org_domains": self._org_domains}
