"""Unit table and resolution for data_engineering/unit_normalizer.

Every unit is one ``{factor, offset}`` row against the SI base of its dimension, so a
single equation covers linear units and temperature alike:

    si = (value + offset_in) * factor_in
    target = si / factor_out - offset_out

Offsets are stored before multiplication: degF carries 459.67, not 255.372.

Dimensions are exponent vectors over (length, mass, time, temperature, angle). Angle
gets its own slot even though SI treats the radian as dimensionless, so the dimension
guard stays hard between angles and everything else.
"""

import math
import re
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Tuple

Dim = Tuple[int, int, int, int, int]


def _dim(length=0, mass=0, time=0, temperature=0, angle=0) -> Dim:
    return (length, mass, time, temperature, angle)


LENGTH = _dim(length=1)
MASS = _dim(mass=1)
TIME = _dim(time=1)
TEMPERATURE = _dim(temperature=1)
ANGLE = _dim(angle=1)
AREA = _dim(length=2)
VOLUME = _dim(length=3)
SPEED = _dim(length=1, time=-1)
ACCELERATION = _dim(length=1, time=-2)
FORCE = _dim(length=1, mass=1, time=-2)
PRESSURE = _dim(length=-1, mass=1, time=-2)
ENERGY = _dim(length=2, mass=1, time=-2)
POWER = _dim(length=2, mass=1, time=-3)
ANGULAR_VELOCITY = _dim(time=-1, angle=1)

NAMED_DIMENSIONS: Dict[Dim, Tuple[str, str]] = {
    LENGTH: ("length", "m"),
    MASS: ("mass", "kg"),
    TIME: ("time", "s"),
    TEMPERATURE: ("temperature", "K"),
    ANGLE: ("angle", "rad"),
    AREA: ("area", "m2"),
    VOLUME: ("volume", "m3"),
    SPEED: ("speed", "m/s"),
    ACCELERATION: ("acceleration", "m/s2"),
    FORCE: ("force", "N"),
    PRESSURE: ("pressure", "Pa"),
    ENERGY: ("energy", "J"),
    POWER: ("power", "W"),
    ANGULAR_VELOCITY: ("angular_velocity", "rad/s"),
}

BASE_SYMBOLS = ("m", "kg", "s", "K", "rad")

PREFIXES: Dict[str, float] = {
    "n": 1e-9,
    "u": 1e-6,
    "m": 1e-3,
    "c": 1e-2,
    "k": 1e3,
    "M": 1e6,
    "G": 1e9,
}

# Only these base units accept an SI prefix; a blanket "strip one leading character"
# would read "min" as milli-inch and "nmi" as nano-mile.
PREFIXABLE = ("m", "g", "s", "L", "Pa", "J", "W", "N", "bar")
CENTI_BASES = ("m", "L")

EXPONENT_SUFFIX = re.compile(
    r"^(?P<base>.+?)(?:\^(?P<caret>[23])|(?P<plain>[23])|(?P<sup>[²³]))$"
)
SUPERSCRIPTS = {"²": 2, "³": 3}


@dataclass(frozen=True)
class Unit:
    key: str
    dimension: Dim
    factor: float
    offset: float = 0.0


@dataclass(frozen=True)
class Resolved:
    unit: Unit
    label: str
    assumption: Optional[Dict[str, Any]] = None


class UnitError(Exception):
    """A unit failure with a stable machine-readable code."""

    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


_UNITS: Dict[str, Unit] = {}
_SYMBOLS: Dict[str, str] = {}
# Long names resolve case-insensitively to a token that is resolved again, so
# "Kilometers" reaches "km" through the prefix path. Symbols are never case folded.
_NAMES: Dict[str, str] = {}


def _add(key, dimension, factor, offset=0.0, symbols=(), names=()):
    _UNITS[key] = Unit(key, dimension, factor, offset)
    for symbol in (key,) + tuple(symbols):
        _SYMBOLS[symbol] = key
    for name in names:
        _NAMES[name.lower()] = key


def _name(token, *names):
    for name in names:
        _NAMES[name.lower()] = token


_MILE = 1609.344
_NAUTICAL_MILE = 1852.0

# Length
_add("m", LENGTH, 1.0, names=("meter", "meters", "metre", "metres"))
_add("in", LENGTH, 0.0254, names=("inch", "inches"))
_add("ft", LENGTH, 0.3048, names=("foot", "feet"))
_add("yd", LENGTH, 0.9144, names=("yard", "yards"))
_add("mi", LENGTH, _MILE, names=("mile", "miles"))
_add("nmi", LENGTH, _NAUTICAL_MILE, names=("nautical_mile", "nautical_miles"))
_name("km", "kilometer", "kilometers", "kilometre", "kilometres")
_name("cm", "centimeter", "centimeters", "centimetre", "centimetres")
_name("mm", "millimeter", "millimeters", "millimetre", "millimetres")

# Mass
_add("kg", MASS, 1.0)
_add("g", MASS, 1e-3, names=("gram", "grams"))
_add("lb", MASS, 0.45359237, symbols=("lbs",), names=("pound", "pounds"))
_add("st", MASS, 6.35029318, names=("stone",))
_add("t", MASS, 1000.0, names=("tonne", "tonnes"))
_name("kg", "kilogram", "kilograms")
_name("mg", "milligram", "milligrams")

# Time
_add("s", TIME, 1.0, symbols=("sec",), names=("second", "seconds"))
_add("min", TIME, 60.0, names=("minute", "minutes"))
_add("h", TIME, 3600.0, symbols=("hr",), names=("hour", "hours"))
_add("d", TIME, 86400.0, names=("day", "days"))
_name("ms", "millisecond", "milliseconds")

# Temperature
_add("K", TEMPERATURE, 1.0, names=("kelvin",))
_add("degC", TEMPERATURE, 1.0, 273.15, symbols=("C", "°C", "℃"), names=("celsius",))
_add(
    "degF",
    TEMPERATURE,
    5.0 / 9.0,
    459.67,
    symbols=("F", "°F", "℉"),
    names=("fahrenheit",),
)
_add("degR", TEMPERATURE, 5.0 / 9.0, symbols=("R", "°R"), names=("rankine",))

# Area
_add("acre", AREA, 4046.8564224, names=("acres",))
_add("ha", AREA, 1e4, names=("hectare", "hectares"))

# Volume
_add("L", VOLUME, 1e-3, symbols=("l",), names=("liter", "liters", "litre", "litres"))
_add(
    "mL",
    VOLUME,
    1e-6,
    symbols=("ml",),
    names=("milliliter", "milliliters", "millilitre", "millilitres"),
)
_add("fl_oz_us", VOLUME, 2.95735295625e-5)

# Speed
_add("knot", SPEED, _NAUTICAL_MILE / 3600.0, symbols=("kn", "kt"), names=("knots",))
_add("mph", SPEED, _MILE / 3600.0)
_add("kph", SPEED, 1000.0 / 3600.0, symbols=("kmh",))

# Force
_add("N", FORCE, 1.0, names=("newton", "newtons"))
_add("lbf", FORCE, 4.4482216152605)
_add("kgf", FORCE, 9.80665)

# Pressure
_add("Pa", PRESSURE, 1.0, names=("pascal", "pascals"))
_add("bar", PRESSURE, 1e5)
_add("psi", PRESSURE, 6894.757293168361)
_add("atm", PRESSURE, 101325.0)
_add("mmHg", PRESSURE, 133.322387415)

# Energy
_add("J", ENERGY, 1.0, names=("joule", "joules"))
_add("cal", ENERGY, 4.184, names=("calorie", "calories"))
_add("kcal", ENERGY, 4184.0)
_add("Wh", ENERGY, 3600.0)
_add("kWh", ENERGY, 3.6e6)
_add("Btu", ENERGY, 1055.05585262, symbols=("BTU",))

# Power
_add("W", POWER, 1.0, names=("watt", "watts"))
_add("hp", POWER, 745.69987158227022, names=("horsepower",))

# Angle
_add("rad", ANGLE, 1.0, names=("radian", "radians"))
_add("deg", ANGLE, math.pi / 180.0, symbols=("°",), names=("degree", "degrees"))
_add("grad", ANGLE, math.pi / 200.0, symbols=("gon",), names=("gradian", "gradians"))
_add("rev", ANGLE, 2.0 * math.pi, names=("revolution", "revolutions", "turn", "turns"))
_add("arcmin", ANGLE, math.pi / 10800.0)
_add("arcsec", ANGLE, math.pi / 648000.0)

# Angular velocity
_add("rpm", ANGULAR_VELOCITY, 2.0 * math.pi / 60.0)
_add("dps", ANGULAR_VELOCITY, math.pi / 180.0)

# Readings of ambiguous units. Each is addressable directly and via assume.
_add("metric_ton", MASS, 1000.0)
_add("us_short_ton", MASS, 907.18474)
_add("imperial_long_ton", MASS, 1016.0469088)
_add("us_gallon", VOLUME, 3.785411784e-3)
_add("imperial_gallon", VOLUME, 4.54609e-3)
_add("us_pint", VOLUME, 4.73176473e-4)
_add("imperial_pint", VOLUME, 5.6826125e-4)
_add("us_quart", VOLUME, 9.46352946e-4)
_add("imperial_quart", VOLUME, 1.1365225e-3)
_add("oz_mass", MASS, 0.028349523125)
_add("oz_fluid_us", VOLUME, 2.95735295625e-5)
_add("oz_fluid_imperial", VOLUME, 2.84130625e-5)

# Ambiguous tokens: the default reading comes first. A token resolving here never
# comes back as a bare result; it carries an assumption record unless assume locks it.
AMBIGUOUS: Dict[str, Tuple[str, ...]] = {
    "ton": ("metric_ton", "us_short_ton", "imperial_long_ton"),
    "gal": ("us_gallon", "imperial_gallon"),
    "pt": ("us_pint", "imperial_pint"),
    "qt": ("us_quart", "imperial_quart"),
    "oz": ("oz_mass", "oz_fluid_us", "oz_fluid_imperial"),
    "'": ("ft", "arcmin"),
    '"': ("in", "arcsec"),
}

AMBIGUOUS_ALIASES: Dict[str, str] = {group: group for group in AMBIGUOUS}
AMBIGUOUS_ALIASES.update(
    {
        "tons": "ton",
        "gallon": "gal",
        "gallons": "gal",
        "pint": "pt",
        "pints": "pt",
        "quart": "qt",
        "quarts": "qt",
        "ounce": "oz",
        "ounces": "oz",
    }
)


def dimension_name(dim: Dim) -> str:
    named = NAMED_DIMENSIONS.get(dim)
    return named[0] if named else "derived"


def _compose_symbol(dim: Dim) -> str:
    def part(symbol: str, exponent: int) -> str:
        return symbol if exponent == 1 else f"{symbol}{exponent}"

    numerator = [part(s, e) for s, e in zip(BASE_SYMBOLS, dim) if e > 0]
    denominator = [part(s, -e) for s, e in zip(BASE_SYMBOLS, dim) if e < 0]
    symbol = "*".join(numerator) or "1"
    if denominator:
        symbol += "/" + "*".join(denominator)
    return symbol


def canonical_unit(dim: Dim) -> Tuple[Unit, str]:
    """Return the SI unit for ``dim`` and its symbol."""
    named = NAMED_DIMENSIONS.get(dim)
    symbol = named[1] if named else _compose_symbol(dim)
    return Unit(symbol, dim, 1.0), symbol


def convert(value: float, src: Unit, dst: Unit) -> float:
    if src.dimension != dst.dimension:
        raise UnitError(
            "dimension_mismatch",
            f"{src.key} ({dimension_name(src.dimension)}) cannot convert to "
            f"{dst.key} ({dimension_name(dst.dimension)})",
        )
    si_value = (value + src.offset) * src.factor
    return si_value / dst.factor - dst.offset


def _lookup(token: str) -> Optional[Unit]:
    key = _SYMBOLS.get(token)
    if key is not None:
        return _UNITS[key]

    for prefix, multiplier in PREFIXES.items():
        base = token[len(prefix) :]
        if not token.startswith(prefix) or base not in PREFIXABLE:
            continue
        if prefix == "c" and base not in CENTI_BASES:
            continue
        unit = _UNITS[_SYMBOLS[base]]
        return Unit(token, unit.dimension, multiplier * unit.factor)

    named = _NAMES.get(token.lower())
    if named is not None:
        return _lookup(named)
    return None


def _resolve_simple(token: str) -> Optional[Unit]:
    unit = _lookup(token)
    if unit is not None:
        return unit

    match = EXPONENT_SUFFIX.match(token)
    if not match:
        return None
    base = _lookup(match.group("base"))
    if base is None or base.offset:
        return None
    if match.group("sup"):
        power = SUPERSCRIPTS[match.group("sup")]
    else:
        power = int(match.group("caret") or match.group("plain"))
    return Unit(
        token,
        tuple(e * power for e in base.dimension),
        base.factor**power,
    )


def resolve_unit(
    token: str,
    assume: Optional[Mapping[str, str]] = None,
    target_dim: Optional[Dim] = None,
) -> Resolved:
    """Resolve a unit token to a ``Unit``.

    Order: exact case-sensitive alias, SI prefix against the allowlist, case-insensitive
    long name, ``^2``/``^3`` suffix, then a single ``a/b`` quotient.
    """
    if not isinstance(token, str) or not token.strip():
        raise UnitError("unknown_unit", "Unit must be a non-empty string.")
    label = token.strip()
    group = _ambiguity_group(label)
    if group is not None:
        return _resolve_ambiguous(label, group, assume or {}, target_dim)
    normalized = label.replace("µ", "u").replace("μ", "u")

    unit = _resolve_simple(normalized)
    if unit is None and normalized.count("/") == 1:
        numerator_token, denominator_token = normalized.split("/")
        numerator = _resolve_simple(numerator_token)
        denominator = _resolve_simple(denominator_token)
        if numerator is not None and denominator is not None:
            if numerator.offset or denominator.offset:
                raise UnitError(
                    "unknown_unit",
                    f"Unrecognised unit '{label}': offset units such as temperature "
                    "scales cannot be composed into a rate; use K.",
                )
            unit = Unit(
                normalized,
                tuple(
                    a - b for a, b in zip(numerator.dimension, denominator.dimension)
                ),
                numerator.factor / denominator.factor,
            )

    if unit is None:
        raise UnitError("unknown_unit", f"Unrecognised unit '{label}'.")
    return Resolved(unit, label)


def _ambiguity_group(token: str) -> Optional[str]:
    if token in AMBIGUOUS_ALIASES:
        return AMBIGUOUS_ALIASES[token]
    if token.isalpha() and token.lower() in AMBIGUOUS_ALIASES:
        return AMBIGUOUS_ALIASES[token.lower()]
    return None


def _risk_variance(candidates: Tuple[str, ...], dimension: Dim) -> Optional[str]:
    factors = [_UNITS[k].factor for k in candidates if _UNITS[k].dimension == dimension]
    if len(factors) < 2:
        return None
    low, high = min(factors), max(factors)
    return f"{(high - low) / low * 100:.1f}%"


def _resolve_ambiguous(
    label: str,
    group: str,
    assume: Mapping[str, str],
    target_dim: Optional[Dim],
) -> Resolved:
    candidates = AMBIGUOUS[group]
    locked = assume.get(group)
    if locked is not None:
        return Resolved(_UNITS[locked], label)

    eligible = candidates
    if target_dim is not None:
        matching = tuple(k for k in candidates if _UNITS[k].dimension == target_dim)
        eligible = matching or candidates
    chosen = eligible[0]
    unit = _UNITS[chosen]
    return Resolved(
        unit,
        label,
        {
            "assumption": f"{label} interpreted as {chosen}",
            "alternatives": [k for k in candidates if k != chosen],
            "risk_variance": _risk_variance(candidates, unit.dimension),
        },
    )


def validate_assume(assume: Any) -> Dict[str, str]:
    """Validate an operator ``assume`` map; keys are ambiguity groups or their aliases."""
    if assume is None:
        return {}
    if not isinstance(assume, dict):
        raise UnitError("invalid_assumption", "assume must be an object.")
    validated: Dict[str, str] = {}
    for token, reading in assume.items():
        group = _ambiguity_group(token) if isinstance(token, str) else None
        if group is None:
            supported = ", ".join(sorted(AMBIGUOUS))
            raise UnitError(
                "invalid_assumption",
                f"'{token}' is not an ambiguous unit. Ambiguous units: {supported}.",
            )
        if reading not in AMBIGUOUS[group]:
            options = ", ".join(AMBIGUOUS[group])
            raise UnitError(
                "invalid_assumption",
                f"'{reading}' is not a reading of '{token}'. Options: {options}.",
            )
        validated[group] = reading
    return validated
