# Copyright (c) 2026 ARPA Hellenic Logical Systems
# SPDX-License-Identifier: MIT

"""Domain-neutral legal_profile validation, PII masking, and jurisdiction-aware field resolution.

Stored optionally on contacts in ``addressbook.yaml`` (alongside ``is_self: true``)
so compliance skills like ``office/pdf_form_filler`` can pre-fill tax, KYB, and
regulatory forms for the operator or any client/entity without duplicating identity.
"""

from __future__ import annotations

from datetime import datetime
import re
from typing import Any, Dict, List, Mapping, Optional, Tuple

VALID_PROFILE_TYPES = frozenset({"individual", "entity"})
VALID_ENTITY_CLASSIFICATIONS = frozenset(
    {
        "individual",
        "sole_proprietor",
        "c_corp",
        "s_corp",
        "corporation",
        "partnership",
        "trust_estate",
        "llc",
        "government",
        "other",
    }
)

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DIGITS_RE = re.compile(r"\D+")

# Compact ISO-3166-1 alpha-2 <-> English full name map for major tax/compliance jurisdictions.
ISO2_TO_COUNTRY_NAME: Dict[str, str] = {
    "AE": "United Arab Emirates",
    "AT": "Austria",
    "AU": "Australia",
    "BE": "Belgium",
    "BG": "Bulgaria",
    "BM": "Bermuda",
    "BR": "Brazil",
    "CA": "Canada",
    "CH": "Switzerland",
    "CN": "China",
    "CY": "Cyprus",
    "CZ": "Czechia",
    "DE": "Germany",
    "DK": "Denmark",
    "EE": "Estonia",
    "ES": "Spain",
    "FI": "Finland",
    "FR": "France",
    "GB": "United Kingdom",
    "GG": "Guernsey",
    "GR": "Greece",
    "HK": "Hong Kong",
    "HR": "Croatia",
    "HU": "Hungary",
    "IE": "Ireland",
    "IL": "Israel",
    "IM": "Isle of Man",
    "IN": "India",
    "IS": "Iceland",
    "IT": "Italy",
    "JE": "Jersey",
    "JP": "Japan",
    "KR": "South Korea",
    "KY": "Cayman Islands",
    "LI": "Liechtenstein",
    "LT": "Lithuania",
    "LU": "Luxembourg",
    "LV": "Latvia",
    "MT": "Malta",
    "MX": "Mexico",
    "NL": "Netherlands",
    "NO": "Norway",
    "NZ": "New Zealand",
    "PL": "Poland",
    "PT": "Portugal",
    "RO": "Romania",
    "SE": "Sweden",
    "SG": "Singapore",
    "SI": "Slovenia",
    "SK": "Slovakia",
    "TR": "Turkey",
    "TW": "Taiwan",
    "UK": "United Kingdom",
    "US": "United States",
    "VG": "British Virgin Islands",
    "ZA": "South Africa",
}

_COUNTRY_NAME_TO_ISO2: Dict[str, str] = {
    name.casefold(): code for code, name in ISO2_TO_COUNTRY_NAME.items() if code != "UK"
}
_COUNTRY_NAME_TO_ISO2.update(
    {
        "usa": "US",
        "u.s.": "US",
        "u.s.a.": "US",
        "united states of america": "US",
        "uk": "GB",
        "great britain": "GB",
        "hellas": "GR",
    }
)


def normalize_country_code(value: Optional[str]) -> Optional[str]:
    """Return canonical ISO-3166-1 alpha-2 code if recognized, else uppercase input."""
    raw = (value or "").strip()
    if not raw:
        return None
    upper = raw.upper()
    if upper == "UK":
        return "GB"
    if len(upper) == 2 and upper in ISO2_TO_COUNTRY_NAME:
        return upper
    return _COUNTRY_NAME_TO_ISO2.get(raw.casefold(), upper if len(upper) == 2 else None)


def normalize_country_name(
    value: Optional[str], *, full_name: bool = True
) -> Optional[str]:
    """Expand ISO-2 country codes to full names when ``full_name=True``."""
    raw = (value or "").strip()
    if not raw:
        return None
    code = normalize_country_code(raw)
    if full_name:
        if code and code in ISO2_TO_COUNTRY_NAME:
            return ISO2_TO_COUNTRY_NAME[code]
        return raw
    return code or raw


def format_iso_date(iso_date: str, date_format: Optional[str] = None) -> str:
    """Format canonical ``YYYY-MM-DD`` date into form-specific format (e.g. ``MM-DD-YYYY``)."""
    raw = (iso_date or "").strip()
    if not raw:
        return ""
    if not _ISO_DATE_RE.match(raw):
        return raw
    dt = datetime.strptime(raw, "%Y-%m-%d")
    fmt = (date_format or "YYYY-MM-DD").strip().upper()
    mapping = {
        "YYYY-MM-DD": "%Y-%m-%d",
        "MM-DD-YYYY": "%m-%d-%Y",
        "MM/DD/YYYY": "%m/%d/%Y",
        "DD-MM-YYYY": "%d-%m-%Y",
        "DD/MM/YYYY": "%d/%m/%Y",
    }
    return dt.strftime(mapping.get(fmt, "%Y-%m-%d"))


def mask_pii_value(value: Any) -> str:
    """Mask sensitive tax IDs / birthdates while keeping the last 4 characters."""
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) <= 4:
        return "*" * len(text)
    if _ISO_DATE_RE.match(text):
        return f"****-**-{text[-2:]}"
    if "-" in text and len(text) >= 9:
        parts = text.split("-")
        masked_prefix = "-".join("*" * len(p) for p in parts[:-1])
        return f"{masked_prefix}-{parts[-1]}"
    return "*" * (len(text) - 4) + text[-4:]


def mask_legal_profile(lp: Mapping[str, Any]) -> Dict[str, Any]:
    """Return a deep copy of ``legal_profile`` with tax IDs and birthdates masked."""
    out: Dict[str, Any] = {}
    for key, val in lp.items():
        if key in {"tax_id", "us_ein", "us_ssn", "us_itin", "giin", "date_of_birth"}:
            out[key] = mask_pii_value(val) if val else val
        elif key == "tax_ids" and isinstance(val, Mapping):
            out[key] = {str(k): mask_pii_value(v) if v else v for k, v in val.items()}
        elif key == "tax_residency" and isinstance(val, list):
            masked_list: List[Dict[str, Any]] = []
            for item in val:
                if isinstance(item, Mapping):
                    entry = dict(item)
                    if entry.get("tin"):
                        entry["tin"] = mask_pii_value(entry["tin"])
                    masked_list.append(entry)
            out[key] = masked_list
        elif isinstance(val, Mapping):
            out[key] = dict(val)
        else:
            out[key] = val
    return out


def validate_legal_profile(contact_id: str, raw: Any) -> List[str]:
    """Validate a contact's optional ``legal_profile`` block."""
    errors: List[str] = []
    prefix = f"contacts.{contact_id}.legal_profile"
    if not isinstance(raw, Mapping):
        return [f"{prefix} must be a mapping"]

    ptype = raw.get("type")
    if ptype is not None:
        if (
            not isinstance(ptype, str)
            or ptype.strip().lower() not in VALID_PROFILE_TYPES
        ):
            errors.append(
                f"{prefix}.type must be 'individual' or 'entity' (got {ptype!r})"
            )

    dob = raw.get("date_of_birth")
    if dob is not None and str(dob).strip():
        dob_s = str(dob).strip()
        if not _ISO_DATE_RE.match(dob_s):
            errors.append(
                f"{prefix}.date_of_birth must be ISO YYYY-MM-DD (got {dob!r})"
            )
        else:
            try:
                datetime.strptime(dob_s, "%Y-%m-%d")
            except ValueError:
                errors.append(
                    f"{prefix}.date_of_birth is not a valid calendar date: {dob!r}"
                )

    tax_residency = raw.get("tax_residency")
    if tax_residency is not None:
        if not isinstance(tax_residency, list):
            errors.append(f"{prefix}.tax_residency must be a list of mappings")
        else:
            for idx, entry in enumerate(tax_residency):
                if not isinstance(entry, Mapping):
                    errors.append(f"{prefix}.tax_residency[{idx}] must be a mapping")
                    continue
                if not str(entry.get("country") or "").strip():
                    errors.append(f"{prefix}.tax_residency[{idx}].country is required")

    tax_ids = raw.get("tax_ids")
    if tax_ids is not None and not isinstance(tax_ids, Mapping):
        errors.append(f"{prefix}.tax_ids must be a mapping")

    comp_reg = raw.get("company_registration")
    if comp_reg is not None:
        if not isinstance(comp_reg, Mapping):
            errors.append(f"{prefix}.company_registration must be a mapping")
        else:
            ec = comp_reg.get("entity_classification")
            if (
                ec is not None
                and str(ec).strip().lower() not in VALID_ENTITY_CLASSIFICATIONS
            ):
                errors.append(
                    f"{prefix}.company_registration.entity_classification invalid: {ec!r}"
                )

    for addr_key in ("residence_address", "mailing_address"):
        addr = raw.get(addr_key)
        if addr is not None and not isinstance(addr, Mapping):
            errors.append(f"{prefix}.{addr_key} must be a mapping")

    signatory = raw.get("authorized_signatory")
    if signatory is not None and not isinstance(signatory, Mapping):
        errors.append(f"{prefix}.authorized_signatory must be a mapping")

    return errors


def validate_is_self_uniqueness(contacts: Mapping[str, Any]) -> List[str]:
    """Ensure at most one contact in ``addressbook.yaml`` has ``is_self: true``."""
    self_ids = [
        str(cid)
        for cid, entry in contacts.items()
        if isinstance(entry, Mapping) and entry.get("is_self") is True
    ]
    if len(self_ids) > 1:
        return [
            f"multiple contacts marked is_self: true ({', '.join(sorted(self_ids))}); "
            "only one primary operator contact is allowed"
        ]
    return []


def find_self_contact(data: Mapping[str, Any]) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Return ``(contact_id, contact_dict)`` for ``is_self: true``, or fallback ``'me'``."""
    contacts = data.get("contacts")
    if not isinstance(contacts, Mapping):
        return None
    for cid, entry in contacts.items():
        if isinstance(entry, Mapping) and entry.get("is_self") is True:
            return str(cid), dict(entry)
    me = contacts.get("me")
    if isinstance(me, Mapping):
        return "me", dict(me)
    return None


def _clean_digits(value: Optional[str]) -> str:
    return _DIGITS_RE.sub("", value or "")


def _extract_tax_id(
    lp: Mapping[str, Any],
    kind: str,
    *,
    form_jurisdiction: Optional[str] = None,
) -> Optional[str]:
    tax_ids_raw = lp.get("tax_ids")
    tax_ids: Dict[str, str] = (
        {str(k).upper(): str(v).strip() for k, v in tax_ids_raw.items() if v}
        if isinstance(tax_ids_raw, Mapping)
        else {}
    )
    residencies = lp.get("tax_residency")
    res_list: List[Mapping[str, Any]] = (
        [r for r in residencies if isinstance(r, Mapping)]
        if isinstance(residencies, list)
        else []
    )
    form_cc = normalize_country_code(form_jurisdiction) if form_jurisdiction else None

    k = kind.strip().lower()
    if k in {"us_ssn", "ssn"}:
        return tax_ids.get("US_SSN") or _nonempty(lp.get("us_ssn"))
    if k in {"us_itin", "itin"}:
        return tax_ids.get("US_ITIN") or _nonempty(lp.get("us_itin"))
    if k in {"us_ein", "ein"}:
        return tax_ids.get("US_EIN") or _nonempty(lp.get("us_ein"))
    if k in {"giin"}:
        return tax_ids.get("GIIN") or _nonempty(lp.get("giin"))
    if k in {"lei"}:
        return tax_ids.get("LEI") or _nonempty(lp.get("lei"))
    if k in {"eu_vat", "vat"}:
        return tax_ids.get("EU_VAT") or _nonempty(lp.get("eu_vat"))

    if k in {"us", "us_tin"}:
        for candidate in (
            tax_ids.get("US_SSN"),
            tax_ids.get("US_ITIN"),
            tax_ids.get("US_EIN"),
            _nonempty(lp.get("us_ssn")),
            _nonempty(lp.get("us_itin")),
            _nonempty(lp.get("us_ein")),
        ):
            if candidate:
                return candidate
        for entry in res_list:
            if normalize_country_code(str(entry.get("country") or "")) == "US":
                tin = _nonempty(entry.get("tin"))
                if tin:
                    return tin
        return None

    if k == "local" and form_cc:
        for entry in res_list:
            if normalize_country_code(str(entry.get("country") or "")) == form_cc:
                tin = _nonempty(entry.get("tin"))
                if tin:
                    return tin
        for tk, tv in tax_ids.items():
            if tk.startswith(f"{form_cc}_"):
                return tv
        return _nonempty(lp.get("tax_id"))

    if k in {"foreign", "foreign_tin", "primary"}:
        exclude = form_cc or "US"
        for entry in res_list:
            cc = normalize_country_code(str(entry.get("country") or ""))
            if cc and cc != exclude:
                tin = _nonempty(entry.get("tin"))
                if tin:
                    return tin
        for tk, tv in tax_ids.items():
            if not tk.startswith(f"{exclude}_") and tk not in {"GIIN", "LEI"}:
                return tv
        flat = _nonempty(lp.get("tax_id"))
        if flat:
            return flat
        return None

    # Direct typed lookup (e.g. "gr_afm" -> tax_ids["GR_AFM"])
    return tax_ids.get(k.upper())


def _nonempty(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _resolve_address_field(
    addr: Mapping[str, Any],
    subkey: str,
    *,
    full_country_name: bool = True,
) -> Optional[str]:
    street = _nonempty(addr.get("street"))
    line2 = _nonempty(addr.get("street_line_2"))
    city = _nonempty(addr.get("city"))
    state = _nonempty(addr.get("state_province") or addr.get("state"))
    postal = _nonempty(addr.get("postal_code") or addr.get("zip"))
    country = normalize_country_name(
        _nonempty(addr.get("country")), full_name=full_country_name
    )

    if subkey == "street":
        return street
    if subkey == "street_line_2":
        return line2
    if subkey == "street_combined":
        parts = [p for p in (street, line2) if p]
        return ", ".join(parts) if parts else None
    if subkey == "city":
        return city
    if subkey in {"state_province", "state"}:
        return state
    if subkey in {"postal_code", "zip"}:
        return postal
    if subkey == "country":
        return country
    if subkey in {"city_state_postal", "city_state_zip"}:
        cs = ", ".join(p for p in (city, state) if p)
        combined = " ".join(p for p in (cs, postal) if p).strip()
        return combined or None
    if subkey == "full_line":
        parts = [p for p in (street, line2, city, state, postal, country) if p]
        return ", ".join(parts) if parts else None
    return _nonempty(addr.get(subkey))


def resolve_profile_field(
    contact: Mapping[str, Any],
    profile_key: str,
    *,
    form_jurisdiction: Optional[str] = None,
    date_format: Optional[str] = None,
    full_country_name: bool = True,
) -> Optional[Any]:
    """Resolve a schema ``profile_key`` from a contact dict + its ``legal_profile``."""
    key = (profile_key or "").strip()
    if not key:
        return None
    lp_raw = contact.get("legal_profile")
    lp: Mapping[str, Any] = lp_raw if isinstance(lp_raw, Mapping) else {}

    # Top-level contact fallbacks (zero duplication)
    if key == "legal_name":
        return _nonempty(lp.get("legal_name")) or _nonempty(contact.get("display_name"))
    if key == "business_name":
        return _nonempty(lp.get("business_name")) or _nonempty(contact.get("org"))
    if key == "email":
        emails = contact.get("emails")
        if isinstance(emails, list) and emails:
            return _nonempty(emails[0])
        return None
    if key == "first_name":
        return _nonempty(lp.get("first_name"))
    if key == "last_name":
        return _nonempty(lp.get("last_name"))
    if key == "phone":
        return _nonempty(lp.get("phone"))
    if key == "date_of_birth":
        dob = _nonempty(lp.get("date_of_birth"))
        return format_iso_date(dob, date_format) if dob else None
    if key == "citizenship":
        return normalize_country_name(
            _nonempty(lp.get("citizenship")), full_name=full_country_name
        )
    if key == "tax_residence_country":
        direct = _nonempty(lp.get("tax_residence_country"))
        if direct:
            return normalize_country_name(direct, full_name=full_country_name)
        res = lp.get("tax_residency")
        if isinstance(res, list) and res and isinstance(res[0], Mapping):
            return normalize_country_name(
                _nonempty(res[0].get("country")), full_name=full_country_name
            )
        return None

    # Authorized signatory (for entity forms; falls back to legal_name for individuals)
    if key == "authorized_signatory.name":
        sig = lp.get("authorized_signatory")
        if isinstance(sig, Mapping) and _nonempty(sig.get("name")):
            return _nonempty(sig.get("name"))
        if str(lp.get("type") or "").strip().lower() == "individual":
            return _nonempty(lp.get("legal_name")) or _nonempty(
                contact.get("display_name")
            )
        return None
    if key == "authorized_signatory.title":
        sig = lp.get("authorized_signatory")
        return _nonempty(sig.get("title")) if isinstance(sig, Mapping) else None

    # Addresses
    for addr_prefix in ("residence_address.", "mailing_address."):
        if key.startswith(addr_prefix):
            addr_block = lp.get(addr_prefix[:-1])
            if not isinstance(addr_block, Mapping):
                return None
            return _resolve_address_field(
                addr_block,
                key[len(addr_prefix) :],
                full_country_name=full_country_name,
            )

    # Company registration & entity classification checkboxes
    if key.startswith("company_registration."):
        reg = lp.get("company_registration")
        if not isinstance(reg, Mapping):
            return None
        sub = key[len("company_registration.") :]
        if sub == "jurisdiction":
            return normalize_country_name(
                _nonempty(reg.get("jurisdiction")), full_name=full_country_name
            )
        return _nonempty(reg.get(sub))

    if key == "jurisdiction_of_incorporation":
        reg = lp.get("company_registration")
        val = _nonempty(lp.get("jurisdiction_of_incorporation")) or (
            _nonempty(reg.get("jurisdiction")) if isinstance(reg, Mapping) else None
        )
        return normalize_country_name(val, full_name=full_country_name) if val else None

    if key.startswith("entity_classification."):
        target_cls = key[len("entity_classification.") :].strip().lower()
        reg = lp.get("company_registration")
        actual = (
            str(reg.get("entity_classification") or "").strip().lower()
            if isinstance(reg, Mapping)
            else ""
        )
        if not actual and str(lp.get("type") or "").strip().lower() == "individual":
            actual = "individual"
        if not actual:
            return None
        if target_cls == "individual":
            return True if actual in {"individual", "sole_proprietor"} else None
        if target_cls == "corporation":
            return True if actual in {"corporation", "c_corp", "s_corp"} else None
        return True if actual == target_cls else None

    # Segmented TIN virtual keys (for IRS Form W-9)
    if key.startswith("tin.us_ssn.part"):
        digits = _clean_digits(_extract_tax_id(lp, "us_ssn", form_jurisdiction="US"))
        if len(digits) != 9:
            return None
        part = key[-1]
        if part == "1":
            return digits[0:3]
        if part == "2":
            return digits[3:5]
        if part == "3":
            return digits[5:9]
        return None

    if key.startswith("tin.us_ein.part"):
        digits = _clean_digits(_extract_tax_id(lp, "us_ein", form_jurisdiction="US"))
        if len(digits) != 9:
            return None
        part = key[-1]
        if part == "1":
            return digits[0:2]
        if part == "2":
            return digits[2:9]
        return None

    # Jurisdiction-aware TIN keys: tin.foreign, tin.local, tin.us, tin.giin, tin.lei, etc.
    if key.startswith("tin."):
        return _extract_tax_id(
            lp, key[len("tin.") :], form_jurisdiction=form_jurisdiction
        )

    # Backward-compatible flat TIN keys
    if key in {"tax_id", "foreign_tin", "us_tin", "us_ein", "giin", "lei", "eu_vat"}:
        mapped = "foreign" if key in {"tax_id", "foreign_tin"} else key
        return _extract_tax_id(lp, mapped, form_jurisdiction=form_jurisdiction)

    return _nonempty(lp.get(key))
