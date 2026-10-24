# Bio Agent Skills

Skills that provide deterministic, offline life sciences, bioinformatics, genomics, and biotechnology capabilities for host agent loops.

This hub is the documentation landing page for Skillware **bio** agent skills. Runtime bundles stay at `skills/bio/<skill_name>/` with stable registry IDs `bio/<skill_name>` — do not rename those folders for search indexing.

[Skill Library](../README.md) · [Glossary](../../glossary.md) · [Sitemap](../../sitemap.md) · [Agent loops](../../usage/agent_loops.md)

## Catalog

| Skill | ID | Version | Issuer | Description |
| :--- | :--- | :--- | :--- | :--- |
| **[Sequence Operations](sequence_ops.md)** | `bio/sequence_ops` | `0.1.0` (24 Oct 2026) | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | Deterministic in-silico operations on DNA, RNA, and protein sequence strings. |

## Typical host pipelines

- Sequence validation and typing: `bio/sequence_ops` (action `validate` or `detect_type`).
- Transformation pipelines: transcribe coding DNA to RNA, translate to peptide frames, or compute reverse complement.
- Structural diffing: compare query sequence against reference gene or plasmid construct.

## Load by registry ID

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("bio/sequence_ops")
skill = bundle["class"]()
```

See the [Skill library](../README.md) for every category, and [install extras](../../usage/install_extras.md) for per-skill pip extras.
