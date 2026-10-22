import pytest
from skills.utilities.unit_converter.skill import UnitConverterSkill

@pytest.fixture
def skill():
    return UnitConverterSkill()


# --- Length ---

def test_km_to_miles(skill):
    result = skill.execute({"value": 100, "from_unit": "km", "to_unit": "miles"})
    assert abs(result["converted_value"] - 62.1371) < 0.01

def test_meters_to_feet(skill):
    result = skill.execute({"value": 1, "from_unit": "m", "to_unit": "feet"})
    assert abs(result["converted_value"] - 3.28084) < 0.01


# --- Weight ---

def test_kg_to_lbs(skill):
    result = skill.execute({"value": 70, "from_unit": "kg", "to_unit": "lbs"})
    assert abs(result["converted_value"] - 154.32) < 0.01

def test_oz_to_grams(skill):
    result = skill.execute({"value": 16, "from_unit": "oz", "to_unit": "g"})
    assert abs(result["converted_value"] - 453.59) < 0.01


# --- Temperature ---

def test_celsius_to_fahrenheit(skill):
    result = skill.execute({"value": 100, "from_unit": "celsius", "to_unit": "fahrenheit"})
    assert result["converted_value"] == 212.0

def test_freezing_point(skill):
    result = skill.execute({"value": 0, "from_unit": "celsius", "to_unit": "fahrenheit"})
    assert result["converted_value"] == 32.0

def test_celsius_to_kelvin(skill):
    result = skill.execute({"value": 0, "from_unit": "celsius", "to_unit": "kelvin"})
    assert result["converted_value"] == 273.15


# --- Speed ---

def test_mph_to_kph(skill):
    result = skill.execute({"value": 60, "from_unit": "mph", "to_unit": "kph"})
    assert abs(result["converted_value"] - 96.56) < 0.1


# --- Error handling ---

def test_unknown_unit(skill):
    result = skill.execute({"value": 10, "from_unit": "furlongs", "to_unit": "km"})
    assert "error" in result

def test_mismatched_categories(skill):
    result = skill.execute({"value": 10, "from_unit": "kg", "to_unit": "km"})
    assert "error" in result

def test_temperature_mixed_with_length(skill):
    result = skill.execute({"value": 100, "from_unit": "celsius", "to_unit": "km"})
    assert "error" in result

def test_missing_value(skill):
    result = skill.execute({"from_unit": "km", "to_unit": "miles"})
    assert "error" in result