# Telemetry Normalizer Directive

## When to invoke

Invoke `data_engineering/telemetry_normalizer` when receiving raw, unformatted, or vendor-specific telemetry data from sensors, robotics hardware, IoT fleets, HVAC building controllers, or environmental monitoring stations.

Use this skill before passing sensor telemetry to spatial planners, diagnostic engines, or reasoning models to prevent hallucinations caused by timestamp epoch formats, non-SI units, out-of-bounds readings, or floating-point sensor faults.

## When NOT to invoke

- Do not invoke for high-level textual reports or pre-aggregated statistical summaries.
- Do not invoke to perform machine learning forecasting, trend extrapolation, or generative physical simulation; this skill performs deterministic, zero-hallucination unit harmonization, timestamp parsing, and sensor validation only.
- Do not pass live URLs or streaming socket handles; pre-load the telemetry records and pass them inline as `raw_telemetry`.

## Operational Parameters

- `action`: Use `normalize` (default) for standard telemetry processing, `list_profiles` to discover bundled domain models, or `validate` to inspect structural health and boundary conformance without payload enrichment.
- `schema_profile`: Required for `normalize` and `validate`. Must match one of the bundled profiles:
  - `robotics_kinematics_imu`: Linear acceleration (m/s2), angular velocity (rad/s), orientation, temperature, and battery voltage.
  - `environmental_air_quality`: PM2.5 (ug/m3), PM10 (ug/m3), CO2 (ppm), temperature, and relative humidity.
  - `energy_battery_fleet`: High-voltage pack voltage (V), current (A), state of charge (%), and cell temperature.
  - `smart_building_hvac`: Airflow (m3/h), static pressure (Pa), zone temperature, and damper position (%).
- `raw_telemetry`: Pass a single dictionary reading or an array of reading dictionaries.
- `unit_system`: Set to `si` (default) or `canonical` for standard SI units.
- `output_format`: Set to `canonical` (default) for typed observation records or `jsonld` for semantic W3C SOSA/SSN linked data export.

## Interpreting Status Envelopes

- `ready`: All telemetry records were successfully mapped and fall within nominal physical boundaries.
- `warning`: Telemetry was normalized, but one or more readings were tagged as `out_of_bounds` or `sensor_fault` (such as stuck readings or floating-point NaN values). Review `quality_metrics` and specific observation `quality` flags before issuing physical actuation commands.
- `insufficient_data`: The payload was empty or omitted required telemetry structures.
- `error`: The request specified an unknown `schema_profile` or malformed input type.

## Chaining and Downstream Consumption

1. Pass raw sensor ingestion payloads directly to `data_engineering/telemetry_normalizer`.
2. Inspect `quality_metrics` for `coverage_score` and anomaly counts (`out_of_bounds_count`, `sensor_fault_count`).
3. If forwarding observations to safety-critical robot controllers, discard or isolate readings where `quality != "valid"`.
4. If exporting to knowledge graphs or smart city digital twins, request `output_format: "jsonld"`.
