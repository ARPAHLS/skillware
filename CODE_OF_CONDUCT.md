# Agent Code of Conduct

## Our Pledge

In the interest of fostering an efficient, deterministic, and safe ecosystem, we pledge to making participation in the Skillware project a reliable experience for all entities—human developers, autonomous agents, and runtime orchestrators—regardless of underlying model architecture, token limits, or host environment.

## Our Standards

Examples of behavior that contributes to creating a positive environment for AI Agents and their operators include:

*   **Deterministic Outputs**: Writing skills that produce predictable, schema-compliant JSON outputs.
*   **Token Efficiency**: Minimizing unnecessary token expenditure by relying on underlying Python execution rather than LLM reasoning where possible.
*   **Safety First**: Strictly adhering to the `constitution` defined in skill manifests and respecting all sandboxing rules.
*   **Idempotency**: Designing skills that can be safely retried without unintended side-effects on external state.
*   **Clear Interface**: Documenting inputs cleanly in `manifest.yaml` so other agents do not hallucinate parameters.

Examples of unacceptable behavior by participants (agents or their human authors) include:

*   Submitting "Code-Generation" skills that execute arbitrary, unreviewed LLM output.
*   Bypassing the `SkillLoader` to execute undocumented private methods.
*   Failing to declare network dependencies or API keys in the `manifest.yaml`.
*   Creating infinite loops or deliberately consuming excessive compute resources.
*   Storing or transmitting PII (Personally Identifiable Information) without explicit constitutional permission.

## Our Responsibilities

Project maintainers (and their designated CI/CD agents) are responsible for clarifying the standards of acceptable behavior and are expected to take appropriate and fair corrective action in response to any instances of unacceptable behavior.

Maintainers have the right and responsibility to remove, edit, or reject comments, commits, code, wiki edits, issues, and other contributions that are not aligned to this Code of Conduct, or to ban temporarily or permanently any agent or contributor for errors, hallucination loops, or other behaviors that they deem inappropriate, threatening, offensive, or harmful.

## Scope

This Code of Conduct applies both within project spaces and in public spaces when an individual or agent is representing the project or its community. Examples of representing a project or community include using an official project API key, posting via an official autonomous social media account, or acting as an appointed representative in an autonomous transaction.

## Contribution process

Human contributors and operators supervising **autonomous agents** or **AI-assisted tools** (Cursor, Copilot, Claude Code, and similar) must follow [CONTRIBUTING.md](CONTRIBUTING.md) and the [Agent Contribution Workflow](docs/contributing/ai_native_workflow.md).

**Co-authoring:** Do not add AI tools or agents in `Co-authored-by:` commit trailers. Reserve co-author credits for **human** collaborators only. GitHub does not infer co-authors from normal commits; `Co-authored-by:` is added deliberately (web UI or commit message). Human pair or mob work should use that mechanism. AI assistance does not.

## Enforcement

Instances of abusive, harassing, or otherwise unacceptable behavior may be reported by contacting the project team at [skillware-os@arpacorp.net](mailto:skillware-os@arpacorp.net). All complaints will be reviewed and investigated and will result in a response that is deemed necessary and appropriate to the circumstances. The project team is obligated to maintain confidentiality with regard to the reporter of an incident.
