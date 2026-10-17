# office/web_form_mapper

Inspects, maps identity profiles to, previews, and submits web forms (HTML & SPAs) with automatic CSRF/hidden state preservation, address book `legal_profile` integration, and strict confirmation safety gates.

## Skill Context & Core Behavior

The skill exposes 4 deterministic actions:
1. `inspect`: Parses HTML content or URL, extracting form elements, input types, required attributes, existing values, and hidden tokens (CSRF tokens, `__VIEWSTATE`, etc.).
2. `map`: Matches form fields against a contact from `addressbook.yaml` (using `use_self: true` or `contact_id`) or an explicit `payload` dictionary. Generates a `fill_plan` and surfaces unmapped required fields (`needs_input`).
3. `preview`: Non-mutating validation step. Produces a human-readable comparison diff table showing field labels, selectors, proposed values, and confidence scores.
4. `submit`: Gated execution. Requires `confirmed: true` when `dry_run: false`. Dispatches HTTP POST or headless browser submission and captures receipt/screenshot artifacts.

## When to Invoke

- **Government & Regulatory Portals**: When filing tax declarations, business registry filings, license renewals, or compliance forms on web portals.
- **Legacy SaaS / Internal Tools**: When populating standard web forms with data already present in `addressbook.yaml` (e.g. operator identity or client corporate entity data).
- **Form Auditing & Field Discovery**: When an agent needs to inspect a web form's required inputs before deciding what information to request from the user.

## When NOT to Invoke

- **Static PDF Documents**: Use `office/pdf_form_filler` instead for local PDF AcroForms.
- **CAPTCHA & WAF Protected Portals**: When forms are gated by active CAPTCHA challenges or anti-bot Cloudflare Turnstile barriers requiring manual interactive solving.
- **Multi-Factor Authentication (MFA)**: Forms requiring SMS/TOTP codes in real time (the skill will fail-closed with `STATUS_BLOCKED`).

## Typical Agent Interaction Loop

```
Step 1: Inspect form
Agent -> web_form_mapper(action="inspect", html_content="...")
Result -> { fields: [...], hidden_fields: { "_csrf": "..." } }

Step 2: Map with address book profile
Agent -> web_form_mapper(action="map", html_content="...", use_self=True)
Result -> { fill_plan: [...], unmapped_fields: [] }

Step 3: Preview diff for user review
Agent -> web_form_mapper(action="preview", fill_plan=[...])
Result -> { preview_table: [...] }
Agent presents preview table to human user and asks for explicit confirmation.

Step 4: Execute submission upon user approval
User -> "Looks good, submit it."
Agent -> web_form_mapper(action="submit", fill_plan=[...], confirmed=True, dry_run=False)
Result -> { status: "success", submission_result: { "receipt_path": "...", "status_code": 200 } }
```

## Security & Safety Boundaries

- **Confirmation Gate**: Any attempt to call `submit` with `dry_run=False` while `confirmed=False` will fail immediately with `CONFIRMATION_REQUIRED`.
- **Hidden State Preservation**: Hidden fields and anti-CSRF tokens extracted during `inspect` are automatically preserved during submission.
- **Fail-Closed on Challenges**: If bot detection or CAPTCHA elements are found, the skill returns status `"blocked"` with reason code `CAPTCHA_DETECTED` to prevent accounts from being flagged or banned.
