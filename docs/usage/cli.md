# CLI Reference

Skillware ships a `skillware` command-line tool for discovering and inspecting
skills installed locally. It mirrors the same path resolution order used by
`SkillLoader.load_skill()`, so the skills listed are exactly the ones your
agent can load.

## Splash

The interactive CLI opens with a gradient-styled **SKILLWARE** ASCII logo, a
version tagline, and footer links. The block art (from `skillware/cli.py`):

```text
  ███████╗██╗  ██╗██╗██╗     ██╗     ██╗    ██╗ █████╗ ██████╗ ███████╗
  ██╔════╝██║ ██╔╝██║██║     ██║     ██║    ██║██╔══██╗██╔══██╗██╔════╝
  ███████╗█████╔╝ ██║██║     ██║     ██║ █╗ ██║███████║██████╔╝█████╗
  ╚════██║██╔═██╗ ██║██║     ██║     ██║███╗██║██╔══██║██╔══██╗██╔══╝
  ███████║██║  ██╗██║███████╗███████╗╚███╔███╔╝██║  ██║██║  ██║███████╗
  ╚══════╝╚═╝  ╚═╝╚═╝╚══════╝╚══════╝ ╚══╝╚══╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝
```

Tagline: `Skillware v{version} — Skill Management Framework`. Gradient colors
are listed under [Color theme](#color-theme). See [Interactive menu](#interactive-menu)
for a terminal screenshot.

## Installation

Install Skillware — `rich` is included as a core dependency:

    pip install skillware

## Running the CLI

After installation, the `skillware` command is available directly:

    skillware
    skillware list
    skillware test
    skillware examples
    skillware --version

If `skillware` is not recognized, Python's `Scripts` directory may not be on
your PATH.

**Unix** — verify with:

    which skillware

**Windows** — verify with:

    where skillware

If the command is not found, use the module fallback (works on any OS as long
as Python is installed):

    python -m skillware
    python -m skillware list
    python -m skillware test finance/wallet_screening
    python -m skillware list --category compliance
    python -m skillware --help

**Windows PATH fix** — add both `Python3x\` and `Python3x\Scripts\` to your
system PATH, or use the `py` launcher:

    py -3 -m pip install skillware
    py -3 -m skillware list

## Version advisory

On CLI startup, Skillware checks the installed package version **once per process**.
If you are on an **unsupported** release (below `0.3.0`, for example `0.2.9`), a single
dim message is printed to stderr suggesting an upgrade to `>= 0.3.5`. Installs in the
`0.3.0`–`0.3.4` band stay silent (no security backports, but no startup spam). Current
supported installs (`0.3.5` and above) stay silent.

Library use (`import skillware`, `SkillLoader`) never prints this message.

To disable the check in CI or automation:

    export SKILLWARE_NO_VERSION_CHECK=1

See [SECURITY.md](../../SECURITY.md) for the full supported-version policy.

## Interactive menu

Running `skillware` with no arguments launches an ASCII splash screen and an
interactive numbered menu:

    skillware

![Skillware interactive menu — splash and skillware list output](../../assets/skillware%20list.png)

The splash shows a gradient-styled **SKILLWARE** ASCII logo, a tagline in the
form `Skillware v{version} — Skill Management Framework` (same version string
as `skillware --version`), and dim footer links to the project site and
repository. The menu accepts both number input (`1`) and command name (`list`).
After each command completes, the menu re-prints automatically. Press `q` or
`Ctrl+C` to exit.

Available commands:

| Input | Command | Status |
| :--- | :--- | :--- |
| `1` / `list` | List all locally installed skills | Available |
| `2` / `examples` | Browse runnable example scripts (index from `examples/README.md`, or from GitHub when no local copy exists) | Available |
| `3` / `test` | Run bundle tests (`test_skill.py`) for one or all skills | Available |
| `4` / `paths` | Show skill root resolution order, tiers, and shadowing | Available |
| `5` / `help` | Print rich-formatted help with commands, flags, and examples | Available |

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
| `--examples` | Add an **EXAMPLES** column with the count of indexed scripts per skill (`-` when none). Works with `--category` and `--issuer`. |

#### Examples

    # Filter by category
    skillware list --category compliance

    # Show example script counts per skill
    skillware list --examples
    skillware list --examples --category dev_tools

    # Filter by issuer
    skillware list --issuer rosspeili

    # Use a custom skills directory
    skillware list --skills-root /path/to/my/skills

### skillware examples

List runnable scripts indexed in `examples/README.md` (source of truth — the CLI does not scan `examples/*.py` directly). When no local `examples/README.md` is found (typical for `pip install`), the CLI loads the index from GitHub `main`.

    skillware examples
    skillware examples compliance/tos_evaluator
    skillware examples finance/wallet_screening

#### Arguments

| Input | Description |
| :--- | :--- |
| *(no args)* | All indexed scripts (script-first view) |
| `<category>/<skill_name>` | Scripts linked to that skill ID only |

Columns: Script, Skill ID(s), Provider, Required extra, and a **GITHUB** link to the script on `main` (for example `https://github.com/ARPAHLS/skillware/blob/main/examples/gemini_tos_evaluator.py`). Environment variables and longer notes stay in `examples/README.md`; a one-line pointer is printed below the table.

Unknown skill IDs exit with a helpful message and non-zero status.

In the interactive menu, choose **`2` / `examples`**, optionally enter a skill ID, then browse the same table with GitHub links.

### skillware test

Run skill **bundle tests** (`test_skill.py`) via pytest. Uses the same skill roots as `skillware list` (`SKILLWARE_SKILL_PATH`, `--skills-root`, cwd `skills/`, bundled registry).

Requires pytest (`pip install -e ".[dev]"` or `pip install -e ".[dev,all]"`).

    skillware test
    skillware test finance/wallet_screening
    skillware test --category compliance
    skillware test --verbose
    skillware test office/pdf_form_filler --no-header

#### Arguments and flags

| Input | Description |
| :--- | :--- |
| *(no args)* | Run bundle tests under all resolved skill roots |
| `<category>/<skill_name>` | Run one skill's `test_skill.py` |
| `--category <name>` | Run all bundle tests in a category directory |
| `--skills-root <path>` | Override the skills directory for this command |
| `-v` / `--verbose` | Pass `-v` to pytest |
| `--no-header` | Pass `--no-header` to pytest |

Exit code matches pytest (non-zero on failures or missing test paths).

### skillware paths

Show where Skillware looks for skills — same order as `SkillLoader.load_skill()` — with tier labels (**external**, **project**, **bundled**), per-root skill counts, and shadowing warnings when the same registry ID exists in multiple roots.

    skillware paths
    skillware paths --skills-root /path/to/my/skills

#### Flags

| Flag | Description |
| :--- | :--- |
| `--skills-root <path>` | Override the skills directory for this command only (shows a single override root). |

Read-only in v0.4.x; persist project/external paths via config is tracked in #246. Interactive menu: **`4` / `paths`**.

## Path resolution

`skillware list` searches for skills in the same order as `SkillLoader`:

1. Roots listed in `SKILLWARE_SKILL_PATH` (OS path separator between multiple entries)
2. A `skills/` directory under the current working directory and its parents
3. Bundled skills installed with the `skillware` package

Run `skillware paths` for a live view of resolved roots, tiers, and shadowing.

To point the CLI at a persistent custom root, set the environment variable:

    export SKILLWARE_SKILL_PATH=/path/to/my/skills
    skillware list

Only skills with both `manifest.yaml` and `skill.py` present are shown —
the same condition `SkillLoader` requires to load a skill successfully.

### Skill ID vs manifest `name` vs LLM tool name

| Concept | Source | Example (`office/pdf_form_filler`) |
| :--- | :--- | :--- |
| **CLI / loader ID** | Folder path `category/skill_name` | `office/pdf_form_filler` |
| **`manifest.yaml` `name`** | Should match the registry ID | `office/pdf_form_filler` |
| **Gemini tool name** | Sanitized via `to_gemini_tool()` / `_sanitize_gemini_tool_name()` | `office_pdf_form_filler` |
| **Claude tool name** | `manifest["name"]` via adapter | `office/pdf_form_filler` |
| **OpenAI / DeepSeek tool name** | Sanitized adapter name | `office_pdf_form_filler` |
| **Ollama prompt `"tool"`** | Same as manifest when using full IDs | `office/pdf_form_filler` |

`skillware list` always shows the **path-derived ID**; it does not read `manifest["name"]` for the ID column. Keep manifest `name` aligned with that ID so agent loops and `SkillLoader.to_*_tool()` stay consistent. `SkillLoader.load_skill()` warns via `SkillwareIdentityWarning` when a registry-layout skill has a missing or mismatched `name` (flat private skills under `<skill_root>/<skill_name>/` are not checked). See [Agent loops](agent_loops.md#tool-name-matching).

## Color theme

The CLI uses a pastel color palette consistent with the project's visual identity:

| Element | Color | Hex |
| :--- | :--- | :--- |
| Table headers and borders | Lavender | `#C7CEEA` |
| Category column | Peach | `#FFDAC1` |
| Skill ID column | Mint | `#B5EAD7` |
| Splash logo and tagline | Gradient (ice → sky → blush) | `#D4E4F1` → `#79B6D8` → `#EBD8DC` |
| Splash footer links | Lavender | `#C7CEEA` |
| Interactive menu | Peach | `#FFDAC1` |

## short_description field

Skill manifests can include a `short_description` field (max 80 chars) for
a concise one-line summary shown in `skillware list`:

    short_description: "Screens Ethereum wallets against OFAC sanctions and mixer lists."

If `short_description` is absent, the CLI falls back to the first sentence
of `description`, truncated to 80 characters.

