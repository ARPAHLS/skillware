"""Bundle tests for data_engineering/unit_normalizer.

Fully offline: the skill is pure Python over bundled constants, so every test drives
the real conversion path with no mocks.
"""

import os

import pytest
import yaml

from . import units as units_module
from .units import UnitError, canonical_unit, convert, resolve_unit, validate_assume


@pytest.fixture
def manifest():
    manifest_path = os.path.join(os.path.dirname(__file__), "manifest.yaml")
    with open(manifest_path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _convert(value, src, dst):
    return convert(value, resolve_unit(src).unit, resolve_unit(dst).unit)


class TestManifest:
    def test_manifest_metadata(self, manifest):
        assert manifest["name"] == "data_engineering/unit_normalizer"
        assert manifest["version"] == "0.1.0"
        assert manifest["tier"] == "core"
        assert manifest["shape"] == "atomic"
        assert manifest["target"] == ["software", "hardware"]
        assert len(manifest["tags"]) == 7
        assert manifest["requirements"] == []
        assert manifest["issuer"]["name"] == "Martin Rizzo Lozano"
        assert manifest["issuer"]["email"] == "rizzolozanomartin@gmail.com"
        assert manifest["issuer"]["github"] == "rizzoMartin"


class TestUnits:
    def test_km_to_miles(self):
        assert _convert(100, "km", "mi") == pytest.approx(62.13711922373339, rel=1e-12)

    def test_temperature_offsets(self):
        assert _convert(20, "C", "F") == pytest.approx(68.0)
        assert _convert(98.6, "F", "C") == pytest.approx(37.0)
        assert _convert(0, "K", "C") == pytest.approx(-273.15)
        assert _convert(491.67, "R", "C") == pytest.approx(0.0, abs=1e-9)

    def test_prefix_case_sensitivity(self):
        assert resolve_unit("MPa").unit.factor == pytest.approx(1e6)
        assert resolve_unit("mPa").unit.factor == pytest.approx(1e-3)
        assert resolve_unit("Mm").unit.factor == pytest.approx(1e6)
        assert resolve_unit("mm").unit.factor == pytest.approx(1e-3)

    def test_symbols_are_not_case_folded(self):
        with pytest.raises(UnitError) as excinfo:
            resolve_unit("MM")
        assert excinfo.value.code == "unknown_unit"
        assert resolve_unit("KILOMETERS").unit.factor == pytest.approx(1000)

    def test_min_is_minute(self):
        assert resolve_unit("min").unit.factor == 60

    def test_micro_variants(self):
        for token in ("µm", "μm", "um"):
            assert resolve_unit(token).unit.factor == pytest.approx(1e-6)

    def test_quotient_units(self):
        assert _convert(120, "km/h", "m/s") == pytest.approx(33.333333333333336)
        assert _convert(3000, "rpm", "rad/s") == pytest.approx(314.1592653589793)
        assert _convert(1, "dps", "rad/s") == pytest.approx(0.017453292519943295)

    def test_dimension_mismatch(self):
        with pytest.raises(UnitError) as excinfo:
            _convert(70, "kg", "m")
        assert excinfo.value.code == "dimension_mismatch"
        with pytest.raises(UnitError) as excinfo:
            _convert(90, "deg", "m")
        assert excinfo.value.code == "dimension_mismatch"

    def test_offset_unit_in_quotient_rejected(self):
        with pytest.raises(UnitError) as excinfo:
            resolve_unit("C/s")
        assert excinfo.value.code == "unknown_unit"
        assert resolve_unit("K/s").unit.factor == 1

    def test_canonical_unit(self):
        assert canonical_unit(resolve_unit("psi").unit.dimension)[1] == "Pa"
        assert canonical_unit(resolve_unit("rpm").unit.dimension)[1] == "rad/s"

    def test_squared_and_cubed_suffixes(self):
        assert resolve_unit("ft2").unit.factor == pytest.approx(0.09290304)
        assert resolve_unit("m^3").unit.dimension == units_module.VOLUME
        assert units_module.dimension_name(resolve_unit("m/s2").unit.dimension) == (
            "acceleration"
        )


class TestAmbiguity:
    def test_ton_defaults_to_metric_and_declares(self):
        resolved = resolve_unit("ton")
        assert resolved.unit.factor == 1000
        assert resolved.assumption["assumption"] == "ton interpreted as metric_ton"
        assert resolved.assumption["alternatives"] == [
            "us_short_ton",
            "imperial_long_ton",
        ]
        assert resolved.assumption["risk_variance"] == "12.0%"

    def test_gallon_risk_variance(self):
        assert resolve_unit("gal").assumption["risk_variance"] == "20.1%"

    def test_assume_locks_without_flag(self):
        resolved = resolve_unit("ton", {"ton": "us_short_ton"})
        assert resolved.unit.factor == pytest.approx(907.18474)
        assert resolved.assumption is None

    def test_invalid_assumption(self):
        for assume in ({"ton": "banana"}, {"kg": "x"}, "ton", {"ton": 1}):
            with pytest.raises(UnitError) as excinfo:
                validate_assume(assume)
            assert excinfo.value.code == "invalid_assumption"
        assert validate_assume(None) == {}

    def test_oz_follows_target_dimension(self):
        resolved = resolve_unit("oz", target_dim=units_module.VOLUME)
        assert resolved.unit.factor == pytest.approx(2.95735295625e-5)
        assert "oz_fluid_us" in resolved.assumption["assumption"]
        assert "oz_mass" in resolved.assumption["alternatives"]

    def test_oz_defaults_to_mass(self):
        resolved = resolve_unit("oz")
        assert resolved.unit.dimension == units_module.MASS
        assert resolved.assumption["risk_variance"] is None

    def test_prime_marks_default_to_length(self):
        resolved = resolve_unit("'")
        assert resolved.unit.factor == pytest.approx(0.3048)
        assert resolved.assumption["alternatives"] == ["arcmin"]
        assert resolve_unit('"').assumption["alternatives"] == ["arcsec"]
