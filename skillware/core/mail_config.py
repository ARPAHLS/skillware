"""Merged mail operator settings for office/gmail_handler."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import yaml

ENV_ADDRESSBOOK_PATH = "GMAIL_ADDRESSBOOK_PATH"
ENV_SIGNATURE_PLAIN = "GMAIL_SIGNATURE_PLAIN"
ENV_SIGNATURE_PATH = "GMAIL_SIGNATURE_PATH"
ENV_SIGNATURE_HTML_PATH = "GMAIL_SIGNATURE_HTML_PATH"
ENV_SIGNATURE_PROFILE = "GMAIL_SIGNATURE_PROFILE"
ENV_SCAN_STATE_PATH = "GMAIL_SCAN_STATE_PATH"
ENV_SEND_LEDGER_PATH = "GMAIL_SEND_LEDGER_PATH"

SKILLWARE_SITE_URL = "https://skillware.site"
SKILLWARE_GITHUB_URL = "https://github.com/ARPAHLS/skillware"
ARPACORP_URL = "https://arpacorp.net"
SKILLWARE_LOGO_URL = (
    "https://raw.githubusercontent.com/ARPAHLS/skillware/main/assets/skillware_logo.png"
)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_SECRET_PATTERN = re.compile(
    r"(APP_PASSWORD|PRIVATE_KEY|SECRET|MNEMONIC|sk-ant-|github_pat_|Bearer\s)",
    re.IGNORECASE,
)
_MAX_SIGNATURE_LEN = 4000

DEFAULT_ADDRESSBOOK_REL = "addressbook.yaml"
DEFAULT_SIGNATURE_FILENAME = "mail_signature.txt"
DEFAULT_SIGNATURE_HTML_FILENAME = "mail_signature.html"
DEFAULT_LOGO_FILENAME = "skillware_logo.png"

ADDRESSBOOK_INIT_TEMPLATE = """\
# Address book for office/gmail_handler.
# Managed via skillware mail addressbook init / set-path.

contacts: {}

org_domains: {}
"""

DEFAULT_SIGNATURE_PLAIN = f"""\
—
Sent by a non-human agent via Skillware
Give your agents their own mailbox.

This message was composed and sent by an automated agent. Content may not reflect a human author.

{SKILLWARE_SITE_URL}
{SKILLWARE_GITHUB_URL}
{ARPACORP_URL}
"""

DEFAULT_SIGNATURE_HTML = f"""\
<div style="font-family: Arial, Helvetica, sans-serif; font-size: 13px; color: #222; line-height: 1.4;">
  <p style="margin: 0 0 10px 0; color: #888; font-size: 14px;">—</p>
  <p style="margin: 0 0 10px 0;">
    <a href="{SKILLWARE_SITE_URL}" style="text-decoration: none;">
      <img src="{SKILLWARE_LOGO_URL}" alt="Skillware" height="40" style="height: 40px; border: 0; display: block;">
    </a>
  </p>
  <p style="margin: 0 0 6px 0;"><strong>Sent by a non-human agent via Skillware</strong></p>
  <p style="margin: 0 0 6px 0;">Give your agents their own mailbox.</p>
  <p style="margin: 0 0 8px 0; font-size: 11px; color: #666;">
    This message was composed and sent by an automated agent. Content may not reflect a human author.
  </p>
  <p style="margin: 0; font-size: 12px;">
    <a href="{SKILLWARE_SITE_URL}">skillware.site</a>
    &nbsp;·&nbsp;
    <a href="{SKILLWARE_GITHUB_URL}">GitHub</a>
    &nbsp;·&nbsp;
    <a href="{ARPACORP_URL}">arpacorp.net</a>
  </p>
</div>
"""


@dataclass
class MailSettings:
    """Optional mail paths and signature from YAML ``mail:`` section."""

    addressbook_path: Optional[str] = None
    signature_path: Optional[str] = None
    signature_html_path: Optional[str] = None
    signature_plain: Optional[str] = None
    signature_profile: Optional[str] = None
    signatures: Optional[Dict[str, Any]] = None
    scan_state_path: Optional[str] = None
    send_ledger_path: Optional[str] = None

    def to_document_block(self) -> Dict[str, Any]:
        block: Dict[str, Any] = {}
        if self.addressbook_path is not None:
            block["addressbook_path"] = self.addressbook_path
        if self.signature_path is not None:
            block["signature_path"] = self.signature_path
        if self.signature_html_path is not None:
            block["signature_html_path"] = self.signature_html_path
        if self.signature_plain is not None:
            block["signature_plain"] = self.signature_plain
        if self.signature_profile is not None:
            block["signature_profile"] = self.signature_profile
        if self.signatures is not None:
            block["signatures"] = self.signatures
        if self.scan_state_path is not None:
            block["scan_state_path"] = self.scan_state_path
        if self.send_ledger_path is not None:
            block["send_ledger_path"] = self.send_ledger_path
        return block


def parse_mail_block(raw: Any) -> MailSettings:
    if not isinstance(raw, dict):
        return MailSettings()
    signatures = raw.get("signatures")
    if signatures is not None and not isinstance(signatures, dict):
        signatures = None
    return MailSettings(
        addressbook_path=_optional_str(raw.get("addressbook_path")),
        signature_path=_optional_str(raw.get("signature_path")),
        signature_html_path=_optional_str(raw.get("signature_html_path")),
        signature_plain=_optional_str(raw.get("signature_plain")),
        signature_profile=_optional_str(raw.get("signature_profile")),
        signatures=signatures if isinstance(signatures, dict) else None,
        scan_state_path=_optional_str(raw.get("scan_state_path")),
        send_ledger_path=_optional_str(raw.get("send_ledger_path")),
    )


def _optional_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def merge_mail_settings(layers: Sequence[MailSettings]) -> MailSettings:
    """Later layers override earlier fields (global then project)."""
    merged = MailSettings()
    for layer in layers:
        if layer.addressbook_path is not None:
            merged.addressbook_path = layer.addressbook_path
        if layer.signature_path is not None:
            merged.signature_path = layer.signature_path
        if layer.signature_html_path is not None:
            merged.signature_html_path = layer.signature_html_path
        if layer.signature_plain is not None:
            merged.signature_plain = layer.signature_plain
        if layer.signature_profile is not None:
            merged.signature_profile = layer.signature_profile
        if layer.signatures is not None:
            existing = dict(merged.signatures or {})
            for profile_id, profile in layer.signatures.items():
                if isinstance(profile, dict):
                    base = dict(existing.get(profile_id) or {})
                    base.update(profile)
                    existing[profile_id] = base
                else:
                    existing[profile_id] = profile
            merged.signatures = existing
        if layer.scan_state_path is not None:
            merged.scan_state_path = layer.scan_state_path
        if layer.send_ledger_path is not None:
            merged.send_ledger_path = layer.send_ledger_path
    return merged


def load_merged_mail_settings(*, refresh: bool = False) -> MailSettings:
    from skillware.core.config import load_merged_config

    return load_merged_config(refresh=refresh).mail


def default_global_addressbook_path() -> Path:
    from skillware.core.config import global_config_dir

    return global_config_dir() / DEFAULT_ADDRESSBOOK_REL


def default_global_signature_path() -> Path:
    from skillware.core.config import global_config_dir

    return global_config_dir() / DEFAULT_SIGNATURE_FILENAME


def default_global_signature_html_path() -> Path:
    from skillware.core.config import global_config_dir

    return global_config_dir() / DEFAULT_SIGNATURE_HTML_FILENAME


def default_global_logo_path() -> Path:
    from skillware.core.config import global_config_dir

    return global_config_dir() / DEFAULT_LOGO_FILENAME


def bundled_logo_path() -> Optional[Path]:
    """Logo shipped inside the skillware package (for local copy on init)."""
    try:
        from importlib.resources import files

        candidate = files("skillware").joinpath("branding/skillware_logo.png")
        path = Path(str(candidate))
        if path.is_file():
            return path
    except Exception:
        pass
    repo_asset = Path(__file__).resolve().parents[2] / "assets" / "skillware_logo.png"
    if repo_asset.is_file():
        return repo_asset
    return None


def default_global_scan_state_path() -> Path:
    from skillware.core.config import global_config_dir

    return global_config_dir() / "gmail_scan_state.json"


def default_global_send_ledger_path() -> Path:
    from skillware.core.config import global_config_dir

    return global_config_dir() / "gmail_send_ledger.json"


def _expand_path(raw: str) -> Path:
    return Path(raw).expanduser().resolve()


def resolve_addressbook_path(
    *,
    mail: Optional[MailSettings] = None,
    skill_data_dir: Optional[Path] = None,
    bundled_addressbook: Optional[Path] = None,
) -> Path:
    env_override = os.environ.get(ENV_ADDRESSBOOK_PATH, "").strip()
    if env_override:
        return _expand_path(env_override)

    settings = mail if mail is not None else load_merged_mail_settings()
    if settings.addressbook_path:
        return _expand_path(settings.addressbook_path)

    if bundled_addressbook and bundled_addressbook.is_file():
        return bundled_addressbook.resolve()

    data_dir = skill_data_dir or Path.cwd()
    bundled = data_dir / "addressbook.yaml"
    if bundled.is_file():
        return bundled.resolve()

    return default_global_addressbook_path()


def _read_signature_file(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8").strip()


def resolve_signature_profile(
    *,
    mail: Optional[MailSettings] = None,
    profile_id: Optional[str] = None,
    context: Optional[Mapping[str, Any]] = None,
) -> str:
    """Return active signature profile id (default ``default``)."""
    if profile_id and str(profile_id).strip():
        return str(profile_id).strip()

    ctx = context or {}
    ctx_profile = ctx.get("signature_profile")
    if isinstance(ctx_profile, str) and ctx_profile.strip():
        return ctx_profile.strip()

    env_profile = os.environ.get(ENV_SIGNATURE_PROFILE, "").strip()
    if env_profile:
        return env_profile

    settings = mail if mail is not None else load_merged_mail_settings()
    if settings.signature_profile:
        return settings.signature_profile

    return "default"


def _profile_block(
    mail: MailSettings,
    profile_id: str,
) -> Dict[str, Any]:
    profiles = mail.signatures if isinstance(mail.signatures, dict) else {}
    block = profiles.get(profile_id)
    if isinstance(block, dict):
        return block
    if profile_id == "default":
        legacy: Dict[str, Any] = {}
        if mail.signature_path:
            legacy["signature_path"] = mail.signature_path
        if mail.signature_html_path:
            legacy["signature_html_path"] = mail.signature_html_path
        if mail.signature_plain:
            legacy["signature_plain"] = mail.signature_plain
        return legacy
    return {}


def list_signature_profiles(
    *,
    mail: Optional[MailSettings] = None,
) -> Dict[str, Dict[str, Any]]:
    """Return known signature profiles with resolved path hints."""
    settings = mail if mail is not None else load_merged_mail_settings()
    profiles: Dict[str, Dict[str, Any]] = {}
    if isinstance(settings.signatures, dict):
        for profile_id, block in settings.signatures.items():
            if isinstance(block, dict):
                profiles[str(profile_id)] = dict(block)
    if "default" not in profiles and (
        settings.signature_path
        or settings.signature_html_path
        or settings.signature_plain
    ):
        profiles["default"] = _profile_block(settings, "default")
    active = resolve_signature_profile(mail=settings)
    for profile_id in profiles:
        profiles[profile_id]["active"] = profile_id == active
    return profiles


def resolve_signature_plain(
    *,
    mail: Optional[MailSettings] = None,
    skill_local_config: Optional[Mapping[str, Any]] = None,
    profile_id: Optional[str] = None,
    context: Optional[Mapping[str, Any]] = None,
) -> Tuple[str, str]:
    """
    Return (signature_text, source_label).

    source_label is one of: env_path, env_plain, config_path, config_plain,
    profile_path, profile_plain, skill_local, none.
    """
    active_profile = resolve_signature_profile(
        mail=mail,
        profile_id=profile_id,
        context=context,
    )

    env_path = os.environ.get(ENV_SIGNATURE_PATH, "").strip()
    if env_path and active_profile == "default":
        return _read_signature_file(_expand_path(env_path)), "env_path"

    env_plain = os.environ.get(ENV_SIGNATURE_PLAIN, "").strip()
    if env_plain and active_profile == "default":
        return env_plain, "env_plain"

    settings = mail if mail is not None else load_merged_mail_settings()
    profile = _profile_block(settings, active_profile)

    if profile.get("signature_path"):
        text = _read_signature_file(_expand_path(str(profile["signature_path"])))
        if text:
            return text, f"profile_path:{active_profile}"

    if profile.get("signature_plain"):
        return (
            str(profile["signature_plain"]).strip(),
            f"profile_plain:{active_profile}",
        )

    if active_profile == "default":
        if settings.signature_path:
            text = _read_signature_file(_expand_path(settings.signature_path))
            if text:
                return text, "config_path"

        if settings.signature_plain:
            return settings.signature_plain.strip(), "config_plain"

    local = skill_local_config or {}
    local_sig = (local.get("default_signature_plain") or "").strip()
    if local_sig and active_profile == "default":
        return local_sig, "skill_local"

    return "", "none"


def resolve_signature_html(
    *,
    mail: Optional[MailSettings] = None,
    skill_local_config: Optional[Mapping[str, Any]] = None,
    profile_id: Optional[str] = None,
    context: Optional[Mapping[str, Any]] = None,
) -> Tuple[str, str]:
    """Return (html_signature, source_label)."""
    active_profile = resolve_signature_profile(
        mail=mail,
        profile_id=profile_id,
        context=context,
    )

    env_path = os.environ.get(ENV_SIGNATURE_HTML_PATH, "").strip()
    if env_path and active_profile == "default":
        return _read_signature_file(_expand_path(env_path)), "env_html_path"

    settings = mail if mail is not None else load_merged_mail_settings()
    profile = _profile_block(settings, active_profile)

    if profile.get("signature_html_path"):
        text = _read_signature_file(_expand_path(str(profile["signature_html_path"])))
        if text:
            return text, f"profile_html_path:{active_profile}"

    if active_profile == "default":
        if settings.signature_html_path:
            text = _read_signature_file(_expand_path(settings.signature_html_path))
            if text:
                return text, "config_html_path"

    local = skill_local_config or {}
    local_html = (local.get("default_signature_html") or "").strip()
    if local_html and active_profile == "default":
        return local_html, "skill_local_html"

    return "", "none"


def is_bundled_skill_path(path: Path) -> bool:
    """True when path lives inside an installed skillware wheel (read-only)."""
    resolved = path.resolve()
    parts = {part.casefold() for part in resolved.parts}
    if "site-packages" in parts:
        return True
    try:
        import skillware

        pkg_root = Path(skillware.__file__).resolve().parent
        if str(resolved).startswith(str(pkg_root)):
            return True
    except Exception:
        pass
    return False


def ensure_writable_addressbook_path(path: Path) -> Path:
    """Prefer a user-writable path outside the installed skill bundle."""
    if is_bundled_skill_path(path):
        return default_global_addressbook_path()
    if path.is_file() and not os.access(path, os.W_OK):
        return default_global_addressbook_path()
    if not path.is_file() and not os.access(path.parent, os.W_OK):
        return default_global_addressbook_path()
    return path


def slugify_contact_id(display_name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", (display_name or "").casefold()).strip("_")
    return slug or "contact"


def write_addressbook_yaml(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


def add_addressbook_contact(
    path: Path,
    *,
    display_name: str,
    email: str,
    aliases: Optional[List[str]] = None,
    org: Optional[str] = None,
    contact_id: Optional[str] = None,
) -> str:
    """Add or upsert one contact; return contact_id."""
    display_name = (display_name or "").strip()
    email = (email or "").strip()
    if not display_name:
        raise ValueError("display_name is required")
    if not email or not _EMAIL_RE.match(email):
        raise ValueError("a valid email is required")

    data = load_addressbook_yaml(path)
    contacts = data.get("contacts")
    if not isinstance(contacts, dict):
        contacts = {}
        data["contacts"] = contacts
    if "org_domains" not in data or not isinstance(data.get("org_domains"), dict):
        data["org_domains"] = data.get("org_domains") or {}

    cid = (contact_id or slugify_contact_id(display_name)).strip()
    base = cid
    suffix = 2
    while cid in contacts and contacts[cid].get("emails") != [email]:
        existing = contacts.get(cid)
        if isinstance(existing, dict) and email in (existing.get("emails") or []):
            break
        cid = f"{base}_{suffix}"
        suffix += 1

    entry: Dict[str, Any] = {
        "display_name": display_name,
        "emails": [email],
    }
    if aliases:
        entry["aliases"] = [a.strip() for a in aliases if a and a.strip()]
    if org and org.strip():
        entry["org"] = org.strip()

    contacts[cid] = entry
    errors = validate_addressbook_data(data)
    if errors:
        raise ValueError("; ".join(errors))
    write_addressbook_yaml(path, data)
    return cid


def resolve_scan_state_path(
    *,
    mail: Optional[MailSettings] = None,
    skill_data_dir: Optional[Path] = None,
) -> Path:
    env_override = os.environ.get(ENV_SCAN_STATE_PATH, "").strip()
    if env_override:
        return _expand_path(env_override)
    settings = mail if mail is not None else load_merged_mail_settings()
    if settings.scan_state_path:
        return _expand_path(settings.scan_state_path)
    data_dir = skill_data_dir or Path.cwd()
    default = data_dir / ".gmail_scan_state.json"
    if default.parent.exists():
        return default.resolve()
    return default_global_scan_state_path()


def resolve_send_ledger_path(
    *,
    mail: Optional[MailSettings] = None,
    skill_data_dir: Optional[Path] = None,
) -> Path:
    env_override = os.environ.get(ENV_SEND_LEDGER_PATH, "").strip()
    if env_override:
        return _expand_path(env_override)
    settings = mail if mail is not None else load_merged_mail_settings()
    if settings.send_ledger_path:
        return _expand_path(settings.send_ledger_path)
    data_dir = skill_data_dir or Path.cwd()
    default = data_dir / "send_ledger.json"
    if default.parent.exists():
        return default.resolve()
    return default_global_send_ledger_path()


def load_addressbook_yaml(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {"contacts": {}, "org_domains": {}}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def count_addressbook_contacts(data: Mapping[str, Any]) -> int:
    contacts = data.get("contacts")
    if not isinstance(contacts, dict):
        return 0
    return sum(1 for value in contacts.values() if isinstance(value, dict))


def validate_addressbook_data(data: Mapping[str, Any]) -> List[str]:
    errors: List[str] = []
    contacts = data.get("contacts")
    org_domains = data.get("org_domains")

    if contacts is None:
        contacts = {}
    if org_domains is None:
        org_domains = {}

    if not isinstance(contacts, dict):
        errors.append("contacts must be a mapping")
        contacts = {}
    if not isinstance(org_domains, dict):
        errors.append("org_domains must be a mapping")

    seen_emails: set[str] = set()
    for contact_id, contact in contacts.items():
        if not isinstance(contact, dict):
            errors.append(f"contacts.{contact_id} must be a mapping")
            continue
        emails = contact.get("emails")
        if not isinstance(emails, list) or not emails:
            errors.append(f"contacts.{contact_id} requires at least one email")
            continue
        valid = False
        for entry in emails:
            if not isinstance(entry, str) or not _EMAIL_RE.match(entry.strip()):
                errors.append(f"contacts.{contact_id} has invalid email {entry!r}")
                continue
            key = entry.strip().casefold()
            if key in seen_emails:
                errors.append(f"duplicate email across contacts: {entry}")
            seen_emails.add(key)
            valid = True
        if not valid:
            errors.append(f"contacts.{contact_id} has no valid emails")

    return errors


def validate_signature_text(text: str) -> List[str]:
    errors: List[str] = []
    stripped = (text or "").strip()
    if not stripped:
        errors.append("signature is empty")
        return errors
    if len(stripped) > _MAX_SIGNATURE_LEN:
        errors.append(
            f"signature exceeds max length ({len(stripped)} > {_MAX_SIGNATURE_LEN})"
        )
    if _SECRET_PATTERN.search(stripped):
        errors.append("signature looks like it contains secret material")
    return errors


def init_addressbook_file(path: Path, *, overwrite: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and not overwrite:
        raise FileExistsError(str(path))
    path.write_text(ADDRESSBOOK_INIT_TEMPLATE, encoding="utf-8")


def init_signature_file(path: Path, *, overwrite: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and not overwrite:
        raise FileExistsError(str(path))
    path.write_text(DEFAULT_SIGNATURE_PLAIN.strip() + "\n", encoding="utf-8")


def init_signature_html_file(path: Path, *, overwrite: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and not overwrite:
        raise FileExistsError(str(path))
    path.write_text(DEFAULT_SIGNATURE_HTML.strip() + "\n", encoding="utf-8")


def copy_bundled_logo_to(dest_dir: Path) -> Optional[Path]:
    source = bundled_logo_path()
    if source is None:
        return None
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / DEFAULT_LOGO_FILENAME
    target.write_bytes(source.read_bytes())
    return target


def init_signature_bundle(
    config_dir: Path,
    *,
    overwrite: bool = False,
) -> Tuple[Path, Path, Optional[Path]]:
    """Create plain + HTML signatures and copy logo into ``config_dir``."""
    txt_path = config_dir / DEFAULT_SIGNATURE_FILENAME
    html_path = config_dir / DEFAULT_SIGNATURE_HTML_FILENAME
    init_signature_file(txt_path, overwrite=overwrite)
    init_signature_html_file(html_path, overwrite=overwrite)
    logo_path = copy_bundled_logo_to(config_dir)
    return txt_path, html_path, logo_path


def load_project_mail_settings(*, start: Optional[Path] = None) -> MailSettings:
    from skillware.core.config import _read_yaml, find_project_config_file

    path = find_project_config_file(start)
    if path is None:
        return MailSettings()
    data = _read_yaml(path)
    return parse_mail_block(data.get("mail"))


def save_project_mail_settings(
    mail: MailSettings,
    *,
    start: Optional[Path] = None,
) -> Path:
    """Merge ``mail`` into project ``.skillware.yaml``; preserve other keys."""
    from skillware.core.config import (
        _read_yaml,
        clear_config_cache,
        project_config_write_path,
    )

    target = project_config_write_path(start)
    target.parent.mkdir(parents=True, exist_ok=True)

    document: Dict[str, Any] = {}
    if target.is_file():
        existing = _read_yaml(target)
        document.update(existing)

    block = mail.to_document_block()
    if block:
        document["mail"] = block
    elif "mail" in document:
        del document["mail"]

    target.write_text(
        yaml.safe_dump(document, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    clear_config_cache()
    return target.resolve()


def save_global_mail_settings(
    mail: MailSettings,
) -> Path:
    """Merge ``mail`` into global ``config.yaml``; preserve other keys."""
    from skillware.core.config import (
        _read_yaml,
        clear_config_cache,
        global_config_path,
    )

    target = global_config_path()
    target.parent.mkdir(parents=True, exist_ok=True)

    document: Dict[str, Any] = {}
    if target.is_file():
        document.update(_read_yaml(target))

    existing = parse_mail_block(document.get("mail"))
    merged = merge_mail_settings([existing, mail])
    block = merged.to_document_block()
    if block:
        document["mail"] = block
    elif "mail" in document:
        del document["mail"]

    target.write_text(
        yaml.safe_dump(document, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    clear_config_cache()
    return target.resolve()


def upsert_signature_profile(
    profile_id: str,
    *,
    signature_path: Optional[str] = None,
    signature_html_path: Optional[str] = None,
    signature_plain: Optional[str] = None,
    start: Optional[Path] = None,
) -> Path:
    """Add or update one named signature profile in project config."""
    profile_id = (profile_id or "").strip()
    if not profile_id:
        raise ValueError("profile_id is required")

    project = load_project_mail_settings(start=start)
    profiles = dict(project.signatures or {})
    block = dict(profiles.get(profile_id) or {})
    if signature_path is not None:
        block["signature_path"] = signature_path
    if signature_html_path is not None:
        block["signature_html_path"] = signature_html_path
    if signature_plain is not None:
        block["signature_plain"] = signature_plain
    profiles[profile_id] = block
    project.signatures = profiles
    return save_project_mail_settings(project, start=start)


def set_active_signature_profile(
    profile_id: str,
    *,
    start: Optional[Path] = None,
) -> Path:
    profile_id = (profile_id or "").strip()
    if not profile_id:
        raise ValueError("profile_id is required")
    project = load_project_mail_settings(start=start)
    project.signature_profile = profile_id
    return save_project_mail_settings(project, start=start)


def persist_global_mail_paths(
    *,
    addressbook_path: Optional[str] = None,
    signature_path: Optional[str] = None,
    signature_html_path: Optional[str] = None,
) -> Path:
    """Convenience helper for CLI init commands."""
    mail = MailSettings()
    if addressbook_path is not None:
        mail.addressbook_path = addressbook_path
    if signature_path is not None:
        mail.signature_path = signature_path
    if signature_html_path is not None:
        mail.signature_html_path = signature_html_path
    return save_global_mail_settings(mail)


def clear_mail_signature_settings() -> List[Path]:
    """Remove signature keys from project and global config files."""
    from skillware.core.config import (
        _read_yaml,
        clear_config_cache,
        global_config_path,
        project_config_write_path,
    )

    updated: List[Path] = []
    for target in (project_config_write_path(), global_config_path()):
        if not target.is_file():
            continue
        document = _read_yaml(target)
        mail_block = document.get("mail")
        if not isinstance(mail_block, dict):
            continue
        changed = False
        for key in ("signature_path", "signature_html_path", "signature_plain"):
            if key in mail_block:
                del mail_block[key]
                changed = True
        for key in ("signature_profile", "signatures"):
            if key in mail_block:
                del mail_block[key]
                changed = True
        if not mail_block:
            document.pop("mail", None)
        elif changed:
            document["mail"] = mail_block
        if changed:
            target.write_text(
                yaml.safe_dump(document, sort_keys=False, default_flow_style=False),
                encoding="utf-8",
            )
            updated.append(target.resolve())
    if updated:
        clear_config_cache()
    return updated


def format_mail_config_lines(
    mail: MailSettings,
    *,
    skill_data_dir: Optional[Path] = None,
    bundled_addressbook: Optional[Path] = None,
    skill_local_config: Optional[Mapping[str, Any]] = None,
) -> List[str]:
    """Human-readable resolved mail settings for config show."""
    lines: List[str] = []
    ab_path = resolve_addressbook_path(
        mail=mail,
        skill_data_dir=skill_data_dir,
        bundled_addressbook=bundled_addressbook,
    )
    sig, sig_source = resolve_signature_plain(
        mail=mail,
        skill_local_config=skill_local_config,
    )
    sig_html, sig_html_source = resolve_signature_html(
        mail=mail,
        skill_local_config=skill_local_config,
    )
    active_profile = resolve_signature_profile(mail=mail)
    scan_path = resolve_scan_state_path(mail=mail, skill_data_dir=skill_data_dir)
    ledger_path = resolve_send_ledger_path(mail=mail, skill_data_dir=skill_data_dir)

    lines.append(f"  addressbook_path (resolved): {ab_path}")
    if os.environ.get(ENV_ADDRESSBOOK_PATH):
        lines.append(f"    source: env {ENV_ADDRESSBOOK_PATH}")
    elif mail.addressbook_path:
        lines.append("    source: config mail.addressbook_path")

    if sig:
        preview = sig.replace("\n", " ")[:72]
        if len(sig) > 72:
            preview += "..."
        lines.append(f"  signature (resolved, {sig_source}): {preview!r}")
    else:
        lines.append("  signature: (none)")

    if sig_html:
        lines.append(f"  signature_html (resolved, {sig_html_source}): present")
    else:
        lines.append("  signature_html: (none)")

    lines.append(f"  signature_profile (active): {active_profile}")
    profiles = list_signature_profiles(mail=mail)
    if profiles:
        lines.append(f"  signature_profiles: {', '.join(sorted(profiles))}")

    lines.append(f"  scan_state_path (resolved): {scan_path}")
    lines.append(f"  send_ledger_path (resolved): {ledger_path}")
    return lines
