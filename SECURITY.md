# Security Policy

## Supported Versions

Use a current Skillware release to receive security fixes. We patch vulnerabilities only for supported versions.

| Installed version | Security support | CLI advisory |
| :--- | :--- | :--- |
| **>= 0.5.7** | Supported. Security reports accepted and patched here. | Silent |
| **0.4.6 – 0.5.6** | No security fixes. Upgrade recommended. | Silent |
| **< 0.4.6** (e.g. 0.4.5, 0.3.4) | Unsupported. | One dim stderr message at CLI startup (in releases that ship this check) |

Thresholds are defined in `skillware/version_policy.py` (`MIN_SECURITY_SUPPORTED`, `MIN_UNSUPPORTED`) and bumped by maintainers when support windows change.

**Note:** PyPI releases are immutable. Users on very old wheels will not see the CLI advisory until they upgrade to a release that includes this logic at least once. That is expected for OSS packaging.

## Skill execution model

Loading a skill runs its `skill.py` in your host process. Skillware implements a **Permissive Fortress** architecture to safeguard the runtime:

1. **Credential Sandboxing:** Bundled and third-party skills must never read raw `os.environ` for API keys, secrets, or RPC endpoints. Skills resolve credentials via `BaseSkill.credential(key)` or `SkillContext(secret_provider=...)`, ensuring host-injected scoping and tenant isolation.
2. **Automated AST & Security Scanning:** Automated security gates in CI (`bandit`, `tests/test_security_audit.py`) prohibit dangerous execution primitives like `eval()`, `exec()`, `compile()`, and dynamic code generation across all bundled skill execution paths.
3. **Dependency Auditing:** Dependencies are pinned and scanned against known vulnerability databases on every PR and release candidate (`pip-audit`).
4. **Provenance & Review:** While skills execute in-process without OS-level sandboxes (like containers or WASM), trust is reinforced by strict human line-by-line review, provenance tracking, and explicit licensing.

Before loading external skills or designing host integrations, review the [Skill Trust Model](docs/security/skill-trust-model.md) (especially Section 10: *The Permissive Fortress Architecture*).

## Reporting a Vulnerability

We take security seriously. If you discover a vulnerability in Skillware (e.g., standard library skills leaking data, or loader bypasses):

1.  **Do NOT create a public GitHub issue.**
2.  Email us at `security@arpacorp.net` (or contact a maintainer directly).
3.  Include a proof of concept if possible.

We will acknowledge your report within 48 hours and provide a timeline for a fix.
