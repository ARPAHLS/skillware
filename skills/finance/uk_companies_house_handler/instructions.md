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

## UK Terminology — Critical

UK companies do **not** use the term "CEO" in a legal sense. When a user says "CEO", "president", or "chairman", you should look up **directors** via the `get_officers` action. The skill includes a terminology map:

| User says | UK equivalent | Skill action |
| :--- | :--- | :--- |
| CEO, president, chairman | Director | `get_officers` |
| Owner, shareholder, beneficial owner | Person with Significant Control (PSC) | `get_pscs` |
| Secretary, corporate secretary | Secretary | `get_officers` |
| Annual report, 10-K, financials | Accounts / Confirmation Statement | `get_filing_history` |
| Company, corporation, LLC | Ltd, PLC, LLP | `resolve_company` |

Always inform the user about these terminology differences when presenting results.

## Available actions

| Action | Purpose | Required params |
| :--- | :--- | :--- |
| `resolve_company` | Search by name, get ranked candidates | `query` |
| `get_company_profile` | Full profile by company number | `company_number` |
| `get_officers` | List directors and secretaries | `company_number` |
| `get_pscs` | List persons with significant control | `company_number` |
| `get_filing_history` | List filings (accounts, returns, etc.) | `company_number` |
| `map_intent` | Translate intent keywords to action pipeline | `intent_keywords` or `entities` |

## Workflow — Always map intent first

1. **Always map intent first.** For every new user request, you MUST start by calling the `map_intent` action with the user's `intent_keywords` (as a comma-separated string) and `entities` (if applicable).
2. Read the `suggested_pipeline` returned by the `map_intent` action.
3. Follow the actions exactly as ordered in the `suggested_pipeline`.
4. If a step (like `resolve_company`) returns a status of `needs_input`, present the candidates to the user and wait for their choice before proceeding.
5. Once you have a confirmed `company_number`, continue with the remaining specific actions (`get_officers`, `get_pscs`, etc.) in your pipeline.

## Understanding responses

Every response includes a `status` field:

- **`ready`**: The data was fetched successfully. Present it to the user.
- **`needs_input`**: Multiple matches or missing information. Present the `candidates` to the user and ask for clarification. Use the `agent_hint` for guidance.
- **`error`**: Something went wrong. Check `error_code` and `message`. Common errors:
  - `not_found`: Company number does not exist.
  - `rate_limited`: Too many requests; wait and retry.
  - `missing_company_number`: You need to resolve a company first.

Every response includes `fetched_at` (UTC timestamp) and `source` — always cite these when presenting data.

## Limitations

- **v1 scope only**: Search, profile, officers, PSC, and filing history. Charges, insolvency registers, and document downloads are not yet supported.
- **No filing submission**: This skill is read-only; it cannot submit documents to Companies House.
- **Rate limits**: Companies House API allows 600 requests per 5 minutes per key.
- **Public data only**: Only publicly available data is returned. No confidential or protected information.

## Safety

- This skill provides company information. **It is not legal or accounting advice.**
- Always include this disclaimer when presenting company data to users.
- Always cite the `company_number` and `fetched_at` timestamp so the user knows the data source and currency.
