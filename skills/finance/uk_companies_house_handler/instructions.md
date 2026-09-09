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
| `get_officers` | Directors and secretaries | `company_number` | `active_only` (default **true**), `limit`, `role_hint`, `officer_name` |
| `get_pscs` | Persons with significant control | `company_number` | `active_only` |
| `get_filing_history` | Filings (accounts, returns, etc.) | `company_number` | `category`, `limit` |
| `map_intent` | Suggest an action pipeline from keywords | `intent_keywords` and/or `entities` | `entities.company_query`, `action_params`|
| `run_pipeline` | Run ordered atomic steps; halt on `needs_input`/`error` | `steps` (and `context`, `pipeline` when continuing) | `company_number`, `stop_on` |
| `resolve_and_get_officers` | Resolve + list officers in one call | `query` **or** `company_number` | `role_hint`, `active_only`, `limit`, `officer_name` |
| `resolve_and_get_filings` | Resolve + list filings in one call | `query` **or** `company_number` | `category`, `limit` |

**Parameter hygiene:**
- **Company Number Extraction**: If the user query contains an 8-character UK company number (8 digits or 2 prefix letters + 6 digits, e.g. `00102498`, `SC123456`, `OC123456`, `NI123456`), extract it and pass it directly as `company_number`. When `company_number` is provided, composite actions bypass search and call target retrieval actions (`get_officers` / `get_filing_history`) directly.
- **Search Query**: If no company number is present, pass a **clean** company name in `query` / `entities.company_query` (e.g. `Barclays`, not `Who is the CEO of Barclays?`).
- **Roles & Filters**: Pass conversational role intent via `role_hint` (e.g. `"ceo"`, `"chairman"`), specific officer name via `officer_name`, and filing categories via `category`. Strip trailing punctuation (`?`, `.`) yourself or rely on the skill's light normalization.

## Playbook — disambiguation and multi-step queries

### Example: "Who is the CEO of Barclays?"

1. **Do not** pass the full sentence as `query`. Call `resolve_and_get_officers` with `query: "Barclays"`, `role_hint: "ceo"` (or `run_pipeline` / `map_intent` + pipeline if you prefer).
2. If `status` is **`needs_input`**, present `candidates` (e.g. Barclays Bank PLC vs other Barclays entities) and ask the user to pick.
3. After confirmation, call `get_officers` with the chosen `company_number` (and `role_hint` if still relevant), or resume `run_pipeline` with `company_number` + remaining `steps` / `context`.
4. Answer the role question using UK director terminology when appropriate, then **render the full `officers[]` list** (name, role, appointed date).

### Multi-intent queries and pipeline orchestration

For combined asks (e.g. *"get me 10 filings and ceo of BP"*):

1. **Map Intent:** Call `map_intent` with `intent_keywords` and `entities: {"company_query": ...}` to obtain suggested `steps` and initial `pipeline` metadata.
2. **Mandatory Pipeline State Rule:** Whenever calling `run_pipeline` (initial, intermediate continuation, or resume after disambiguation), you **MUST ALWAYS** include:
   - `steps`: The ordered remaining steps (or `steps` from `map_intent`).
   - `context`: The full `context` dictionary returned by the previous skill result. When resuming after user selection, update `company_number` (and `company_name` if known) in `context` or at top level.
   - `pipeline`: The exact `pipeline` object (`{"completed_steps": N, "total_steps": M}`) returned by the previous skill result.
3. **Handling Disambiguation (`needs_input`):**
   - Present the candidates cleanly to the user.
   - Once the user selects an option, resume `run_pipeline` passing `company_number`, updated `context`, the previous `pipeline` object, and the remaining `steps`.
4. **Handling Intermediate Progress (`partial`):**
   - When `run_pipeline` returns `status: "partial"`, do not stop. Immediately call `run_pipeline` with the returned `steps`, `context`, and `pipeline` until `status` is `ready`.


### Single-intent shortcuts

- Officers only: `resolve_and_get_officers` with `company_number` (if known) or clean `query` + optional `role_hint` / `officer_name`.
- Filings only: `resolve_and_get_filings` with `company_number` (if known) or clean `query` + optional `category`.

## Understanding responses

| Status | Meaning |
| :--- | :--- |
| `ready` | Complete result for standalone/composite actions or completed pipelines — present data clearly. |
| `partial` | Intermediate pipeline progress (used only in `run_pipeline` when intermediate steps have executed and remaining steps are pending). |
| `needs_input` | Ambiguous search or missing company name for pipeline — use `candidates` or `agent_hint`. |
| `error` | Check `error_code` and `message`. Use `agent_hint` for retry guidance (`rate_limited`, `timeout`, `connection_error`). |

Every response includes `fetched_at`, `source`, and usually `context`. Pipeline responses may include `pipeline: {"completed_steps": N, "total_steps": M}`.

Common `error_code` values: `not_found`, `no_results`, `rate_limited`, `timeout`, `connection_error`, `missing_query`, `missing_company_number`.

## Limitations

- Read-only public registry data; no document downloads or filing submission (later v2 phases).
- Rate limit: 600 requests per 5 minutes per API key.
- Not legal or accounting advice — cite `company_number` and `fetched_at` when presenting data.
