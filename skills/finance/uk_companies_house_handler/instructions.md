# UK Companies House Handler — Instructions

You are an agent equipped with the `finance/uk_companies_house_handler` skill. This tool lets you query the UK Companies House registry for company information, officers, ownership, and filing history through structured actions.

## When to use

Use this skill when the user:

- Asks about a UK company (registered in England, Wales, Scotland, or Northern Ireland).
- Wants to know who runs, owns, or controls a UK company.
- Asks about directors, officers, or "the CEO" of a UK company.
- Requests filing history, accounts, or annual returns for a UK company.
- Mentions "Companies House" or refers to a UK company number (8 characters, e.g. 00102498).
- Asks about beneficial owners, PSCs, or persons with significant control.

## UK Terminology

UK statutory company law uses specific terminology:

| User says | UK equivalent | Skill action |
| :--- | :--- | :--- |
| CEO, president, chairman | Director | `get_officers` |
| Owner, shareholder, beneficial owner | Person with Significant Control (PSC) | `get_pscs` |
| Secretary, corporate secretary | Secretary | `get_officers` |
| Annual report, 10-K, financials | Accounts / Confirmation Statement | `get_filing_history` |
| Company, corporation, LLC | Ltd, PLC, LLP | `resolve_company` |

**Important guidelines for terminology:**
- Only mention terminology differences if the user explicitly used non-UK or informal terms (for example, if the user specifically asked for "the CEO", "president", "10-K", or "the owner").
- If the user asked for standard terms (e.g. "officers", "directors", "filings"), present the results directly without redundant or unprompted terminology disclaimers.
- Do NOT insert terminology disclaimers into intermediate disambiguation questions (e.g. when asking the user to choose between matching companies).

## Available actions

| Action | Purpose | Required params | Optional params |
| :--- | :--- | :--- | :--- |
| `resolve_company` | Search by name, get ranked candidates | `query` | `limit` |
| `get_company_profile` | Full profile by company number | `company_number` | |
| `get_officers` | List directors and secretaries | `company_number` | `active_only`, `limit`, `role_hint`, `officer_filter` |
| `get_pscs` | List persons with significant control | `company_number` | `active_only` |
| `get_filing_history` | List filings (accounts, returns, etc.) | `company_number` | `category`, `limit` |
| `map_intent` | Translate intent keywords to action pipeline | `intent_keywords` or `entities` | |
| `run_pipeline` | Execute ordered steps sequentially; halt on needs_input/error | `steps` (or auto-resumes `next_actions`) | `company_number`, `pipeline`, `stop_on` |
| `resolve_and_get_officers` | Composite: resolve company by name and list officers in one step | `query` or `company_number` | `role_hint`, `active_only`, `limit`, `officer_filter` |
| `resolve_and_get_filings` | Composite: resolve company by name and list filings in one step | `query` or `company_number` | `category`, `limit` |

## Workflow — Multi-step queries and Intent Mapping

1. **Multi-intent & Complex Queries (Always Map Intent First)**:
   - When a user asks for multiple pieces of information in a single query (e.g., *"give me the officer name and filings of bp"*, *"who runs and owns Monzo"*, or *"give me profile and PSC of Tesco"*), you **MUST start by calling `map_intent`** with `intent_keywords` (comma-separated, e.g. `"officer, filings"`) and `entities` (e.g. `{"company_query": "bp"}`).
   - `map_intent` returns a clean, ordered `suggested_pipeline` and UK terminology translations. Execute this pipeline directly using `run_pipeline`.
2. **Single-intent Queries (Direct Composite)**:
   - When the user asks for a single category of information for a named company (e.g., *"Who is the CEO of BP?"* or *"Show me filings for Tesco"*), invoke the composite action directly (`resolve_and_get_officers` or `resolve_and_get_filings`). When querying specific roles like CEO, CFO, or Chairman, pass `role_hint: "ceo"` (or the requested role) so the skill provides tailored role translation notes.
3. **Pipeline Construction Rules**:
   - Steps in `run_pipeline.steps` MUST be **atomic actions** (`resolve_company`, `get_company_profile`, `get_officers`, `get_pscs`, `get_filing_history`). Never nest composite actions inside `run_pipeline`.
4. **Handling Disambiguation (`needs_input`)**:
   - If any step returns `needs_input` (such as ambiguous company search hits), present the `candidates` cleanly to the user and pause. Do not add premature terminology notes or disclaimers at this stage.
   - Once the user confirms the company (e.g. "BP P.L.C." / `00102498`), you can either call the target action directly (e.g. `get_officers(company_number='00102498')`), or call `run_pipeline` with the remaining steps, passing `company_number` and `pipeline` state.
5. **State Tracking (Context)**:
   - Every response includes a `context` object. Pass this `context` object back on subsequent tool calls to preserve session state (`company_number`, `company_name`, `role_hint`).
6. **Synthesizing Responses**:
   - When the tool returns records (`officers`, `filings`, `pscs`), **always render the formatted list** for the user (in clear bullet points or markdown tables with name, officer role, and appointed date).
   - If the user asked a role-specific question (e.g. *"Who is the CEO of BP?"*), first directly answer the question identifying the primary executive / director and explaining the UK statutory terminology note, and then **list the active directors and secretaries** returned by the tool.
   - When `run_pipeline` completes, its response envelope merges data from all executed steps (e.g., BOTH `officers` and `filings`). Always synthesize a complete answer that includes all requested information and renders all returned data sections.

## Understanding responses

Every response includes a `status` field:

- **`ready`**: The data was fetched completely. Present it clearly to the user.
- **`partial`**: The operation succeeded and returned a preview (e.g. the first 10 active officers or first 10 filings out of a larger total on record).
  - **Always display the formatted list** of returned items (bullet points with name, role, and appointment date for officers; date, category, and description for filings).
  - State the total count clearly above or below the list (e.g. *"Showing 10 active officers out of 11 active on file (74 total on record):"* followed by the 10 listed officers).
  - Never mention a preview count sentence without actually presenting the returned records.
- **`needs_input`**: Multiple matches or missing information. Present the `candidates` to the user and ask for clarification. Use the `agent_hint` for guidance.
- **`error`**: Something went wrong. Check `error_code` and `message`. Common errors:
  - `not_found`: Company number does not exist.
  - `rate_limited`: Too many requests; wait and retry.
  - `missing_company_number`: You need to resolve a company first.
  - `missing_steps` / `invalid_step`: Pipeline step definition error.

Every response includes `fetched_at` (UTC timestamp), `source`, and a `context` block — always cite the timestamp and source when presenting data. Multi-step operations (`run_pipeline`, composite actions) also include a `pipeline` object (e.g. `{"completed_steps": 1, "total_steps": 2}`) representing progress.

## Limitations

- **Scope**: Search, profile, officers, PSC, filing history, pipelines, and composites are supported. Charges, insolvency registers, and document downloads are planned for later v2 phases.
- **No filing submission**: This skill is read-only; it cannot submit documents to Companies House.
- **Rate limits**: Companies House API allows 600 requests per 5 minutes per key.
- **Public data only**: Only publicly available data is returned. No confidential or protected information.

## Safety

- This skill provides company information. **It is not legal or accounting advice.**
- Always include this disclaimer when presenting company data to users.
- Always cite the `company_number` and `fetched_at` timestamp so the user knows the data source and currency.
