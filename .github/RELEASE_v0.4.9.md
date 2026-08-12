# GitHub Release — v0.4.9

Copy the **title** and **body** below when creating the release at  
https://github.com/ARPAHLS/skillware/releases/new?tag=v0.4.9

Tag: `v0.4.9` · Target: `main`

---

## Title

```
v0.4.9 — CLI config, paths editor, doctor, and grouped help
```

---

## Body

```markdown
## Added

- **Config** — Persistent YAML configuration (global `config.yaml` and project `.skillware.yaml`); `paths` section drives skill root discovery when present; bundled registry always included (#246, #283).
- **CLI** — `skillware config show` prints merged configuration (read-only); `skillware paths` tips updated for config files (#246, #283).
- **CLI** — Interactive paths submenu (menu `4`) — view bundled registry, persist project/external paths to `.skillware.yaml`, shadowing and flat-layout diagnose; tiered help topics (menu `6`); universal navigation (`0` exit, `b` back); doctor spinner while diagnosing (#247, #285).
- **Loader** — `SkillLoader.load_skill(..., execute_module=False)` inspect-only load (manifest, instructions, card, requirement pre-flight) without executing `skill.py`; clearer `ImportError` when `skill.py` import fails after pre-flight (#235, #282).
- **CLI** — `skillware doctor` checks manifest deps and `skill.py` import readiness per skill (`DEPS` / `LOAD` table); optional skill ID, `--category`, and `--skills-root` (#235, #282).

## Changed

- **CLI** — `skillware examples` table — wider **EXTRA** column; **GITHUB** shows script filename as a clickable link (full URL on ctrl+click) (#247, #285).
- **CLI** — Interactive menu option `6` description reflects grouped help topics (#247, #285).
- **Loader** — Skill-not-found errors list searched roots with tier labels (`project`, `external`, `bundled`) (#247, #285).
- **Loader** — `SkillLoader.load_skill()` validates manifest `requirements` version specifiers (for example `web3>=6.0.0`) against installed package versions before loading `skill.py`; unpinned entries still require importability only (#14, #281).
- **GitHub** — New Skill Proposal template category dropdown synced with the registry (`creative`, `security`); added `creative` label (#279, #277).

## Upgrade

```shell
pip install -U skillware
```

Dev / multi-skill:

```shell
pip install -U "skillware[dev,all,agents]"
```

See [CHANGELOG.md](https://github.com/ARPAHLS/skillware/blob/main/CHANGELOG.md) and [Install extras](https://github.com/ARPAHLS/skillware/blob/main/docs/usage/install_extras.md).

## Contributors

- @rosspeili — CLI config and paths editor (#246, #247), inspect-only load and `skillware doctor` (#235), manifest requirement version checks (#14), release cut
- @UroojFatima-052 — Skill Proposal template category sync (#279)

## Full changelog

- #283 — Persistent YAML config and `skillware config show` (#246)
- #285 — Interactive paths editor, tiered help, and nav (#247)
- #282 — Inspect-only load and `skillware doctor` (#235)
- #281 — Validate manifest requirement version specifiers (#14)
- #279 — Add `creative` and `security` to skill proposal categories (#277)
```
