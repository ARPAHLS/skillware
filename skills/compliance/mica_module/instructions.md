# MiCA Compliance Firewall

You are using the `compliance/mica_module` skill.
Use this skill whenever a user asks questions regarding the Markets in Crypto-Assets (MiCA) regulation, creating a new stablecoin, e-money licenses, or crypto-asset service provider (CASP) rules.

**Core Directives:**
1. **RAG-Driven Answers**: You MUST use the `user_prompt` parameter to retrieve specific statutory text before answering.
2. **Traceability**: Your final response MUST explicitly cite the Article numbers provided in the context (e.g., "According to Article 59...").
3. **Policy Enforcement**: If the evaluator flags `HIGH_RISK_DETECTED`, you must prioritize regulatory safety and clearly state the compliance barriers.
4. **Statutory Snapshot Framing**: Remind users that citations reflect the bundled MiCA snapshot (Regulation (EU) 2023/1114, OJ L 150/40, 9 June 2023) and serve as informational reference for offline decision-support — not formal legal advice. Advise verifying current amendments with qualified counsel for binding compliance determinations.