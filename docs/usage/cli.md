# CLI Reference

Skillware ships a `skillware` command-line tool for discovering and inspecting
skills installed locally. It mirrors the same path resolution order used by
`SkillLoader.load_skill()`, so the skills listed are exactly the ones your
agent can load.

## Installation

The CLI depends on `rich` for terminal output. Install it with the `cli` extra:

    pip install "skillware[cli]"

## Commands

### skillware list

Print a table of all locally available skills.

    skillware list

Sample output:

    ID                           VERSION  CATEGORY    ISSUER      DESCRIPTION                        REQUIREMENTS
    compliance/pii_masker        0.1.0    compliance  rosspeili   High-precision PII detection...    requests
    finance/wallet_screening     1.0.0    finance     rosspeili   Crypto wallet screening tool...    requests
    office/pdf_form_filler       0.1.0    office      rosspeili   Fills PDF forms from natural...    pymupdf, anthropic

#### Flags

| Flag | Description |
| :--- | :--- |
| `--category <name>` | Show only skills in the given category. Discovered at runtime, never hardcoded. |
| `--issuer <handle>` | Show only skills by a given GitHub handle or issuer name. |
| `--skills-root <path>` | Override the skills directory for this command only. |

#### Examples

    # Filter by category
    skillware list --category compliance

    # Filter by issuer
    skillware list --issuer rosspeili

    # Use a custom skills directory
    skillware list --skills-root /path/to/my/skills

## Path resolution

`skillware list` searches for skills in the same order as `SkillLoader`:

1. Roots listed in `SKILLWARE_SKILL_PATH` (OS path separator between multiple entries)
2. A `skills/` directory under the current working directory and its parents
3. Bundled skills installed with the `skillware` package

To point the CLI at a persistent custom root, set the environment variable:

    export SKILLWARE_SKILL_PATH=/path/to/my/skills
    skillware list

Only skills with both `manifest.yaml` and `skill.py` present are shown —
the same condition `SkillLoader` requires to load a skill successfully.

