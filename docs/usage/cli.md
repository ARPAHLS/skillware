# CLI Reference

Skillware ships a `skillware` command-line tool for discovering and inspecting
skills installed locally. It mirrors the same path resolution order used by
`SkillLoader.load_skill()`, so the skills listed are exactly the ones your
agent can load.

## Installation

The CLI depends on `rich` for terminal output. Install it with the `cli` extra:

    pip install "skillware[cli]"

## Interactive menu

Running `skillware` with no arguments launches an ASCII splash screen and an
interactive numbered menu:

    skillware

The splash displays the current version and links to the project site and
repository. The menu accepts both number input (`1`) and command name (`list`).
After each command completes, the menu re-prints automatically. Press `q` or
`Ctrl+C` to exit.

Available commands:

| Input | Command | Status |
| :--- | :--- | :--- |
| `1` / `list` | List all locally installed skills | Available |
| `2` / `paths` | Show and repair skill directory resolution paths | Coming in #81 |
| `3` / `test` | Run test_skill.py for one or all skills | Coming in #83 |
| `4` / `help` | Print usage information | Available |

## Commands

### skillware list

Print a table of all locally available skills.

    skillware list

Sample output:

    ID                           VERSION  CATEGORY    ISSUER      DESCRIPTION                                       REQUIREMENTS
    compliance/pii_masker        0.1.0    compliance  rosspeili   Detects and redacts PII locally using Ollama.     requests
    finance/wallet_screening     1.0.0    finance     rosspeili   Screens Ethereum wallets against OFAC sanctions.  requests
    office/pdf_form_filler       0.1.0    office      rosspeili   Fills PDF forms from natural language.            pymupdf, anthropic

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

## Color theme

The CLI uses a pastel color palette consistent with the project's visual identity:

| Element | Color | Hex |
| :--- | :--- | :--- |
| Table headers and borders | Lavender | `#C7CEEA` |
| Category column | Peach | `#FFDAC1` |
| Skill ID column | Mint | `#B5EAD7` |
| Splash screen | Lavender | `#C7CEEA` |
| Interactive menu | Peach | `#FFDAC1` |

## short_description field

Skill manifests can include a `short_description` field (max 80 chars) for
a concise one-line summary shown in `skillware list`:

    short_description: "Screens Ethereum wallets against OFAC sanctions and mixer lists."

If `short_description` is absent, the CLI falls back to the first sentence
of `description`, truncated to 80 characters.

