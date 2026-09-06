# Creative Deck Builder Instructions

You are equipped with `creative/deck_builder`, a deterministic skill for validating, assembling, and inspecting Microsoft PowerPoint (`.pptx`) presentations from structured JSON specifications.

## Purpose & Boundaries

Use this tool when a user or upstream workflow requests an editable slide deck, investor pitch, technical architecture presentation, or business briefing.

- **Local & Deterministic**: The skill executes entirely offline. It does not generate text copy or images autonomously; it strictly assembles the structure, layouts, tables, charts, and image assets supplied in `deck_spec`.
- **Workflow Separation**: Generate narrative outlines and copy in your agent loop, then compile them into a valid `deck_spec` and pass them to `deck_builder`.
- **Editable Output**: Renders standard OpenXML `.pptx` documents that can be opened and styled in Microsoft PowerPoint, LibreOffice Impress, Apple Keynote, or Google Slides.

---

## Actions

| Action | Parameters | Description |
| :--- | :--- | :--- |
| `validate_spec` *(default)* | `deck_spec`, `strict` *(optional)* | Validates `deck_spec` against JSON schema and business rules. Emits warnings for truncated text or asset issues without writing files. |
| `render` | `deck_spec`, `output_path`, `template_id` *(optional)*, `theme` *(optional)*, `strict` *(optional)* | Assembles slides, applies theme tokens, inserts images/charts, writes `.pptx` to disk. |
| `inspect` | `input_path` | Reads an existing `.pptx` presentation and returns slide counts, titles, layout names, and notes presence. |
| `list_templates` | *(none)* | Enumerates bundled template IDs, names, descriptions, and aspect ratios. |
| `lint_deck` | `deck_spec`, `min_score` *(optional)*, `strict_a11y` *(optional)* | Analyzes deck specification for presentation quality, text density, and accessibility best practices. Returns score (0–100), issue counts, and rule findings. |
| `suggest_outline` | `archetype`, `topic` *(optional)*, `constraints` *(optional)* | Generates a structured slide outline, recommendations, and skeleton `deck_spec` for an archetype (`investor_pitch`, `technical_brief`, `quarterly_review`, `product_launch`, `training_workshop`). |

---

## Slide Layout Types

`deck_spec.slides` accepts an array of slide objects. Each must include `"type"`. Supported layout types:

1. **`title`**: Cover slide.
   - Keys: `title` (required), `subtitle` (optional), `image` (optional logo or hero graphic), `speaker_notes` (optional).
2. **`section`**: Section divider.
   - Keys: `title` (required), `subtitle` (optional), `speaker_notes` (optional).
3. **`bullets`**: Standard list slide.
   - Keys: `title` (required), `bullets` (required array of strings), `speaker_notes` (optional).
   - *Soft limit*: Bullets over 120 characters emit a non-fatal `BULLET_TRUNCATED` warning.
4. **`two_column`**: Comparative or two-panel text/bullets.
   - Keys: `title` (required), `left` (string or array), `right` (string or array), `speaker_notes` (optional).
5. **`image`**: Visual showcase.
   - Keys: `title` (optional), `image` (required `{path: ...}`, `{base64: ...}`, or `{placeholder_id: ...}`), `caption` (optional), `speaker_notes` (optional).
6. **`image_caption`**: Side-by-side graphic and detailed explanation.
   - Keys: `title` (required), `image` (required), `body` (required explanatory copy), `speaker_notes` (optional).
7. **`quote`**: Pull-quote or executive testimony.
   - Keys: `quote` (required), `attribution` (optional name/title), `speaker_notes` (optional).
8. **`table`**: Tabular grid.
   - Keys: `title` (required), `columns` (array of header names), `rows` (array of row arrays), `speaker_notes` (optional).
9. **`chart`**: Data visualization.
   - Keys: `title` (required), `chart` (object with `kind` (`bar`, `line`, `pie`), `categories` (array of labels), `series` (array of `{name: ..., values: [...]}`)), `speaker_notes` (optional).
10. **`timeline`**: Milestone roadmap with status badges.
    - Keys: `title` (required), `items` (required array of `{date: ..., title: ..., description: ..., status?: "completed"|"in_progress"|"planned"}`), `speaker_notes` (optional).
11. **`metrics`**: KPI big number cards with trend indicators.
    - Keys: `title` (required), `metrics` (required array of `{value: ..., label: ..., delta?: ..., trend?: "up"|"down"|"neutral"}`), `speaker_notes` (optional).
12. **`comparison`**: Structured comparison cards or pros/cons matrix.
    - Keys: `title` (required), `left` (object with `title` and `items`), `right` (object with `title` and `items`), `speaker_notes` (optional).
13. **`blank`**: Clean canvas for freeform editing.
    - Keys: `speaker_notes` (optional).

---

## Image Handling, Placeholders & Fit Policies

- **Offline-First & Transposition**:
  Images are processed locally using Pillow. EXIF orientation tags are automatically normalized and non-RGB color spaces (CMYK, Grayscale, RGBA) are converted cleanly.
- **Image Fit Policies**:
  Each image can specify `"fit"`:
  - `"contain"` *(default)*: Scales proportionally to fit within bounding box, centered with letterboxing/pillarboxing.
  - `"cover"` or `"crop_center"`: Crops image symmetrically from center to fill target aspect ratio without distortion.
  - `"stretch"`: Scales directly to bounding box dimensions.
  - `"native"`: Keeps native dimensions bounded by slide boundaries.
- **Offline Placeholders**:
  When an asset is not yet available, specify `"placeholder_id"`:
  - Supported IDs: `"hero"`, `"logo"`, `"icon"`, `"chart_backdrop"`, `"headshot"`.
  - Placeholders are procedurally generated via Pillow with neutral monochrome branding, subtle grid lines, and an icon badge. No network connection is required.
  - Optionally provide `"placeholder_prompt"` to describe the planned image for later substitution by an image generation pipeline.
- **Paths and Base64 Only (No Remote URLs)**:
  `image.path` must point to an existing local file on the filesystem, and `image.base64` must contain valid base64-encoded image bytes. Remote HTTP/HTTPS URLs are rejected with `ASSET_NOT_FOUND`.
- **Supported Formats**: PNG, JPEG, WEBP.

---

## Bundled Templates

- **`pitch_v1`** *(default)*: 16:9 widescreen modern startup aesthetic with bold typography and purple/indigo accents (`#6E57E0`).
- **`corporate_v1`**: 16:9 widescreen structured executive presentation with navy and slate accents (`#1E3A8A`).
- **`minimal_v1`**: 16:9 widescreen clean monochrome layout with black/charcoal accents (`#262626`).

---

## Quality Gates & Linting (`lint_deck`)

Autonomous agent decks often suffer from text bloat, missing titles, or monotonous slides. Call `action="lint_deck"` to run deterministic heuristic checks across the `deck_spec`:

- **Score Calculation**: Starts at `100`. Warnings deduct 5 points, errors deduct 15 points.
- **Rule Codes**:
  - `WALL_OF_TEXT`: A bullet exceeds 200 characters or slide exceeds 600 total text characters.
  - `DECK_TOO_LONG`: Slide count exceeds 30 slides.
  - `MISSING_ALT`: Image without an `alt` tag (evaluated when `strict_a11y: true`).
  - `ORPHAN_BULLET`: Slide has exactly 1 bullet point (recommend >= 2 or convert to statement).
  - `EMPTY_TITLE`: Slide title is missing, empty, or whitespace.
  - `CHART_NO_TITLE`: Chart slide missing title.
  - `METRIC_WITHOUT_LABEL`: Metric entry contains a value but no descriptive label.
  - `LOW_SLIDE_COUNT`: Deck contains fewer than 3 slides.
  - `MONOTONOUS_LAYOUT`: 4 or more consecutive slides share the exact same layout type.
- **Strict Enforcement**: Pass `min_score` (e.g. `80`) to automatically fail `passed: false` if score falls below threshold.

---

## Archetype Outlines (`suggest_outline`)

Use `action="suggest_outline"` to bootstrap structured presentations:

- **Supported Archetypes**:
  - `investor_pitch`: Problem, Solution, Market Size, Product Demo, Business Model, Traction, Team, Ask.
  - `technical_brief`: Executive Summary, Architecture Overview, Deep Dive, Benchmarks, Security & Compliance, Deployment Roadmap.
  - `quarterly_review`: Executive Summary, KPI Scorecard, Quarterly Achievements, Roadmap Timeline, Challenges & Learnings, Next Quarter Priorities.
  - `product_launch`: Vision & Value Prop, Feature Highlights, Architecture & Metrics, Customer Testimonial, Availability Timeline, Call to Action.
  - `training_workshop`: Agenda & Objectives, Core Concept Deep Dive, Architecture Walkthrough, Comparative Analysis, Key Takeaways, Hands-on Next Steps.
- **Constraint Filtering**: Pass `constraints` (e.g. `["no pricing", "confidential"]`) to filter out sensitive sections (e.g., pricing or financial tiers).
- **Output**: Returns recommended slide types, narrative guidance, and a pre-structured `deck_spec` skeleton ready for agent population.

---

## Enterprise Governance

For enterprise compliance and corporate identity:

- **Document Classification**: Pass `"classification": "CONFIDENTIAL" | "INTERNAL" | "PUBLIC" | "RESTRICTED"` under `deck_spec.metadata` (or at root for compatibility). Renders a standardized classification ribbon header on each slide.
- **Legal Footer**: Pass `"legal_footer"` under `deck_spec.metadata` (or at root) to stamp a legal disclaimer across the footer of all slides.

---

## Recommended Agent Workflow

1. **Bootstrap Outline**: Call `creative/deck_builder` with `action="suggest_outline"`, selecting an `archetype` and specifying constraints.
2. **Draft Content**: Populate slide copy, metrics, comparison points, and timeline items into the skeleton `deck_spec`.
3. **Pre-flight Validation**: Call `action="validate_spec"` to catch schema errors and text truncations.
4. **Quality Linting**: Call `action="lint_deck"` with `min_score=80` to verify text density, readability, and visual variety.
5. **Render Presentation**: Call `action="render"` specifying `output_path` (e.g. `/tmp/briefing.pptx`).
6. **Report to User**: Return file path, slide count, quality score, and slide titles.

---

## Worked Example: NL Prompt to 7-Slide Deck Spec

### User Prompt
> "Build a 7-slide enterprise pitch deck for CortexEngine, an autonomous database optimization platform. Keep it high-level, include our architecture, 3 customer proof points, a benchmark comparison table, and next steps. Do NOT include pricing or licensing tiers."

### Agent Mapping Rationale
- Slide 1 (`title`): Platform name, tagline, cover.
- Slide 2 (`section`): Problem overview ("The High Cost of Database Inefficiency").
- Slide 3 (`bullets`): Core value proposition (3 concise points, each under 120 chars).
- Slide 4 (`two_column`): Legacy manual tuning vs CortexEngine autonomous tuning.
- Slide 5 (`table`): Benchmark comparison (Latency, Throughput, Cost Reduction across 3 engines).
- Slide 6 (`quote`): Enterprise customer endorsement quote.
- Slide 7 (`bullets`): Next steps & pilot deployment CTA (respecting constraint: no pricing).

### Generated `deck_spec`
```json
{
  "title": "CortexEngine Enterprise Overview",
  "template_id": "pitch_v1",
  "theme": {
    "accent_color": "#6E57E0",
    "font_heading": "Calibri",
    "font_body": "Calibri"
  },
  "slides": [
    {
      "type": "title",
      "title": "CortexEngine",
      "subtitle": "Autonomous Database Optimization for Modern Clouds",
      "speaker_notes": "Introduce CortexEngine as a zero-touch optimization layer."
    },
    {
      "type": "section",
      "title": "The Scaling Bottleneck",
      "subtitle": "Why manual index tuning fails under petabyte workloads"
    },
    {
      "type": "bullets",
      "title": "Autonomous Execution",
      "bullets": [
        "Continuous telemetry inspection with zero query overhead",
        "Deterministic index recommendation and instant rollout",
        "Automated rollback on query regression or latency spikes"
      ]
    },
    {
      "type": "two_column",
      "title": "Operational Comparison",
      "left": [
        "Manual DBA Tuning",
        "Reactive incident response",
        "Multi-week rollout cycles"
      ],
      "right": [
        "CortexEngine",
        "Proactive autonomous adaptation",
        "Real-time index updates without downtime"
      ]
    },
    {
      "type": "table",
      "title": "Benchmark Performance",
      "columns": ["Workload", "Manual DBA", "CortexEngine", "Improvement"],
      "rows": [
        ["TPC-C OLTP", "4.2 ms", "1.1 ms", "3.8x faster"],
        ["Analytical Query", "18.5 s", "3.2 s", "5.7x faster"],
        ["Peak Cloud Spend", "$45,000/mo", "$18,500/mo", "-58% cost"]
      ]
    },
    {
      "type": "quote",
      "quote": "CortexEngine slashed our p99 query latency by 70% within 48 hours of deployment.",
      "attribution": "VP of Infrastructure, Global Fintech"
    },
    {
      "type": "bullets",
      "title": "Next Steps: 30-Day Proof of Value",
      "bullets": [
        "Non-intrusive read-only telemetry audit",
        "Simulated index impact report against live workloads",
        "Dedicated implementation engineering support"
      ],
      "speaker_notes": "Emphasize zero risk PoV; avoid pricing discussion until technical validation."
    }
  ]
}
```

---

## Error Codes

- `INVALID_SPEC`: The provided `deck_spec` failed JSON Schema validation.
- `OUTPUT_PATH_UNSAFE`: The target path contains directory traversal sequences (`..`) or lacks `.pptx` extension.
- `OUTPUT_PATH_MISSING`: `output_path` was not specified for `action='render'`.
- `INPUT_PATH_MISSING`: `input_path` was not specified for `action='inspect'`.
- `INSPECT_FAILED`: File could not be found or read as a PowerPoint document.
- `CHART_DIMENSION_MISMATCH`: The number of series data points does not match categories count.
- `RENDER_FAILED`: python-pptx encountered an unrecoverable rendering exception.