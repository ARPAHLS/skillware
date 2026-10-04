"""Data models and type definitions for office/web_form_mapper."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class FormField:
    """Represents a discovered input/select/textarea field inside a form."""

    name: str
    id: str
    tag: str  # input, select, textarea
    type: str  # text, email, number, hidden, checkbox, radio, select, etc.
    label: str
    value: str = ""
    placeholder: str = ""
    required: bool = False
    pattern: Optional[str] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    options: List[Dict[str, str]] = field(
        default_factory=list
    )  # for select: [{"value": ..., "text": ...}]
    is_hidden: bool = False
    selector: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FormMetadata:
    """Metadata describing a detected web form."""

    form_index: int
    form_id: str
    form_name: str
    action: str
    method: str
    enctype: str = "application/x-www-form-urlencoded"
    fields: List[FormField] = field(default_factory=list)
    hidden_fields: Dict[str, str] = field(default_factory=dict)
    has_captcha: bool = False
    captcha_type: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["fields"] = [f.to_dict() for f in self.fields]
        return d


@dataclass
class FillPlanItem:
    """Proposed assignment of a value to a form field."""

    selector: str
    field_name: str
    proposed_value: Any
    source: str  # addressbook:me, addressbook:<id>, payload, curated_profile, default
    confidence: float  # 0.0 - 1.0
    required: bool = False
    field_type: str = "text"
    label: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PreviewDiffItem:
    """Human-readable preview diff for verification before submission."""

    label: str
    selector: str
    current_value: str
    proposed_value: str
    source: str
    confidence: float
    required: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
