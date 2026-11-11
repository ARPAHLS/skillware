from typing import Any, Dict
from skillware.core.base_skill import BaseSkill

class UnitConverterSkill(BaseSkill):
    """
    Converts values between common units of measurement:
    length, weight, temperature, and speed.
    """

    @property
    def manifest(self) -> Dict[str, Any]:
        return {
            "name": "utilities/unit_converter",
            "version": "0.1.0",
        }

    CONVERSIONS = {
        # Length — base unit: meters
        "km":      ("length", 1000),
        "m":       ("length", 1),
        "cm":      ("length", 0.01),
        "mm":      ("length", 0.001),
        "miles":   ("length", 1609.34),
        "mile":    ("length", 1609.34),
        "yards":   ("length", 0.9144),
        "feet":    ("length", 0.3048),
        "inches":  ("length", 0.0254),

        # Weight — base unit: kilograms
        "kg":      ("weight", 1),
        "g":       ("weight", 0.001),
        "mg":      ("weight", 0.000001),
        "lbs":     ("weight", 0.453592),
        "lb":      ("weight", 0.453592),
        "ounces":  ("weight", 0.0283495),
        "oz":      ("weight", 0.0283495),

        # Speed — base unit: meters per second
        "mps":     ("speed", 1),
        "kph":     ("speed", 0.277778),
        "mph":     ("speed", 0.44704),
        "knots":   ("speed", 0.514444),
    }

    def _convert_temperature(self, value: float, from_unit: str, to_unit: str):
        """Temperature needs its own logic since it's not a simple multiply."""
        f = from_unit.lower()
        t = to_unit.lower()

        # Convert to Celsius first
        if f == "celsius":
            celsius = value
        elif f == "fahrenheit":
            celsius = (value - 32) * 5 / 9
        elif f == "kelvin":
            celsius = value - 273.15
        else:
            return None

        # Convert from Celsius to target
        if t == "celsius":
            return celsius
        elif t == "fahrenheit":
            return (celsius * 9 / 5) + 32
        elif t == "kelvin":
            return celsius + 273.15
        else:
            return None

    def execute(self, params: Dict[str, Any]) -> Any:
        value = params.get("value")
        from_unit = str(params.get("from_unit", "")).lower().strip()
        to_unit = str(params.get("to_unit", "")).lower().strip()

        if value is None:
            return {"error": "value is required."}
        if not from_unit or not to_unit:
            return {"error": "from_unit and to_unit are required."}

        # Handle temperature separately
        temp_units = {"celsius", "fahrenheit", "kelvin"}
        if from_unit in temp_units or to_unit in temp_units:
            if from_unit not in temp_units or to_unit not in temp_units:
                return {"error": f"Cannot convert between temperature and non-temperature units."}
            result = self._convert_temperature(value, from_unit, to_unit)
            if result is None:
                return {"error": f"Unrecognised temperature unit."}
            return {
                "original_value": value,
                "from_unit": from_unit,
                "to_unit": to_unit,
                "converted_value": round(result, 6),
            }

        # Handle all other unit types
        if from_unit not in self.CONVERSIONS:
            return {"error": f"Unrecognised unit: '{from_unit}'."}
        if to_unit not in self.CONVERSIONS:
            return {"error": f"Unrecognised unit: '{to_unit}'."}

        from_category, from_factor = self.CONVERSIONS[from_unit]
        to_category, to_factor = self.CONVERSIONS[to_unit]

        if from_category != to_category:
            return {"error": f"Cannot convert '{from_unit}' ({from_category}) to '{to_unit}' ({to_category})."}

        # Convert: source → base unit → target unit
        base_value = value * from_factor
        result = base_value / to_factor

        return {
            "original_value": value,
            "from_unit": from_unit,
            "to_unit": to_unit,
            "converted_value": round(result, 6),
        }