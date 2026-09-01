# Deceptive UI Guard

You are using the `security/deceptive_ui_guard` skill (v0.2.0).

Run this skill on **web HTML surfaces** before an autonomous agent clicks checkout controls, accepts subscriptions, or passes scraped page text into model context. The skill is a deterministic, offline surface-integrity layer — not a guarantee against every semantic manipulation.

## Trust model

- **HTML-first, offline by default.** Prefer `html_content` from the host browser. Optional public `url` fetch uses SSRF guards; analysis stays deterministic with no LLM detection path.
- **Dual-surface & optional render lane.** Compares extractable DOM text against the visible surface and supports headless Chromium computed-style diffing (`render_mode='auto'|'force'`) to catch external-CSS hidden fees and zero-size overlay traps.
- **Allowlist-guarded channel matching.** Standard accessibility screen-reader text (`sr-only`, `visually-hidden`), CMP cookie banners (OneTrust, Cookiebot), and SEO tags are allowlisted to prevent false positives unless containing imperative overrides.
- **Corroboration gates & zone weighting.** Subtrees are classified into `checkout`, `modal`, `cmp`, `navigation`, and `general` zones with severity weighting.
- **Warn only.** Never click, submit forms, or complete checkout. Escalate high/critical checkout findings to a human.

## When to invoke

- Before clicking pay, subscribe, or accept on an untrusted page
- Before feeding page HTML or visible excerpts into the host LLM
- When the user task involves checkout, billing, signup, or cookie/consent walls
- After capturing DOM HTML from a browser automation step (Playwright, Selenium, WebView snapshot)

## How to interpret results

| Field | Meaning |
| :--- | :--- |
| `is_safe` | `true` when posture is clean at the chosen sensitivity |
| `status` | Aggregate posture: `ok`, `caution`, `warning`, or `blocked` |
| `trust_score` | 0–100 page trust score |
| `surface_integrity` | `ok`, `degraded`, or `compromised` |
| `risk_level` | Aggregated severity (`none` when clean) |
| `detected_threat` | Primary human-readable reason when unsafe |
| `findings` | Published signals (`type`, `subtype`, `severity`, `selector`, `snippet`, `zone`, `evidence`) |
| `agent_guidance` | `do_not_click` selectors, `verify_before_payment`, summary |
| `sanitized_excerpt` | Visible-surface text safe for downstream context |
| `zone_summary` | Breakdown of DOM zones identified and their risk weights |
| `session_recommendation` | Guidance based on session nag loop detection |
| `fetch_status` | `skipped`, `ok`, or error detail when `url` was used |
| `offline` | `true` when only local HTML was analyzed |
| `sensitivity` | Sensitivity level used for the scan |

If `is_safe` is `false`, honor `agent_guidance.do_not_click` and prefer `sanitized_excerpt` over raw HTML for downstream reasoning.

## Parameters

- `html_content` (preferred): Sanitized HTML or DOM snapshot from the host browser
- `url` (optional): Public http(s) URL when HTML is unavailable (network + SSRF guards)
- `sensitivity`: `strict`, `balanced` (default), or `lenient`
- `intended_action` (optional): Task hint (e.g. complete checkout) to tune zone weighting and guidance
- `render_mode` (optional): `off` (default), `auto`, or `force` for optional Playwright computed-style diffing
- `surface_profile` (optional): `desktop` (default), `mobile`, or `auto` (inferred from viewport meta)
- `session_fingerprint` (optional): Stable session hash to detect recurring nag loops across pages

## Allowlist maintenance

Allowlists live under `skills/security/deceptive_ui_guard/kb/`:
- `allowlist_sr_only.json`: Add new legitimate accessibility/screen-reader classes or patterns.
- `allowlist_cmp.json`: Add new Consent Management Platform vendor selectors and benign copy.
- `allowlist_seo.json`: Add valid metadata tags and structured data script types.
- `deception_lexicon.json`: Curated dark pattern phrases and categories.

