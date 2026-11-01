"""Compound quantity parsing for data_engineering/unit_normalizer.

Turns strings such as ``5 ft 11 in``, ``3 1/2 gal``, ``120 km/h`` or ``5'11"`` into
number/unit components and one SI value. Separate number+unit pairs are summed, which
is only meaningful when every component shares a dimension and carries no offset.
"""

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Tuple

try:
    from . import units
except ImportError:  # pragma: no cover - loader executes skill.py without a package
    import units

COMPONENT = re.compile(
    r"""\s*
    (?P<sign>[+-])?
    (?:
        (?P<whole>\d+)\s+(?P<mixed_num>\d+)/(?P<mixed_den>[\d.]+)
      | (?P<frac_num>\d+)/(?P<frac_den>[\d.]+)
      | (?P<decimal>(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)
    )
    \s*
    (?P<unit>['"]|[^\s\d'"+\-.][^\s'"]*)
    """,
    re.VERBOSE,
)


@dataclass
class ParsedQuantity:
    components: List[Tuple[float, units.Resolved]]
    si_value: float
    dimension: units.Dim
    assumptions: List[Dict[str, Any]]


def _fraction(numerator: str, denominator: str, text: str) -> float:
    if "." in denominator:
        raise units.UnitError(
            "unparseable",
            f"'{text}' has a decimal denominator ({numerator}/{denominator}), which is "
            "never a real fraction. It is likely an optical sensor-format designation, "
            "not a length; supply the physical dimension instead.",
        )
    if float(denominator) == 0:
        raise units.UnitError("unparseable", f"'{text}' divides by zero.")
    return float(numerator) / float(denominator)


def _number(match: "re.Match[str]", text: str) -> float:
    if match.group("whole") is not None:
        value = float(match.group("whole")) + _fraction(
            match.group("mixed_num"), match.group("mixed_den"), text
        )
    elif match.group("frac_num") is not None:
        value = _fraction(match.group("frac_num"), match.group("frac_den"), text)
    else:
        value = float(match.group("decimal"))
    return -value if match.group("sign") == "-" else value


def parse_quantity(
    text: str,
    assume: Optional[Mapping[str, str]] = None,
    target_dim: Optional[units.Dim] = None,
) -> ParsedQuantity:
    if not isinstance(text, str) or not text.strip():
        raise units.UnitError(
            "unparseable", "Quantity text must be a non-empty string."
        )
    if "," in text:
        raise units.UnitError(
            "unparseable",
            f"'{text}' contains a comma; thousands separators and decimal commas are "
            "not guessed. Use plain digits with a '.' decimal point.",
        )

    components: List[Tuple[float, units.Resolved]] = []
    position = 0
    stripped_end = len(text.rstrip())
    while position < stripped_end:
        match = COMPONENT.match(text, position)
        if match is None:
            raise units.UnitError(
                "unparseable",
                f"Could not read a number followed by a unit at '{text[position:].strip()}'.",
            )
        if components and match.group("sign"):
            raise units.UnitError(
                "unparseable",
                f"'{text}' has a sign inside a compound quantity.",
            )
        value = _number(match, text)
        resolved = units.resolve_unit(match.group("unit"), assume, target_dim)
        components.append((value, resolved))
        position = match.end()

    if len(components) > 1:
        dimensions = {r.unit.dimension for _, r in components}
        if len(dimensions) > 1:
            raise units.UnitError(
                "unparseable",
                f"'{text}' mixes dimensions; components can only be summed within one dimension.",
            )
        if any(r.unit.offset for _, r in components):
            raise units.UnitError(
                "unparseable",
                f"'{text}' sums offset units such as temperature scales, which is not a quantity.",
            )

    si_value = sum((v + r.unit.offset) * r.unit.factor for v, r in components)
    return ParsedQuantity(
        components=components,
        si_value=si_value,
        dimension=components[0][1].unit.dimension,
        assumptions=[r.assumption for _, r in components if r.assumption],
    )
