# Office Agent Skills

Skills for document processing, email automation, and productivity.

This hub is the documentation landing page for Skillware **office** agent skills. Runtime bundles stay at `skills/office/<skill_name>/` with stable registry IDs `office/<skill_name>` — do not rename those folders for search indexing.

[Skill Library](../README.md) · [Glossary](../../glossary.md) · [Sitemap](../../sitemap.md) · [Agent loops](../../usage/agent_loops.md)

## Catalog

| Skill | ID | Version | Issuer | Description |
| :--- | :--- | :--- | :--- | :--- |
| **[PDF Form Filler](pdf_form_filler.md)** | `office/pdf_form_filler` | `0.1.0` (16 Jul 2026) | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | Fills AcroForm-based PDFs by mapping user instructions to detected form fields using LLM-based semantic understanding. |
| **[Gmail Handler](gmail_handler.md)** | `office/gmail_handler` | `0.2.0` (19 Aug 2026) | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | Gmail send, search, read, reply, and attachments via IMAP/SMTP with address book, signatures, and confirmation gates. |

## Typical host pipelines

- Fill a PDF from natural-language instructions, then send it: `office/pdf_form_filler` → `office/gmail_handler`.
- Search mail, draft a reply, send with the confirmation gate: `office/gmail_handler` (`search` / `read` / `reply`).

## Load by registry ID

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("office/pdf_form_filler")
skill = bundle["class"]()
```

See the [Skill library](../README.md) for every category, and [install extras](../../usage/install_extras.md) for per-skill pip extras.
