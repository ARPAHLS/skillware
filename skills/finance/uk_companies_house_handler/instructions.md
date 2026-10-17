# UK Companies House Handler

You are using the `finance/uk_companies_house_handler` skill.

This skill wraps the UK Companies House REST API (`api.company-information.service.gov.uk`) and Document API (`document-api.company-information.service.gov.uk`) with deterministic actions. It returns structured JSON envelopes (`ready`, `partial`, `needs_input`, `error`) — it does not parse conversational user text.

**You are the host agent.** You infer intent, choose actions, pass clean parameters (`query`, `company_number`, `role_hint`, `category`), handle disambiguation with the user, interpret every envelope, and **always** reply in plain language. The skill never speaks to the user directly.

**Never end your turn without a user-facing message.** Even when the registry returns no rows, an error, or only `needs_input`, explain what you attempted, what the JSON means, and what you need next (if anything). One-word answers (e.g. `"No."`) are not acceptable — summarize the lookup scope and result.

`data/terminology_map.yaml` is a **reference lexicon** for UK/US/finance term equivalents and keyword hints; it is not a substitute for your reasoning. Prefer explicit parameters over relying on keyword routing alone.

## When to use

Use this skill when the user:

- Asks about a UK company (England, Wales, Scotland, or Northern Ireland).
- Wants directors, officers, secretaries, PSCs, or filing history for a UK entity.
- Mentions Companies House or a UK company number (8 characters, e.g. `00445790`).
- Needs multi-step registry lookups that benefit from `run_pipeline` or composite actions.
- Wants to discover, pick, and download statutory filings (accounts, incorporation docs) as bounded base64 payloads.

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
| `get_officers` | Directors and secretaries with deterministic filtering | `company_number` | `active_only` (default **true**), `limit`, `start_index`, `role_hint`, `officer_name`, `officer_role` |
| `get_pscs` | Persons with significant control | `company_number` | `active_only` |
| `get_filing_history` | Filings with deterministic sorting and helpers | `company_number` | `category`, `limit`, `start_index`, `latest_only`, `latest_per_category` |
| `list_downloadable_documents` | Pick list of filings that have Document API metadata links | `company_number` (or context) | `category`, `limit` (max 25), `latest_only`, `latest_per_category` |
| `get_document_metadata` | Inspect Document API metadata (MIME types, size, pages) | `transaction_id` **or** `metadata_url` | |
| `fetch_document` | Stream document bytes as bounded base64 (no disk) | `transaction_id` **or** `metadata_url` | `content_type` (default PDF), `include_content` (default true), `max_bytes` (default 5 MB, hard ceiling 10 MB) |
| `run_pipeline` | Run ordered atomic steps; halt on `needs_input`/`error` | `steps` (and `context`, `pipeline` when continuing) | `company_number`, `stop_on` |
| `resolve_and_get_officers` | Resolve + list officers in one call | `query` **or** `company_number` | `role_hint`, `active_only`, `limit`, `officer_name`, `officer_role` |
| `resolve_and_get_filings` | Resolve + list filings in one call | `query` **or** `company_number` | `category`, `limit`, `latest_only`, `latest_per_category` |
| `resolve_company_officer` | Resolve + filter officers by role and/or name in one call | `query` **or** `company_number` | `officer_name`, `officer_role`, `role_hint`, `active_only`, `limit` |

**Parameter hygiene:**
- **Company Number Extraction**: If the user query contains an 8-character UK company number (8 digits or 2 prefix letters + 6 digits, e.g. `00102498`, `SC123456`, `OC123456`, `NI123456`), extract it and pass it directly as `company_number`. When `company_number` is provided, composite actions bypass search and call target retrieval actions (`get_officers` / `get_filing_history`) directly.
- **Search Query**: If no company number is present, pass a **clean** company name in `query` (e.g. `Barclays`, not `Who is the CEO of Barclays?`).
- **Pipeline Step Construction**: For multi-intent queries, construct the `steps` array directly for `run_pipeline`. Put `resolve_company` first and use `company_number: "<from_resolve>"` in subsequent retrieval steps.
- **Roles & Filters**: Pass conversational role intent via `role_hint` (e.g. `"ceo"`, `"chairman"`), canonical category or exact statutory role via `officer_role` (`"director"`, `"secretary"`, `"corporate"`, or exact Companies House role like `"cic-manager"`), specific officer name or surname via `officer_name` (e.g. `"John McFarlane"`, `"McFarlane"`, or `"John"`; the skill checks all parts against registry format), and filing categories via `category`.
- **Filing Helpers**: Use `latest_only: true` when the user asks for the single newest filing (e.g. "latest accounts" or "newest filing") or `latest_per_category: true` for the latest filing per distinct category (e.g. "newest filing per category").
- **Active vs. Resigned Officers**: Pass `active_only: false` when the user asks for historical, former, or resigned officers.
- Strip trailing punctuation (`?`, `.`) yourself or rely on the skill's light normalization.

## Playbook — disambiguation and multi-step queries

### Example: "Who is the CEO of Barclays?"

1. **Do not** pass the full sentence as `query`. Call `resolve_company_officer` (or `resolve_and_get_officers`) with `query: "Barclays"`, `officer_role: "director"`, `role_hint: "ceo"` (or `run_pipeline` with direct steps if you prefer).
2. If `status` is **`needs_input`**, present `candidates` (e.g. Barclays Bank PLC vs other Barclays entities) and ask the user to pick.
3. After confirmation, call `get_officers` with the chosen `company_number` (and `officer_role` / `role_hint` if still relevant), or resume `run_pipeline` with `company_number` + remaining `steps` / `context`.
4. Answer the role question using UK director terminology when appropriate, then **render the full `officers[]` list** (name, role, appointed date).

### Multi-intent queries (run_pipeline)

When the user asks for more than one registry aspect (e.g. *"get me the officers and newest filing from Tesco"*, *"all filings and John from Barclays"*, or *"who is the CEO and what are the accounts for BP"*):

1. **Construct the ordered `steps` directly**:
   - **Step 1 — Resolve**: Always start with `{"action": "resolve_company", "params": {"query": "<company_name>"}}` (unless the 8-character `company_number` is already known).
   - **Subsequent Steps — Retrieve**: Add the target retrieval actions (`get_officers`, `get_filing_history`, `get_pscs`, `get_company_profile`) with `company_number: "<from_resolve>"` and any specific filters (`officer_name`, `officer_role`, `role_hint`, `category`, `latest_only`, `latest_per_category`).

   **Common step templates:**
   - *Officers + Filings*:
     ```json
     [
       {"action": "resolve_company", "params": {"query": "Tesco"}},
       {"action": "get_officers", "params": {"company_number": "<from_resolve>"}},
       {"action": "get_filing_history", "params": {"company_number": "<from_resolve>"}}
     ]
     ```
   - *Officers + Newest Filing per Category*:
     ```json
     [
       {"action": "resolve_company", "params": {"query": "Tesco"}},
       {"action": "get_officers", "params": {"company_number": "<from_resolve>"}},
       {"action": "get_filing_history", "params": {"company_number": "<from_resolve>", "latest_per_category": true}}
     ]
     ```
   - *Filings + Specific Officer by Name*:
     ```json
     [
       {"action": "resolve_company", "params": {"query": "Barclays"}},
       {"action": "get_filing_history", "params": {"company_number": "<from_resolve>"}},
       {"action": "get_officers", "params": {"company_number": "<from_resolve>", "officer_name": "John"}}
     ]
     ```
   - *CEO + Recent Accounts*:
     ```json
     [
       {"action": "resolve_company", "params": {"query": "BP"}},
       {"action": "get_officers", "params": {"company_number": "<from_resolve>", "officer_role": "director", "role_hint": "ceo"}},
       {"action": "get_filing_history", "params": {"company_number": "<from_resolve>", "category": "accounts", "latest_only": true}}
     ]
     ```

2. **Execute via `run_pipeline`**:
   Call `run_pipeline` passing the constructed `steps` array.

3. **Mandatory Pipeline State Rule:** Whenever calling `run_pipeline` (initial, intermediate continuation, or resume after disambiguation), you **MUST ALWAYS** include:
   - `steps`: The ordered remaining steps.
   - `context`: The full `context` dictionary returned by the previous skill result. When resuming after user selection, update `company_number` (and `company_name` if known) in `context` or at top level.
   - `pipeline`: The exact `pipeline` object (`{"completed_steps": N, "total_steps": M}`) returned by the previous skill result.

4. **Handling Disambiguation (`needs_input`):**
   - Present the candidates cleanly to the user.
   - Once the user selects an option, resume `run_pipeline` passing `company_number`, updated `context`, the previous `pipeline` object, and the remaining `steps`.

5. **Handling Intermediate Progress (`partial`):**
   - When `run_pipeline` returns `status: "partial"`, do not stop. Immediately call `run_pipeline` with the returned `steps`, `context`, and `pipeline` until `status` is `ready`.

### Single-intent shortcuts

- Officers only: `resolve_company_officer` or `resolve_and_get_officers` with `company_number` (if known) or clean `query` + optional `officer_role` / `officer_name` / `role_hint`.
- Filings only: `resolve_and_get_filings` with `company_number` (if known) or clean `query` + optional `category` / `latest_only`.


## Playbook — Document Mode (discover → pick → download)

Use when the user asks to download accounts, confirmation statements, incorporation documents, or other filings.

1. **Discover** — Call `list_downloadable_documents` with `company_number` (or after `resolve_company`) and optional `category` / `latest_only`.
2. **Pick** — Present `documents[]` (`transaction_id`, `date`, `description`, `category`). Optionally call `get_document_metadata` to confirm MIME types and size before download.
3. **Download** — Call `fetch_document` with the chosen `transaction_id` or `metadata_url`. Carry `context` so `document_candidates` and `selected_transaction_id` stay available.
4. **Relay** — Return `content_base64` to the user. Never write PDFs to disk inside the skill. On `document_too_large`, raise `max_bytes` (up to 10 MB) or use `include_content: false`.
5. **Rate limits** — On `rate_limited`, read `retry_after` / `agent_hint` and wait before retrying. The skill does not sleep.

Pipeline example:

```json
{
  "action": "run_pipeline",
  "steps": [
    {"action": "resolve_company", "params": {"query": "BP"}},
    {"action": "list_downloadable_documents", "params": {"company_number": "<from_resolve>", "category": "accounts", "latest_only": true}}
  ]
}
```

Then call `fetch_document` with the selected `transaction_id` from the list result.

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

Common `error_code` values: `not_found`, `no_results`, `rate_limited`, `timeout`, `connection_error`, `missing_query`, `missing_company_number`, `missing_document_target`, `document_too_large`, `invalid_metadata_url`, `unsupported_content_type`.

## Empty or missing registry data

A **`ready` response with empty arrays** (`officers: []`, `filings: []`, `pscs: []`) is valid — it means the API call succeeded but nothing matched your filters or this entity has no public rows in that category. Do **not** treat it as a failure and do **not** stay silent.

In your own words:

- State which company (`company_number`, `company_name`) you queried and which action ran.
- Say that Companies House returned no matching public records for that request.
- Offer helpful next steps: confirm the exact legal entity, try a different company number, widen filters (`active_only: false`, higher `limit`), or ask what the user is trying to learn.

The same applies to `error` with `no_results` / `not_found`, and to officer name checks where no match appears — explain how many officers you scanned and that the name was not found.

Use `agent_hint` when present; it summarizes machine-oriented guidance — translate it for the user, do not paste it verbatim unless helpful.

## Limitations

- Read-only public registry data; supports Document API downloads as in-memory base64. No filing submission or local disk persistence of documents.
- Rate limit: [600 requests per 5 minutes per API key](https://developer.company-information.service.gov.uk/documentation/rate-limiting) across Public Data and Document API hosts. On `rate_limited`, tell the user the Retry-After hint and retry later — the skill does not sleep.
- Document payloads are capped (`max_bytes`, default 5 MB, hard ceiling 10 MB). Oversized files return `document_too_large`.
- Not legal or accounting advice — cite `company_number` and `fetched_at` when presenting data.
