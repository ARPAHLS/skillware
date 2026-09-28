# Inclusive language

Skillware docs and comments should be precise and neutral. This is a **wording** policy. It does not rename public APIs, CLI commands, registry skill IDs, or third-party tools.

Canonical terms: [glossary.md](../glossary.md). Reference: [Khronos Inclusive Language](https://www.khronos.org/about/inclusive-language).

## Prefer

| Avoid | Prefer | Notes |
| :--- | :--- | :--- |
| dummy (placeholder) | mock, stub, placeholder, sample | Test fixtures and comments |
| master (dominance / “master a domain”) | primary, main, cover / use | Git `main` is already the default branch name |
| sanity check | confidence check, smoke check, quick check | |
| guys / default he | they, contributors, operators | |
| whitelist / blacklist (our prose) | allow-list / block-list | Do **not** rename `allowlist_*.json` data files or quoted upstream names |
| man-in-the-middle | on-path attacker | If it appears in security docs |

## Exceptions (do not churn)

- Tool and formatter names (`black`, …)
- Skill-domain wording we do not control (quoted standards, clinical KB sources)
- Historical [CHANGELOG.md](../../CHANGELOG.md) bullets
- LLM protocol fields (`role: "user"`)
- **End user** in Directives (`instructions.md`) — that is the person talking to the host agent, not the operator
- Keep a Changelog **user-visible**
- OS **user-level** config paths
