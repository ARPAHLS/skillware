# Creative Agent Skills

Skills for image processing, media editing, and creative utilities.

This hub is the documentation landing page for Skillware **creative** agent skills. Runtime bundles stay at `skills/creative/<skill_name>/` with stable registry IDs `creative/<skill_name>` — do not rename those folders for search indexing.

[Skill Library](../README.md) · [Glossary](../../glossary.md) · [Sitemap](../../sitemap.md) · [Agent loops](../../usage/agent_loops.md)

## Catalog

| Skill | ID | Version | Issuer | Description |
| :--- | :--- | :--- | :--- | :--- |
| **[Background Remover](bg_remover.md)** | `creative/bg_remover` | `0.2.0` (2 Aug 2026) | [@AyushSrivastava1818](https://github.com/AyushSrivastava1818) ([@ARPAHLS](https://github.com/ARPAHLS)) | Removes image backgrounds locally using rembg and returns transparent PNGs. |
| **[Deck Builder](deck_builder.md)** | `creative/deck_builder` | `0.2.0` (16 Sep 2026) | [@tusharjamunkar](https://github.com/tusharjamunkar) ([@ARPAHLS](https://github.com/ARPAHLS)) | Offline PPTX assembly from JSON deck specs — placeholders, lint_deck, suggest_outline, and 13 layouts. |

## Typical host pipelines

- Remove a logo background, then drop it into a PPTX: `creative/bg_remover` → `creative/deck_builder` (see `examples/deck_builder_chain_demo.py`).
- Outline → quality gate → render: `creative/deck_builder` `suggest_outline` → `lint_deck` → assemble.

## Load by registry ID

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("creative/bg_remover")
skill = bundle["class"]()
```

See the [Skill library](../README.md) for every category, and [install extras](../../usage/install_extras.md) for per-skill pip extras.
