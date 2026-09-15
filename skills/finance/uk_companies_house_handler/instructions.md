# UK Companies House Handler

You are using the `finance/uk_companies_house_handler` skill.

This skill wraps the UK Companies House REST API (`api.company-information.service.gov.uk`) with deterministic actions. It returns structured JSON envelopes (`ready`, `partial`, `needs_input`, `error`) — it does not parse conversational user text.

**You are the host agent.** You infer intent, choose actions, pass clean parameters (`query`, `company_number`, `role_hint`, `category`), handle disambiguation with the user, interpret every envelope, and **always** reply in plain language. The skill never speaks to the user directly.

**Never end your turn without a user-facing message.** Even when the registry returns no rows, an error, or only `needs_input`, explain what you attempted, what the JSON means, and what you need next (if anything). One-word answers (e.g. `"No."`) are not acceptable — summarize the lookup scope and result.

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

## Conversation workflow

Follow this loop for every user question:

1. **Understand** — What registry facts are needed (company, officers, PSCs, filings, yes/no officer check)?
2. **Parameterize** — Do you have a `company_number` or clean `query`? If not, ask the user before calling the skill.
3. **Call the skill** — One action at a time (or `run_pipeline` / composites when appropriate) with clean params.
4. **Interpret the envelope** — Read `status`, record arrays, counts, `agent_hint`, and `context`.
5. **Reply or clarify** — Present findings in simple language, or ask a focused follow-up (pick a candidate, confirm company number, refine officer name).

After tool results return `ready` or `partial`, **stop calling tools** unless you still lack data to answer the question. Write the user-facing summary first.

## Understanding responses

| Status | Meaning | Your reply |
| :--- | :--- | :--- |
| `ready` | Complete result for standalone/composite actions or completed pipelines. | Present data clearly; cite `company_number` / `company_name` and `fetched_at` when useful. List all returned records and state `total_results` / `active_count` when truncated. |
| `partial` | In-flight `run_pipeline` only — intermediate step finished, remaining steps pending. | Summarize completed step output; explain remaining pipeline work or ask for disambiguation if halted. |
| `needs_input` | Ambiguous search or missing company name for pipeline. | Show `candidates` or paraphrase `agent_hint`; ask the user to choose or supply a company number. |
| `error` | Request failed. | Explain `message` / `error_code`; suggest retry or different params (`rate_limited`, `timeout`, etc.). |

Every response includes `fetched_at`, `source`, and usually `context`. Pipeline responses may include `pipeline: {"completed_steps": N, "total_steps": M}`.

Common `error_code` values: `not_found`, `no_results`, `rate_limited`, `timeout`, `connection_error`, `missing_query`, `missing_company_number`.

## Empty or missing registry data

A **`ready` response with empty arrays** (`officers: []`, `filings: []`, `pscs: []`) is valid — it means the API call succeeded but nothing matched your filters or this entity has no public rows in that category. Do **not** treat it as a failure and do **not** stay silent.

In your own words:

- State which company (`company_number`, `company_name`) you queried and which action ran.
- Say that Companies House returned no matching public records for that request.
- Offer helpful next steps: confirm the exact legal entity, try a different company number, widen filters (`active_only: false`, higher `limit`), or ask what the user is trying to learn.

The same applies to `error` with `no_results` / `not_found`, and to officer name checks where no match appears — explain how many officers you scanned and that the name was not found.

Use `agent_hint` when present; it summarizes machine-oriented guidance — translate it for the user, do not paste it verbatim unless helpful.

## Limitations

- Read-only public registry data; no document downloads or filing submission (later v2 phases).
- Rate limit: [600 requests per 5 minutes per API key](https://developer.company-information.service.gov.uk/documentation/rate-limiting). On `rate_limited`, tell the user to wait and retry.
- Not legal or accounting advice — cite `company_number` and `fetched_at` when presenting data.
