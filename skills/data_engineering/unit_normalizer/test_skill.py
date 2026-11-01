"""Bundle tests for data_engineering/unit_normalizer.

Fully offline: the skill is pure Python over bundled constants, so every test drives
the real conversion path with no mocks.
"""

import os

import pytest
import yaml

from . import units as units_module
from .parser import parse_quantity
from .skill import UnitNormalizerSkill
from .units import UnitError, canonical_unit, convert, resolve_unit, validate_assume


@pytest.fixture
def skill():
    return UnitNormalizerSkill()


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


def _parse_error(text):
    with pytest.raises(UnitError) as excinfo:
        parse_quantity(text)
    return excinfo.value.code


class TestParser:
    def test_feet_inches(self):
        parsed = parse_quantity("5 ft 11 in")
        assert parsed.si_value == pytest.approx(1.8034)
        assert [r.label for _, r in parsed.components] == ["ft", "in"]
        assert [v for v, _ in parsed.components] == [5, 11]
        assert parsed.assumptions == []

    def test_prime_notation(self):
        parsed = parse_quantity("5'11\"")
        assert parsed.si_value == pytest.approx(1.8034)
        assert len(parsed.assumptions) == 2

    def test_fraction_and_mixed_number(self):
        assert parse_quantity("1/4 lb").si_value == pytest.approx(0.1133980925)
        parsed = parse_quantity("3 1/2 gal")
        assert parsed.si_value == pytest.approx(0.013248941244)
        assert len(parsed.assumptions) == 1

    def test_rate_and_prefix_strings(self):
        assert parse_quantity("120 km/h").si_value == pytest.approx(33.333333333333336)
        assert parse_quantity("3.5 MPa").si_value == pytest.approx(3.5e6)
        assert parse_quantity("45.2 psi").si_value == pytest.approx(311643.0296512)
        assert parse_quantity("15 knots").si_value == pytest.approx(7.716666666666667)
        assert parse_quantity("25mm").si_value == pytest.approx(0.025)
        assert parse_quantity("-40 F").si_value == pytest.approx(233.15)
        assert parse_quantity("1.5e3 m").si_value == pytest.approx(1500)

    def test_offset_compound_rejected(self):
        assert _parse_error("20 C 5 F") == "unparseable"

    def test_mixed_dimension_compound_rejected(self):
        assert _parse_error("5 ft 3 kg") == "unparseable"

    def test_decimal_denominator_refused(self):
        assert _parse_error('1/2.3"') == "unparseable"

    def test_comma_refused(self):
        assert _parse_error("1,500 kg") == "unparseable"

    def test_malformed_text(self):
        for text in ("", "   ", "kg", "5", "5 ft -11 in", "1/0 in"):
            assert _parse_error(text) == "unparseable"
        assert _parse_error("5 parsecs") == "unknown_unit"


ENVELOPE_KEYS = {
    "status",
    "action",
    "result",
    "results",
    "errors",
    "summary",
    "precision",
    "agent_hint",
    "error",
}


class TestSkillActions:
    def test_normalize_scalar(self, skill):
        res = skill.execute({"value": 100, "from_unit": "km", "to_unit": "miles"})
        assert res["status"] == "ready"
        assert res["action"] == "normalize"
        assert res["result"]["value"] == pytest.approx(62.13711922373339, rel=1e-12)
        assert res["result"]["display_value"] == "62.137119"
        assert res["result"]["dimension"] == "length"
        assert res["summary"]["converted"] == 1
        assert res["error"] is None

    def test_batch_issue_example(self, skill):
        res = skill.execute(
            {
                "action": "normalize_batch",
                "records": [
                    {"id": "a", "value": 100, "from_unit": "km", "to_unit": "miles"},
                    {"id": "b", "value": 70, "from_unit": "kg", "to_unit": "lbs"},
                ],
            }
        )
        assert res["status"] == "ready"
        assert [r["id"] for r in res["results"]] == ["a", "b"]
        assert res["results"][0]["value"] == pytest.approx(62.13711922373339)
        assert res["results"][1]["value"] == pytest.approx(154.32358352941431)
        assert res["results"][1]["display_value"] == "154.323584"
        assert res["errors"] == []
        assert res["result"] is None

    def test_batch_partial_failure(self, skill):
        res = skill.execute(
            {
                "action": "normalize_batch",
                "records": [
                    {"id": "ok", "value": 1, "from_unit": "m", "to_unit": "ft"},
                    {"id": "r7", "value": 70, "from_unit": "kg", "to_unit": "m"},
                    {"value": 1, "from_unit": "xyz", "to_unit": "m"},
                    "not a record",
                    {"id": "nounit", "value": 1},
                ],
            }
        )
        assert res["status"] == "warning"
        assert res["summary"] == {
            "total": 5,
            "converted": 1,
            "assumed": 0,
            "errors": 4,
            "skipped": 0,
        }
        errors = {e["id"]: e for e in res["errors"]}
        assert errors["r7"]["code"] == "dimension_mismatch"
        assert errors["r7"]["detail"] == "kg (mass) cannot convert to m (length)"
        assert errors[2]["code"] == "unknown_unit"
        assert errors[3]["code"] == "invalid_record"
        assert errors["nounit"]["code"] == "invalid_record"

    def test_bool_nan_inf_rejected(self, skill):
        records = [
            {"id": i, "value": v, "from_unit": "m", "to_unit": "ft"}
            for i, v in enumerate([True, float("nan"), float("inf"), "abc", None])
        ]
        records.append({"id": "str", "value": "12.5", "from_unit": "m"})
        res = skill.execute({"action": "normalize_batch", "records": records})
        assert [e["code"] for e in res["errors"]] == ["invalid_value"] * 5
        assert res["results"][0]["id"] == "str"
        assert res["results"][0]["value"] == pytest.approx(12.5)

    def test_ambiguous_row_is_warning_not_ready(self, skill):
        params = {"value": 20, "from_unit": "ton", "to_unit": "kg"}
        res = skill.execute(params)
        assert res["status"] == "warning"
        assert res["result"]["assumed"] is True
        assert res["result"]["alternatives"] == ["us_short_ton", "imperial_long_ton"]
        assert res["result"]["risk_variance"] == "12.0%"
        assert res["summary"]["assumed"] == 1

        locked = skill.execute(dict(params, assume={"ton": "metric_ton"}))
        assert locked["status"] == "ready"
        assert "assumed" not in locked["result"]
        assert locked["result"]["value"] == pytest.approx(20000.0)

    def test_invalid_assume_is_fatal(self, skill):
        res = skill.execute(
            {"value": 1, "from_unit": "ton", "to_unit": "kg", "assume": {"ton": "x"}}
        )
        assert res["status"] == "error"
        assert "invalid_assumption" in res["error"]

    def test_canonicalize(self, skill):
        res = skill.execute({"action": "canonicalize", "value": 45, "from_unit": "psi"})
        assert res["results"][0]["to_unit"] == "Pa"
        assert res["results"][0]["value"] == pytest.approx(310264.0781925762)
        res = skill.execute(
            {
                "action": "canonicalize",
                "records": [
                    {"value": 3000, "from_unit": "rpm", "to_unit": "deg/s"},
                    {"value": 20, "from_unit": "C"},
                ],
            }
        )
        assert [r["to_unit"] for r in res["results"]] == ["rad/s", "K"]
        assert res["results"][1]["value"] == pytest.approx(293.15)
        batch = skill.execute(
            {"action": "normalize_batch", "records": [{"value": 1, "from_unit": "mi"}]}
        )
        assert batch["results"][0]["to_unit"] == "m"

    def test_precision(self, skill):
        params = {"value": 100, "from_unit": "km", "to_unit": "miles"}
        assert skill.execute(dict(params, precision=2))["result"]["display_value"] == (
            "62.14"
        )
        assert skill.execute(dict(params, precision=0))["result"]["display_value"] == (
            "62"
        )
        for bad in (13, -1, True, "2", 2.0):
            assert skill.execute(dict(params, precision=bad))["status"] == "error"

    def test_parse_quantity_action(self, skill):
        res = skill.execute(
            {"action": "parse_quantity", "text": "5 ft 11 in", "target_unit": "m"}
        )
        assert res["status"] == "ready"
        record = res["result"]
        assert record["value"] == pytest.approx(1.8034)
        assert record["display_value"] == "1.803400"
        assert record["original_text"] == "5 ft 11 in"
        assert record["from_unit"] == "ft+in"
        assert record["to_unit"] == "m"
        assert record["components"] == [
            {"value": 5.0, "unit": "ft"},
            {"value": 11.0, "unit": "in"},
        ]

    def test_parse_quantity_canonical_and_errors(self, skill):
        res = skill.execute({"action": "parse_quantity", "text": "3 1/2 gal"})
        assert res["status"] == "warning"
        assert res["result"]["to_unit"] == "m3"
        assert res["result"]["assumed"] is True
        bad = skill.execute({"action": "parse_quantity", "text": "20 C 5 F"})
        assert bad["status"] == "warning"
        assert bad["result"] is None
        assert bad["errors"][0]["code"] == "unparseable"
        missing = skill.execute({"action": "parse_quantity"})
        assert missing["status"] == "insufficient_data"

    def test_empty_and_bad_payloads(self, skill):
        empty = skill.execute({"action": "normalize_batch", "records": []})
        bad_type = skill.execute({"action": "normalize_batch", "records": "x"})
        bad_action = skill.execute({"action": "nope"})
        no_params = skill.execute(None)
        assert empty["status"] == "insufficient_data"
        assert bad_type["status"] == "error"
        assert bad_action["status"] == "error"
        assert no_params["status"] == "insufficient_data"
        for res in (empty, bad_type, bad_action, no_params):
            assert set(res) == ENVELOPE_KEYS

    def test_determinism(self, skill):
        params = {
            "action": "normalize_batch",
            "records": [
                {"id": "a", "value": 20, "from_unit": "ton", "to_unit": "kg"},
                {"id": "b", "value": 450, "from_unit": "kPa", "to_unit": "psi"},
            ],
        }
        assert skill.execute(params) == skill.execute(params)


class TestTableAndCompact:
    SPEED = {"speed": {"from_unit": "mph", "to_unit": "km/h"}}

    def test_table_rows(self, skill):
        res = skill.execute(
            {
                "action": "normalize_table",
                "table": [
                    {"id": "a", "speed": 60, "name": "x"},
                    {"id": "b", "speed": "30"},
                ],
                "columns": self.SPEED,
            }
        )
        assert res["status"] == "ready"
        assert res["table"][0]["speed"] == pytest.approx(96.56064)
        assert res["table"][0]["name"] == "x"
        assert res["table"][1]["speed"] == pytest.approx(48.28032)
        assert res["results"][0]["column"] == "speed"
        assert res["results"][0]["id"] == "a"

    def test_table_columnar(self, skill):
        res = skill.execute(
            {
                "action": "normalize_table",
                "table": {"speed": [60, None], "label": ["p", "q"]},
                "columns": self.SPEED,
            }
        )
        assert res["table"]["speed"][0] == pytest.approx(96.56064)
        assert res["table"]["speed"][1] is None
        assert res["table"]["label"] == ["p", "q"]
        assert res["summary"]["skipped"] == 1
        assert res["results"][0]["id"] == 0

    def test_table_text_cell_rejected(self, skill):
        res = skill.execute(
            {
                "action": "normalize_table",
                "table": [{"speed": "12.5 kg"}, {"speed": 10}],
                "columns": self.SPEED,
            }
        )
        assert res["status"] == "warning"
        assert res["errors"][0]["code"] == "invalid_value"
        assert res["errors"][0]["column"] == "speed"
        assert res["errors"][0]["id"] == 0
        assert res["table"][0]["speed"] == "12.5 kg"

    def test_table_canonical_column(self, skill):
        res = skill.execute(
            {
                "action": "normalize_table",
                "table": [{"t": 20}],
                "columns": {"t": {"from_unit": "C"}},
            }
        )
        assert res["table"][0]["t"] == pytest.approx(293.15)
        assert res["results"][0]["to_unit"] == "K"

    def test_table_bad_spec(self, skill):
        table = [{"speed": 1}]
        for columns in (
            {"speed": {"to_unit": "m"}},
            {"speed": {"from_unit": "xyz"}},
            {"speed": {"from_unit": "mph", "to_unit": "kg"}},
            "speed",
            {},
        ):
            res = skill.execute(
                {"action": "normalize_table", "table": table, "columns": columns}
            )
            assert res["status"] == "error"
            assert set(res) == ENVELOPE_KEYS
        empty = skill.execute(
            {"action": "normalize_table", "table": [], "columns": self.SPEED}
        )
        assert empty["status"] == "insufficient_data"
        ragged = skill.execute(
            {
                "action": "normalize_table",
                "table": {"speed": [1, 2], "x": [1]},
                "columns": self.SPEED,
            }
        )
        assert ragged["status"] == "error"

    def test_compact_bounds_output(self, skill):
        records = [
            {"id": i, "value": i, "from_unit": "km", "to_unit": "m"}
            for i in range(4995)
        ]
        records += [
            {"id": f"bad{i}", "value": 1, "from_unit": "kg", "to_unit": "m"}
            for i in range(5)
        ]
        res = skill.execute(
            {"action": "normalize_batch", "records": records, "compact": True}
        )
        assert res["compact"] is True
        assert len(res["results"]) == 5
        assert len(res["errors"]) == 5
        assert res["results_omitted"] == 4990
        assert res["stats"]["m"] == {"count": 4995, "min": 0.0, "max": 4994000.0}
        assert res["summary"]["converted"] == 4995

    def test_compact_table_omits_table(self, skill):
        res = skill.execute(
            {
                "action": "normalize_table",
                "table": [{"speed": 60}],
                "columns": self.SPEED,
                "compact": True,
            }
        )
        assert "table" not in res
        assert res["stats"]["km/h"]["count"] == 1
