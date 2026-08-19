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
    skillware doctor
    skillware config show
    skillware mail addressbook show
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
    python -m skillware doctor optimization/prompt_rewriter
    python -m skillware list --category compliance
    python -m skillware --help

**Windows PATH fix** — add both `Python3x\` and `Python3x\Scripts\` to your
system PATH, or use the `py` launcher:

    py -3 -m pip install skillware
    py -3 -m skillware list

## Version advisory

On CLI startup, Skillware checks the installed package version **once per process**.
If you are on an **unsupported** release (below `0.3.5`, for example `0.3.4` or `0.2.9`), a single
dim message is printed to stderr suggesting an upgrade to `>= 0.4.7`. Installs in the
`0.3.5`–`0.4.6` band stay silent (no security backports, but no startup spam). Current
supported installs (`0.4.7` and above) stay silent.

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
After each command completes, the menu re-prints automatically.

**Navigation (all menu levels):**

| Input | Action |
| :--- | :--- |
| `0` | Exit Skillware |
| `b` / `back` | Return to the previous menu (submenus only) |
| `q` | Same as `0` (exit) |
| `Ctrl+C` | Exit from the main menu |

Available commands:

| Input | Command | Status |
| :--- | :--- | :--- |
| `1` / `list` | List all locally installed skills | Available |
| `2` / `examples` | Browse runnable example scripts (index from `examples/README.md`, or from GitHub when no local copy exists) | Available |
| `3` / `test` | Run bundle tests (`test_skill.py`) for one or all skills | Available |
| `4` / `paths` | Paths submenu — view roots, edit project/external paths, shadowing, flat-layout diagnose | Available |
| `5` / `doctor` | Check manifest deps and skill.py import readiness | Available |
| `6` / `help` | Grouped help (Skills, Examples, Paths, Config, Mail, General) with doc links | Available |
| `7` / `mail` | Mail submenu — address book and signature setup for `office/gmail_handler` | Available |

## Grouped help

`skillware --help` prints a **compact topic index**, **CLI usage examples**, and pointers to install/docs. For full command details per topic, run `skillware` and choose **`6` / `help`**, then pick a topic:

| Input | Topic |
| :--- | :--- |
| `1` / `skills` | `list`, `test`, `doctor` |
| `2` / `examples` | indexed runnable scripts |
| `3` / `paths` | resolution and paths submenu |
| `4` / `config` | merged YAML settings |
| `5` / `general` | menu, `--help`, `--version` |
| `6` / `install` | pip install skillware |
| `7` / `docs` | link to this CLI guide |
| `8` / `interactive` | numbered splash menu |

Brief `--help` groups (same topics, less detail):

| Group | Topics |
| :--- | :--- |
| **Skills** | `list`, `test`, `doctor` |
| **Examples** | `examples` |
| **Paths** | `paths`, interactive paths submenu |
| **Config** | `config show` |
| **General** | interactive menu, `--help`, `--version` |

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

Columns: Script, Skill ID(s), Provider, Required extra (pip extra name), and **GITHUB** — the script filename as a clickable link to `main` (ctrl+click; full URL not repeated in the cell). Environment variables and longer notes stay in `examples/README.md`; a one-line pointer is printed below the table.

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

Show where Skillware looks for skills — same order as `SkillLoader.load_skill()` —
with tier labels (**project**, **external**, **bundled**; order depends on
legacy vs config — see [Path resolution](#path-resolution)), per-root skill
counts, and shadowing warnings when the same registry ID exists in multiple roots.
Only **existing** roots are searched at load time; missing project directories
are skipped, and bundled skills from `pip install skillware` remain available.

    skillware paths
    skillware paths --skills-root /path/to/my/skills

#### Flags

| Flag | Description |
| :--- | :--- |
| `--skills-root <path>` | Override the skills directory for this command only (shows a single override root). |

Non-interactive `skillware paths` is read-only. To **persist** project and external roots, use the interactive **paths submenu** (menu **`4` / `paths`**) or edit `.skillware.yaml` manually.

#### Interactive paths submenu (menu `4`)

| Input | Action |
| :--- | :--- |
| `1` / `view` | Same table as `skillware paths` (resolution, tiers, shadowing) |
| `2` / `bundled` | Show bundled registry root (read-only; shipped with pip) |
| `3` / `project` | Set `paths.project` to `auto` or an explicit directory (saved to `.skillware.yaml`) |
| `4` / `external` | Add or remove `paths.external` entries (saved to project config) |
| `5` / `shadows` | Shadowing summary only |
| `6` / `flat` | List flat-layout skills (`<root>/<name>/`) that load but do not appear in `skillware list` |
| `b` / `back` | Return to the main menu |

Bundled registry paths cannot be edited. Global config (`~/.config/skillware/config.yaml`) is not modified by the submenu — use `skillware config show` to inspect merged settings.

### skillware doctor

Check whether skills can load in the current environment — manifest **requirements** pre-flight (**DEPS**) and `skill.py` import (**LOAD**) — without running `execute()`. Uses the same skill roots as `skillware list`.

    skillware doctor
    skillware doctor finance/wallet_screening
    skillware doctor --category compliance
    skillware doctor --skills-root /path/to/my/skills

#### Arguments and flags

| Input | Description |
| :--- | :--- |
| *(no args)* | Diagnose all registry skills visible to `list` |
| `<category>/<skill_name>` | Diagnose one skill |
| `--category <name>` | Diagnose all skills in a category |
| `--skills-root <path>` | Override the skills directory for discovery and load |

**DEPS** validates manifest `requirements` (same rules as `SkillLoader.load_skill()`). **LOAD** imports `skill.py` and discovers the `BaseSkill` subclass; it is skipped (shown as `—`) when **DEPS** fails. The **DETAIL** column shows the first line of any error.

Exit code is non-zero when any skill fails **DEPS** or **LOAD**. For full bundle behavior, use `skillware test`.

Interactive menu: **`5` / `doctor`**.

### skillware config

Show merged global + project Skillware configuration (read-only). The `paths` and `mail` sections are active today; other top-level keys are preserved for future settings (themes, chains, etc.).

    skillware config show

**Global config:** `~/.config/skillware/config.yaml` (Linux/macOS), `%APPDATA%/skillware/config.yaml` (Windows), or override with `SKILLWARE_CONFIG_DIR`.

**Project config:** `.skillware.yaml` in the repository root (walks up from cwd). See [`.skillware.yaml.example`](../../.skillware.yaml.example).

Example project file:

```yaml
paths:
  project: auto
  external:
    - /path/to/private-skills
resolution:
  order:
    - project
    - external
    - bundled
legacy:
  honor_skillware_skill_path: true
mail:
  addressbook_path: ~/.config/skillware/addressbook.yaml
  signature_path: ~/.config/skillware/mail_signature.txt
  signature_html_path: ~/.config/skillware/mail_signature.html
  signature_plain: |
    —
    Agent Name
    Skillware Project
```

When no config file exists, resolution stays **legacy**: `SKILLWARE_SKILL_PATH` → `./skills/` walk → bundled. When config exists, `resolution.order` applies (default: project → external → bundled). The **bundled** registry from `pip install skillware` is always included and cannot be disabled. **Pip-only installs with no local `skills/` folder still resolve bundled registry skills** — only roots that exist on disk are searched; an empty project tier does not block bundled.

### skillware mail

Operator UX for **`office/gmail_handler`** address book, email signatures (including multi-profile), and attachment path settings — without editing bundled skill files. **Full operator guide:** [`docs/skills/gmail_handler.md`](../skills/gmail_handler.md) (fresh install checklist, precedence, plain vs HTML MIME, attachments, persistence).

    skillware mail
    skillware mail addressbook init
    skillware mail addressbook add
    skillware mail addressbook add --name "Jane" --email jane@example.com
    skillware mail addressbook show
    skillware mail addressbook validate
    skillware mail addressbook set-path ~/.config/skillware/addressbook.yaml
    skillware mail signature init
    skillware mail signature init --force
    skillware mail signature show
    skillware mail signature set --file ./signature.txt
    skillware mail signature validate
    skillware mail signature clear
    skillware mail signature profiles
    skillware mail signature set-profile formal
    skillware mail signature add-profile formal --html ~/.config/skillware/signatures/formal.html

**Nothing is configured by default.** Run **`addressbook init`** and **`signature init`** once to create files under your user config dir (`~/.config/skillware/` or `%APPDATA%/skillware/`). That data **survives skillware upgrades and reinstalls**; it is not stored inside the pip wheel.

**Precedence:** environment variables (`GMAIL_*`) → project `.skillware.yaml` → global `config.yaml` → skill bundled read-only defaults.

| Area | Actions |
|------|---------|
| Address book | **init**, **add** (wizard or `--name` / `--email` / `--aliases` / `--org` / `--id`), **show**, **validate**, **set-path** |
| Signature | **init** (plain + HTML + logo; `--force` overwrite), **show**, **set** (paste or `--file`), **validate**, **clear** |

**User config files** (after init):

| File | Purpose |
|------|---------|
| `addressbook.yaml` | Contacts |
| `mail_signature.txt` | Plain signature (`text/plain` MIME part) |
| `mail_signature.html` | HTML signature (logo, `—`, links — what Gmail shows) |
| `skillware_logo.png` | Local logo copy |
| `config.yaml` | Registers `mail.*` paths |

**Env overrides** (optional): `GMAIL_ADDRESSBOOK_PATH`, `GMAIL_SIGNATURE_PATH`, `GMAIL_SIGNATURE_HTML_PATH`, `GMAIL_SIGNATURE_PLAIN`, `GMAIL_SCAN_STATE_PATH`, `GMAIL_SEND_LEDGER_PATH`.

Interactive menu: **`7` / `mail`**. Submenu mirrors the commands above.

Test signature in your inbox (requires `.env` credentials):

    python examples/gmail_signature_test_send.py --to you@example.com --preview-only
    python examples/gmail_signature_test_send.py --to you@example.com

Non-interactive `skillware mail` (no subcommand) prints resolved paths and signature source — similar to the `mail` block in `skillware config show`.

## Path resolution

`skillware list`, `load_skill`, `test`, and `doctor` share the same roots as `SkillLoader`.

**Without config files (default):**

1. Roots listed in `SKILLWARE_SKILL_PATH` (OS path separator between multiple entries)
2. A `skills/` directory under the current working directory and its parents
3. Bundled skills installed with the `skillware` package

**With `.skillware.yaml` and/or global config:**

1. Tiers in `resolution.order` (default: project → external → bundled)
2. `paths.project`: `auto` (same walk as above) or an explicit directory
3. `paths.external`: persisted private/proprietary skill roots
4. Bundled registry always last-resort fallback (always on)

Run `skillware paths` for a live view of resolved roots, tiers, and shadowing. Run `skillware config show` for merged YAML settings.

To point the CLI at custom roots without config files:

    export SKILLWARE_SKILL_PATH=/path/to/my/skills
    skillware list

Or copy `.skillware.yaml.example` to `.skillware.yaml` and list paths under `paths.external`.

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

