# Glossary

Canonical Skillware terms. Prefer the **primary** column in new docs. Synonyms are fine once per page for readability; link here on first use.

Skill file roles follow [Skill anatomy](introduction.md#skill-anatomy) ([#326](https://github.com/ARPAHLS/skillware/issues/326)). Do not use retired Mind / Body / Conscience labels.

Inclusive language: [inclusive-language.md](contributing/inclusive-language.md). Issue: [#252](https://github.com/ARPAHLS/skillware/issues/252).

## People and runtimes

| Primary | Means | Do not use for this | Keep when |
| :--- | :--- | :--- | :--- |
| **Operator** | Person who installs Skillware, sets credentials, runs the CLI, and owns fork / commit / PR | admin, generic “user” | — |
| **Contributor** | Person or supervised agent opening PRs on this repository | operator (unless they also run the host) | — |
| **Supervised agent** | Cursor, Copilot, or similar working **on this repo** under an operator | bot, AI contributor, host agent | “human operator” when contrasting with the agent |
| **Host agent** | LLM + tool loop that **loads** skills | contributor, operator, calling agent | — |
| **End user** | Person the host agent is serving (for example “ask the user to confirm send”) | operator | Skill **Directive** copy; templates |

**`user` is not banned.** It stays for LLM `role: "user"`, Keep a Changelog **user-visible**, OS **user-level config** (`~/.config`), and **end user** in Directives.

Do not global-replace `user` → `operator`.

## Skill artifacts

| Primary | Means | Avoid |
| :--- | :--- | :--- |
| **Skill ID** | Registry string `category/name` (folder path, `manifest.name`, CLI `ID`) | “name” alone |
| **Skill directory** | Folder `skills/<category>/<name>/` | “the skill” when the folder vs class is ambiguous |
| **Skill bundle** | That directory on disk, **or** the dict returned by `SkillLoader.load_skill()` (`bundle["class"]`, `bundle["instructions"]`, …) | “package” (conflicts with the PyPI **package** `skillware`) |
| **PyPI package** | Installable `skillware` distribution | calling a registry skill a package |

## Skill anatomy (roles)

| Role | File | Answers |
| :--- | :--- | :--- |
| **Contract** | `manifest.yaml` | Typed I/O, constitution, issuer, requirements |
| **Effect** | `skill.py` | What runs in `execute()` |
| **Directive** | `instructions.md` | When and how the **host agent** should call the skill (skill context, not host persona) |
| **Assurance** | `test_skill.py` | Offline bundle tests |
| **Presentation** | `card.json` | Catalog / UI metadata |
| **Corpus** | `kb/`, `data/`, … | Bundled knowledge Effect reads |
| **Reference** | `schemas/`, maps | Machine-readable adjuncts to Contract |
| **Interface** | `SkillLoader` adapters | Host API tool schemas |

Retired: **Mind**, **Body**, **Conscience** as role names. Filenames did not change.

## Deprecated synonyms

| Instead of | Write |
| :--- | :--- |
| calling agent (LLM loading skills) | **host agent** |
| Skill Package Standard | **Skill bundle standard** ([CONTRIBUTING](../CONTRIBUTING.md#skill-bundle-standard)) |
| user (person running Skillware) | **operator** |
| dummy (placeholder data) | mock, stub, **placeholder**, sample |
| master a domain | cover / use a skill in a domain |

## Operator configuration

| Primary | Means | Avoid |
| :--- | :--- | :--- |
| **EVM operator config** | Writable `evm.yaml` plus `skillware.core.evm_config` merge helpers for chain IDs, `rpc_env` names, and token registry metadata shared by defi skills — see [EVM operator config](usage/evm_operator_config.md) | putting RPC URLs or private keys in YAML |
| **Orchestration chain** | Named multi-skill pipeline under top-level `chains:` in `.skillware.yaml` (`skillware chain run`) | EVM blockchain network |
| **EVM chain (network)** | JSON-RPC network entry (ethereum, base, …) under `evm:` / `evm.yaml` | orchestration **chain** |
