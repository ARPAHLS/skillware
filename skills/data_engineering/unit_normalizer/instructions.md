# Unit Normalizer

`data_engineering/unit_normalizer` converts values between units deterministically,
in bulk, with an audit trail. Use it instead of doing unit arithmetic in your own
reasoning whenever more than a handful of values are involved, a value arrives as a
compound string, or a unit could be read more than one way.

## When to invoke

- A table, CSV, JSON array, or bill of materials carries quantities in mixed or
  non-SI units that must be harmonized before analysis.
- A value arrives as text such as `5 ft 11 in`, `3 1/2 gal`, `120 km/h`, `3.5 MPa`,
  or `5'11"`. Compound and fractional strings are where mental arithmetic fails.
- A downstream consumer (a robotics controller, a physics model, a database column)
  requires SI units: meters, kilograms, seconds, kelvin, pascals, radians, rad/s.
- A document uses an ambiguous unit (`ton`, `gal`, `oz`, `pt`, `qt`) and the reading
  must be recorded rather than guessed.

## When not to invoke

- For one obvious conversion inside a sentence where no record is needed.
- For continuous sensor streams, IMU arrays, or W3C SOSA/SSN observations. That is
  `data_engineering/telemetry_normalizer`, which applies fixed sensor profiles,
  timestamps, and physical bounds. This skill handles tabular records, document
  quantities, and ad hoc pipeline values.
- For currencies, exchange rates, or any value that changes over time. No live data
  is used.

## Actions

- `normalize`: one `value` with `from_unit` and optional `to_unit`.
- `normalize_batch`: `records`, a list of `{id, value, from_unit, to_unit}`. `id`
  defaults to the record index; `to_unit` defaults to the SI unit.
- `canonicalize`: like `normalize` or `normalize_batch`, but always converts to the SI
  unit of each value's dimension, ignoring any `to_unit`.
- `parse_quantity`: `text` plus optional `target_unit`.
- `normalize_table`: `table` (a list of row objects or an object of column lists) and
  `columns`, e.g. `{"speed": {"from_unit": "mph", "to_unit": "km/h"}}`. The table comes
  back in the same shape with converted cells.

Shared options: `assume` locks ambiguous readings, `precision` (0 to 12, default 6) sets
`display_value` decimals, and `compact: true` returns statistics, five sample results,
and every error instead of every result. Use `compact` above a few hundred records.

## Interpreting the output

- `status`: `ready` when every record converted cleanly; `warning` when any record
  failed or any reading was assumed; `insufficient_data` when nothing was supplied;
  `error` when the request itself is invalid (unknown action, bad `assume`, bad
  `precision`, bad `columns`). A failed record never aborts the rest of the batch.
- `results[].value` is full precision. Use it for further computation. Quote
  `display_value` to the user.
- `result` is the single record for `normalize` and `parse_quantity`, or `null`.
- `errors[]` carry `id`, a stable `code`, and `detail`. Codes: `unknown_unit`,
  `dimension_mismatch`, `unparseable`, `invalid_value`, `invalid_record`.

## Ambiguous units

A record whose unit had more than one reading carries `assumed: true`, `assumption`,
`alternatives`, and `risk_variance` (the spread between same-dimension readings, e.g.
`12.0%` for tons). Do not present an assumed value as certain. Either tell the user
which reading was used, or re-run with `assume`, for example
`{"ton": "us_short_ton", "gal": "imperial_gallon", "oz": "oz_fluid_us"}`. Locked rows
come back as clean `ready` rows. Defaults: `ton` metric, `gal`/`pt`/`qt` US, `oz` mass
(fluid when the target is a volume), `'` and `"` feet and inches (arcminutes and
arcseconds are the alternatives).

## Limits

- Compound strings sum only within one dimension and never with temperature scales:
  `20 C 5 F` is `unparseable`. Separate pairs need whitespace (`5 ft 11 in`), except
  quote marks (`5'11"`).
- Commas are refused rather than guessed as thousands or decimal separators.
- A fraction with a decimal denominator such as `1/2.3"` is refused: it is an optical
  sensor-format designation, not a length.
- Unit products (`oz-in`, `N*m`), ambiguous units inside rates (`gal/min`), and
  caller-defined units are not supported in this version.
- Symbols are case-sensitive: `MPa` is megapascal, `mPa` is millipascal.
