# Unit Converter Skill

You have access to a unit conversion tool. Use it whenever the user asks to convert a value from one unit to another.

## When to use this skill

- The user mentions a numeric value alongside a unit (e.g. "100km", "70kg", "32°F")
- The user asks "how much is X in Y"
- The user needs a unit conversion as part of a larger calculation

## Supported categories

- **Length**: km, m, cm, mm, miles, yards, feet, inches
- **Weight**: kg, g, mg, lbs, oz
- **Temperature**: celsius, fahrenheit, kelvin
- **Speed**: kph, mph, mps, knots

## How to call the tool

Always pass three parameters:
- `value` — the numeric amount (number, not a string)
- `from_unit` — the unit to convert from, lowercase (e.g. "celsius", "km", "lbs")
- `to_unit` — the unit to convert to, lowercase

## Handling errors

If the tool returns an `error` key, explain the issue clearly to the user. Common causes:
- Unrecognised unit name — suggest the closest supported unit
- Mismatched categories — explain that e.g. weight cannot be converted to length
- Missing value — ask the user to provide a numeric amount

## Response style

Always confirm the original value and unit alongside the result. For example:
"100 km is equal to 62.14 miles."