# UK Companies House Handler

You are using the `finance/uk_companies_house_handler` skill.

This skill wraps the UK Companies House REST API (`api.company-information.service.gov.uk`) with deterministic actions. It returns structured JSON envelopes (`ready`, `partial`, `needs_input`, `error`) — it does not parse conversational user text. **You** infer intent, choose actions, pass clean parameters (`query`, `company_number`, `role_hint`, `category`), handle disambiguation with the user, and render record lists in your reply.

`data/terminology_map.yaml` is a **reference lexicon** for UK/US/finance term equivalents and keyword hints; it is not a substitute for your reasoning. Prefer explicit parameters over relying on keyword routing alone.

## When to use

Use this skill when the user:

- Asks about a UK company (England, Wales, Scotland, or Northern Ireland).
- Wants directors, officers, secretaries, PSCs, or filing history for a UK entity.
- Mentions Companies House or a UK company number (8 characters, e.g. `00445790`).
- Needs multi-step registry lookups that benefit from `run_pipeline` or composite actions.

## UK terminology (present only when the user used non-UK terms)

| User may say | UK registry term | Typical action |
| :--- | :--- | :--- |
| CEO, president, chairman | Director | `get_officers` + optional `role_hint: "ceo"` |
| Owner, shareholder, beneficial owner | Person with Significant Control (PSC) | `get_pscs` |
| Secretary, corporate secretary | Secretary | `get_officers` |
| Annual report, 10-K, financials | Accounts / confirmation statement | `get_filing_history` (+ optional `category`) |
| Company, corporation, LLC | Ltd, PLC, LLP | `resolve_company` |

Only explain terminology when the user used informal or US-centric wording. Do not add disclaimers during disambiguation prompts.

## Available actions

| Action | Purpose | Required params | Optional params |
| :--- | :--- | :--- | :--- |
| `resolve_company` | Search by name; ranked candidates | `query` (clean company name) | `limit` |
| `get_company_profile` | Full profile by number | `company_number` | |
| `get_officers` | Directors and secretaries | `company_number` | `active_only` (default **true**), `limit`, `role_hint`, `officer_filter` |
| `get_pscs` | Persons with significant control | `company_number` | `active_only` |
| `get_filing_history` | Filings (accounts, returns, etc.) | `company_number` | `category`, `limit` |
| `map_intent` | Suggest an action pipeline from keywords | `intent_keywords` and/or `entities` | `entities.company_query` when actions need a company |
| `run_pipeline` | Run ordered atomic steps; halt on `needs_input`/`error` | `steps` or resume via `context` | `company_number`, `pipeline`, `stop_on`, `context` |
| `resolve_and_get_officers` | Resolve + list officers in one call | `query` **or** `company_number` | `role_hint`, `active_only`, `limit`, `officer_filter` |
| `resolve_and_get_filings` | Resolve + list filings in one call | `query` **or** `company_number` | `category`, `limit` |

**Parameter hygiene:** Pass a **clean** company name in `query` / `entities.company_query` (e.g. `Barclays`, not `Who is the CEO of Barclays?`). Pass conversational role intent via `role_hint` (e.g. `"ceo"`, `"chairman"`). Strip trailing punctuation (`?`, `.`) yourself or rely on the skill's light normalization.

## Playbook — disambiguation and multi-step queries

### Example: "Who is the CEO of Barclays?"

1. **Do not** pass the full sentence as `query`. Call `resolve_and_get_officers` with `query: "Barclays"`, `role_hint: "ceo"` (or `run_pipeline` / `map_intent` + pipeline if you prefer).
2. If `status` is **`needs_input`**, present `candidates` (e.g. Barclays Bank PLC vs other Barclays entities) and ask the user to pick.
3. After confirmation, call `get_officers` with the chosen `company_number` (and `role_hint` if still relevant), or resume `run_pipeline` with `company_number` + remaining `steps` / `context`.
4. Answer the role question using UK director terminology when appropriate, then **render the full `officers[]` list** (name, role, appointed date).

### Multi-intent queries

For combined asks (e.g. *"officers and filings for BP"*):

1. Optionally call `map_intent` with `intent_keywords: "officers, filings"` and `entities: {"company_query": "BP"}` to obtain `suggested_pipeline`.
2. Execute via `run_pipeline` with atomic steps only (`resolve_company`, `get_officers`, `get_filing_history`, …). Never nest composites inside `run_pipeline`.
3. On `needs_input`, pause, disambiguate, then resume with `company_number` and updated `context` / `pipeline`.

### Single-intent shortcuts

- Officers only: `resolve_and_get_officers` with clean `query` + optional `role_hint`.
- Filings only: `resolve_and_get_filings` with clean `query` + optional `category`.

## Understanding responses

| Status | Meaning |
| :--- | :--- |
| `ready` | Complete result — present data clearly. |
| `partial` | Preview (default limit 10 officers or filings). **Always list returned records** and state total counts from the envelope / `agent_hint`. |
| `needs_input` | Ambiguous search or missing company name for pipeline — use `candidates` or `agent_hint`. |
| `error` | Check `error_code` and `message`. Use `agent_hint` for retry guidance (`rate_limited`, `timeout`, `connection_error`). |

Every response includes `fetched_at`, `source`, and usually `context`. Pipeline/composite responses may include `pipeline: {"completed_steps": N, "total_steps": M}`.

Common `error_code` values: `not_found`, `no_results`, `rate_limited`, `timeout`, `connection_error`, `missing_query`, `missing_company_number`.

## Limitations

- Read-only public registry data; no document downloads or filing submission (later v2 phases).
- Rate limit: 600 requests per 5 minutes per API key.
- Not legal or accounting advice — cite `company_number` and `fetched_at` when presenting data.
