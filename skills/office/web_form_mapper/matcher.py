"""Semantic matching and profile resolution for office/web_form_mapper."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

import yaml

try:
    from .models import FillPlanItem, FormField, FormMetadata
except (ImportError, ValueError):
    try:
        from skills.office.web_form_mapper.models import (
            FillPlanItem,
            FormField,
            FormMetadata,
        )
    except (ImportError, ValueError):
        from models import FillPlanItem, FormField, FormMetadata

# Canonical semantic dictionary mapping profile concepts to common web form labels and names
TAXONOMY: Dict[str, List[str]] = {
    "first_name": [
        "first_name",
        "firstname",
        "first",
        "fname",
        "given_name",
        "givenname",
        "forename",
        "prenom",
        "vorname",
    ],
    "last_name": [
        "last_name",
        "lastname",
        "last",
        "lname",
        "surname",
        "family_name",
        "nom",
        "nachname",
    ],
    "full_name": [
        "full_name",
        "fullname",
        "name",
        "legal_name",
        "applicant_name",
        "contact_name",
        "display_name",
        "your_name",
    ],
    "email": [
        "email",
        "e_mail",
        "email_address",
        "electronic_mail",
        "user_email",
        "mail",
        "courriel",
    ],
    "phone": [
        "phone",
        "phone_number",
        "telephone",
        "mobile",
        "cell",
        "tel",
        "contact_phone",
        "phone_no",
    ],
    "tax_id": [
        "tax_id",
        "taxid",
        "tin",
        "ssn",
        "social_security",
        "social_security_number",
        "ein",
        "employer_id",
        "vat_id",
        "vat",
        "vat_number",
        "steuer_id",
        "nif",
        "cif",
        "foreign_tax_id",
    ],
    "street": [
        "street",
        "street_address",
        "address_line_1",
        "address_line1",
        "address1",
        "address",
        "residential_address",
        "permanent_address",
        "registered_address",
        "strasse",
    ],
    "street2": [
        "street2",
        "street_address_2",
        "address_line_2",
        "address_line2",
        "address2",
        "apt",
        "suite",
        "unit",
        "building",
    ],
    "city": [
        "city",
        "town",
        "municipality",
        "suburb",
        "ort",
        "ville",
        "locality",
    ],
    "state": [
        "state",
        "province",
        "region",
        "prefecture",
        "county",
        "bundesland",
        "state_province",
    ],
    "postal_code": [
        "postal_code",
        "postalcode",
        "zip",
        "zipcode",
        "zip_code",
        "postcode",
        "plz",
        "code_postal",
    ],
    "country": [
        "country",
        "country_code",
        "nation",
        "citizenship",
        "country_of_citizenship",
        "land",
        "pays",
    ],
    "dob": [
        "dob",
        "date_of_birth",
        "birth_date",
        "birthdate",
        "geburtsdatum",
        "date_birth",
    ],
    "org": [
        "org",
        "organization",
        "company",
        "business_name",
        "entity_name",
        "company_name",
        "employer",
        "firm",
        "corporation",
    ],
}


def _normalize_key(text: str) -> str:
    """Normalize input strings for token comparison."""
    clean = re.sub(r"[^a-zA-Z0-9]+", "_", (text or "").strip().lower())
    return clean.strip("_")


def extract_flattened_identity(contact: Mapping[str, Any]) -> Dict[str, Any]:
    """
    Flatten a contact and its legal_profile into standard semantic keys.
    Compatible with addressbook.yaml schema from RFC #402 / Issue #408.
    """
    flat: Dict[str, Any] = {}

    # Standard contact fields
    if contact.get("display_name"):
        flat["full_name"] = contact["display_name"]
    elif contact.get("name"):
        flat.setdefault("full_name", contact["name"])
    if contact.get("org"):
        flat["org"] = contact["org"]

    emails = contact.get("emails") or []
    if emails and isinstance(emails, list):
        flat["email"] = emails[0]
    elif contact.get("email"):
        flat["email"] = str(contact["email"])

    if contact.get("phone"):
        flat["phone"] = contact["phone"]

    # Legal profile extension
    legal = contact.get("legal_profile") or {}
    if isinstance(legal, dict):
        if legal.get("legal_name"):
            flat["full_name"] = legal["legal_name"]
            flat.setdefault("org", legal["legal_name"])
        if legal.get("first_name"):
            flat["first_name"] = legal["first_name"]
        if legal.get("last_name"):
            flat["last_name"] = legal["last_name"]
        if legal.get("middle_name"):
            flat["middle_name"] = legal["middle_name"]

        # Derive first/last if full_name is present but first/last are missing
        if "full_name" in flat and (
            "first_name" not in flat or "last_name" not in flat
        ):
            parts = flat["full_name"].strip().split()
            if len(parts) >= 2:
                flat.setdefault("first_name", parts[0])
                flat.setdefault("last_name", " ".join(parts[1:]))

        # Tax IDs
        for tax_key in ("tax_id", "tin", "ssn", "ein", "vat_id", "foreign_tax_id"):
            if legal.get(tax_key):
                flat["tax_id"] = str(legal[tax_key])
                flat[tax_key] = str(legal[tax_key])

        if legal.get("dob"):
            flat["dob"] = str(legal["dob"])
        if legal.get("citizenship"):
            flat["citizenship"] = str(legal["citizenship"])
            flat.setdefault("country", str(legal["citizenship"]))
        if legal.get("jurisdiction"):
            flat.setdefault("country", str(legal["jurisdiction"]))
        if legal.get("tax_residence"):
            flat["tax_residence"] = str(legal["tax_residence"])

        # Address components
        addr = legal.get("address") or {}
        if isinstance(addr, dict):
            if addr.get("street"):
                flat["street"] = addr["street"]
            if addr.get("street2"):
                flat["street2"] = addr["street2"]
            if addr.get("city"):
                flat["city"] = addr["city"]
            if addr.get("state"):
                flat["state"] = addr["state"]
            if addr.get("postal_code") or addr.get("zip"):
                flat["postal_code"] = str(addr.get("postal_code") or addr.get("zip"))
            if addr.get("country"):
                flat["country"] = addr["country"]

    return flat


def load_curated_profile(
    profiles_dir: Path, profile_id: str
) -> Optional[Dict[str, Any]]:
    """Load a curated profile from kb/form_profiles/ if available."""
    if not profile_id:
        return None
    candidates = [
        profiles_dir / f"{profile_id}.yaml",
        profiles_dir / f"{profile_id}.yml",
        profiles_dir / f"{profile_id}.json",
    ]
    for p in candidates:
        if p.is_file():
            try:
                return yaml.safe_load(p.read_text(encoding="utf-8"))
            except Exception:
                pass
    return None


def _extract_tokens(field: FormField) -> List[str]:
    """Extract individual words, bigrams, and normalized phrases from field metadata."""
    raw_texts = [field.name, field.id, field.label, field.placeholder]
    tokens: set[str] = set()
    for text in raw_texts:
        if not text:
            continue
        # Split camelCase into words (e.g. txtLegalName -> txt_Legal_Name)
        s = re.sub(r"([a-z])([A-Z])", r"\1_\2", text)
        parts = [p.lower() for p in re.split(r"[^a-zA-Z0-9]+", s) if p]
        for p in parts:
            tokens.add(p)
        for i in range(len(parts) - 1):
            tokens.add(f"{parts[i]}_{parts[i+1]}")
        if len(parts) >= 3:
            tokens.add("_".join(parts))
    return list(tokens)


def match_field_to_value(
    field: FormField,
    identity_data: Dict[str, Any],
    curated_rules: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[Any], str, float]:
    """
    Match a single FormField against identity data.
    Returns (proposed_value, source, confidence).
    """
    # 1. Curated profile explicit rule
    if curated_rules and "field_mappings" in curated_rules:
        mappings = curated_rules["field_mappings"]
        for rule_selector, prop_key in mappings.items():
            if rule_selector in (field.selector, field.name, field.id):
                if prop_key in identity_data:
                    return identity_data[prop_key], "curated_profile", 1.0

    tokens = _extract_tokens(field)

    # 2. Handle Select dropdowns (resolve semantic concept to actual option value)
    if field.tag == "select" and field.options:
        candidate_values: List[Tuple[str, Any]] = []
        for concept, synonyms in TAXONOMY.items():
            if concept in identity_data and identity_data[concept]:
                for t in tokens:
                    if t in synonyms:
                        candidate_values.append((concept, identity_data[concept]))
                        break
        for t in tokens:
            if t in identity_data and identity_data[t]:
                candidate_values.append((t, identity_data[t]))

        for opt in field.options:
            opt_val = opt["value"].strip()
            opt_txt = opt["text"].strip().casefold()
            if not opt_val:
                continue
            for concept, val in candidate_values:
                target_str = str(val).strip().casefold()
                if not target_str:
                    continue
                if (
                    opt_val.casefold() == target_str
                    or opt_txt == target_str
                    or target_str in opt_txt
                    or (len(opt_txt) >= 4 and opt_txt in target_str)
                ):
                    return opt_val, f"select_option_match:{concept}", 0.95

    # 3. Exact token match in identity_data
    for t in tokens:
        if t in identity_data and identity_data[t]:
            return identity_data[t], f"exact_match:{t}", 1.0

    # 4. Disambiguate name fields: first_name vs last_name vs full_name
    has_first = any(
        t in ("first", "fname", "first_name", "given_name", "forename") for t in tokens
    )
    has_last = any(
        t in ("last", "lname", "last_name", "surname", "family_name") for t in tokens
    )
    has_full = any(
        t in ("full_name", "legal_name", "fullname")
        or (t == "name" and not has_first and not has_last)
        for t in tokens
    )

    if has_first and "first_name" in identity_data:
        return identity_data["first_name"], "semantic:first_name", 0.95
    if has_last and "last_name" in identity_data:
        return identity_data["last_name"], "semantic:last_name", 0.95
    if has_full and "full_name" in identity_data:
        return identity_data["full_name"], "semantic:full_name", 0.95

    # 5. Semantic taxonomy lookup for text/other inputs
    for concept, synonyms in TAXONOMY.items():
        if concept in ("first_name", "last_name", "full_name"):
            continue  # Already disambiguated above
        if concept not in identity_data or not identity_data[concept]:
            continue

        val = identity_data[concept]
        # Exact token in synonyms
        for t in tokens:
            if t in synonyms:
                return val, f"semantic:{concept}", 0.95

    return None, "none", 0.0


def generate_fill_plan(
    form: FormMetadata,
    identity_data: Dict[str, Any],
    source_label: str = "payload",
    curated_profile: Optional[Dict[str, Any]] = None,
) -> Tuple[List[FillPlanItem], List[str]]:
    """
    Generate an actionable FillPlan for all visible/unprotected fields.
    Returns (fill_plan, unmapped_required_fields).
    """
    fill_plan: List[FillPlanItem] = []
    unmapped_required: List[str] = []

    for field in form.fields:
        if field.is_hidden:
            continue  # Hidden fields are handled separately as pass-through invariants

        val, match_source, confidence = match_field_to_value(
            field,
            identity_data,
            curated_rules=curated_profile,
        )

        if val is not None:
            fill_plan.append(
                FillPlanItem(
                    selector=field.selector,
                    field_name=field.name or field.id or field.selector,
                    proposed_value=val,
                    source=f"{source_label} ({match_source})",
                    confidence=confidence,
                    required=field.required,
                    field_type=field.type,
                    label=field.label,
                )
            )
        else:
            if field.required:
                unmapped_required.append(field.label or field.name or field.id)

    return fill_plan, unmapped_required
