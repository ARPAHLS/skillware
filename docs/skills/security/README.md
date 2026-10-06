# Security Agent Skills

Offline and local-first defenses for untrusted input before it reaches model context or host agents.

This hub is the documentation landing page for Skillware **security** agent skills. Runtime bundles stay at `skills/security/<skill_name>/` with stable registry IDs `security/<skill_name>` — do not rename those folders for search indexing.

[Skill Library](../README.md) · [Glossary](../../glossary.md) · [Sitemap](../../sitemap.md) · [Agent loops](../../usage/agent_loops.md)

## Catalog

| Skill | ID | Version | Issuer | Description |
| :--- | :--- | :--- | :--- | :--- |
| **[Prompt Injection Firewall](prompt_injection_firewall.md)** | `security/prompt_injection_firewall` | `0.2.0` (21 Sep 2026) | [@mrmasa88](https://github.com/mrmasa88) ([@ARPAHLS](https://github.com/ARPAHLS), [AO](https://github.com/0x-AO-Protocol)) | Offline deterministic scan and sanitization for hostile instructions in untrusted text before LLM context. |
| **[Deceptive UI Guard](deceptive_ui_guard.md)** | `security/deceptive_ui_guard` | `0.2.0` (3 Sep 2026) | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | Deterministic HTML surface scan with zone weighting, allowlists, optional render diff, trust scoring, and pre-click agent guidance (#314). |
| **[Deepfake Guard](deepfake_guard.md)** | `security/deepfake_guard` | `0.1.0` (6 Oct 2026) | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | Offline media and KYC document authenticity guard: ICAO 9303 MRZ validation, C2PA provenance, ELA, noise residual variance, and moiré screen recapture detection (#48). |

## Typical host pipelines

- Scan untrusted **text** (prompt injection, encoding smuggling, instruction override) before LLM context: `security/prompt_injection_firewall`.
- Scan untrusted **HTML** (hidden controls, bait, pre-click traps) before a click: `security/deceptive_ui_guard`.
- Verify untrusted **media / ID documents** (deepfakes, digital tampering, forged MRZ, recaptured screens) before KYC or onboarding: `security/deepfake_guard`.
- Combined channel: firewall (text), deceptive UI guard (DOM), and deepfake guard (media/documents).

## Load by registry ID

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("security/prompt_injection_firewall")
skill = bundle["class"]()
```

See the [Skill library](../README.md) for every category, and [install extras](../../usage/install_extras.md) for per-skill pip extras.
