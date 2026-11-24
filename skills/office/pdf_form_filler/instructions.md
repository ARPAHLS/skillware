The `office/pdf_form_filler` skill provides deterministic inspection, validation, and filling of static AcroForm PDFs using either curated KB/operator templates or ad-hoc PDF paths.

### Choosing the Right Path
- **Multi-turn user interview** (user asks *"help me fill out a W-8BEN"* without supplying all fields at once): Use **Path C (`session_init` → `session_update` → `session_preview` → `session_finalize`)**.
- **Single-shot / programmatic fill** (caller already has all field values ready): Use **Path A (`list_templates` → `get_template_schema` → `validate` → `fill`)** for curated or custom templates, or **Path B (`inspect` → `validate` → `fill`)** for ad-hoc PDFs.

### Custom Templates & Output Directory
- Operators manage custom PDF templates outside `site-packages` via `skillware pdf` (`init`, `import --auto-map`, `status`, `map-generate`, `map-validate`, `output-dir`).
- Template precedence: `PDF_TEMPLATES_DIR` > `.skillware.yaml` `pdf.templates_dir` > user `~/.config/skillware/pdf_templates/` > bundled KB.
- Filled output precedence (when `output_path` is omitted): explicit `output_dir` param > `PDF_OUTPUT_DIR` > `.skillware.yaml` / global `config.yaml` `pdf.output_dir` > current working directory (or alongside input for ad-hoc PDFs). Non-existent output folders are auto-created.

### Operational Protocol

#### Path A: Curated KB Templates (Single-Shot: W-8BEN, W-9, W-8BEN-E, Form 8966)
1. **Discover (`action: "list_templates"`):** Optionally filter by `category` (e.g., `"tax"`) or `jurisdiction` (e.g., `"US"`).
2. **Fetch Schema by Section (`action: "get_template_schema"`):** Pass `template_id` and `section` (e.g., `"part_1_identification"`) to load one section at a time and protect your context window.
3. **Validate (`action: "validate"`):** Pass `template_id` and `edits` keyed by semantic field `id`.
4. **Fill with Confirmation Gate (`action: "fill"`):** Call with `confirmed: false` for a **PII-redacted** `preview`, then `confirmed: true` and `flatten: true` to write `<template_id>_<timestamp>_<filler>.pdf`.

#### Path B: Custom / Ad-Hoc PDFs (Single-Shot)
1. **Inspect (`action: "inspect"`):** Pass `pdf_path` (and optionally `schema_path` for `validate`/`fill`).
2. **Validate (`action: "validate"`):** Pass `pdf_path` and `edits`.
3. **Fill (`action: "fill"`):** Pass `pdf_path`, `edits`, `confirmed: true`, and optional `output_path` / `flatten: true`.

#### Path C: Multi-Turn Conversational Interview (`session_init` → `session_finalize`)
1. **`session_init`:** Pass `template_id` (or `pdf_path`) to start a file-backed session (`session_id`).
   - **Address book `legal_profile` autofill (optional):** Pass `use_profile: true` to pre-fill from the operator's `is_self: true` contact in `addressbook.yaml`, or pass `contact: "<id_or_alias>"` to pre-fill for a client/entity (e.g., `"acme_corp"`). Omit both for a plain manual interview.
   - **Guards:** If `error_code: "ambiguous_contact"` is returned, show the `candidates` and ask the user to pick an exact `contact_id`. If `warnings` contains `entity_type_mismatch`, alert the user before filling.
2. **`session_update`:** Collect remaining missing fields section-by-section without overwhelming the user. Pass `values`, `skip_fields` (if user opts out), or `defer_fields` (if user needs to look something up — marked `to_revise`). Users can override any autofilled field at any time.
3. **`session_preview`:** Present the PII-masked `summary_table` to the user before finalizing.
4. **`session_finalize`:** Only after explicit user approval, pass `confirmed: true` (defaults to `flatten: true`, stamps `auto_date`, and formats `typed_e_sign` as `"/s/ Name"`). If `profile_updates_suggested` is returned (because the user overrode an autofilled field), ask if they want to update `addressbook.yaml` via `skillware addressbook set-legal-profile`.

### Field Type & Signing Guidance
- **Text:** Plain string values.
- **Checkbox:** Boolean `true` or `false` (`capacity_to_sign` must be `true` on W-8BEN / W-8BEN-E).
- **Date (`signature_mode: "auto_date"`):** Supply `"MM-DD-YYYY"`, or omit / pass `"auto"` to auto-fill today's UTC date.
- **Radio Buttons:** Provide the exact `export_value` string (e.g., `"Choice1"`) or unambiguous option `label`.
- **XFA Guard:** If `unsupported_xfa_form` is returned, inform the operator that dynamic XFA forms must be converted to static AcroForms first.
