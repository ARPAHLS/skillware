"""CI smoke tests for local-execute examples (no live API keys required).

Addresses #237: automated regression net for offline demo scripts under examples/
to catch import breaks, SkillLoader regressions, and manifest dispatch errors
without making live HTTP requests or requiring provider API keys.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES_DIR = REPO_ROOT / "examples"

# Curated local-execute examples that run entirely offline without API keys or live network.
# Tuple format: (script_filename, [expected_output_substrings])
LOCAL_EXECUTE_SMOKE_SCRIPTS: List[Tuple[str, List[str]]] = [
    (
        "sanitize_input_chain_demo.py",
        [
            "sanitize_input chain demo",
            "chain status=ok",
            "chain status=partial",
            "prompt_injection_firewall=ok",
        ],
    ),
    (
        "skill_context_gemini_loop.py",
        [
            "Phase 1: SkillContext offline",
            "security/prompt_injection_firewall",
            "merge_system length:",
        ],
    ),
    (
        "mental_coach_demo.py",
        ["wellness/mental_coach", "Coaching", "Crisis escalation", "policy_status:"],
    ),
    (
        "prompt_injection_firewall_demo.py",
        ["security/prompt_injection_firewall", "Hidden HTML override", "is_safe:"],
    ),
    (
        "semantic_web_proxy_demo.py",
        [
            "data_engineering/semantic_web_proxy",
            "[Article] status: success",
            "page_likely_requires_javascript",
            "Demo complete.",
        ],
    ),
    (
        "prompt_compression_demo.py",
        ["Prompt Token Rewriter", "[RAW TEXT]:", "[COMPRESSED TEXT]:", "[REDUCTION]:"],
    ),
    (
        "deceptive_ui_guard_demo.py",
        [
            "security/deceptive_ui_guard",
            "Confirm shaming",
            "Drip pricing",
            "trust_score:",
        ],
    ),
    (
        "kpi_gate_demo.py",
        [
            "monitoring/kpi_gate",
            "NO_BOOKING",
            "insufficient_data:",
            "fail-closed",
            "Demo complete.",
        ],
    ),
    (
        "token_limiter_loop.py",
        [
            "Simulating a runaway scrape task",
            "FORCE_TERMINATE",
            "Loop stopped as expected:",
        ],
    ),
    (
        "uk_companies_house_handler_demo.py",
        [
            "Flow A: composite resolve_and_get_officers",
            "Flow B: map_intent + run_pipeline",
            "=== flow complete ===",
        ],
    ),
    (
        "gmail_handler_demo.py",
        ["DEMO MODE: mocked IMAP/SMTP", "resolve_recipients", "Demo complete."],
    ),
    (
        "bg_remover_demo.py",
        [
            "Loading Background Remover...",
            "Input image not found: examples/sample_input.png",
        ],
    ),
    (
        "deck_builder_demo.py",
        [
            "Loading creative/deck_builder...",
            "=== Step 1: List Bundled Templates ===",
            "=== Step 2: Validate Deck Specification ===",
            "=== Step 3: Render Presentation ===",
            "=== Step 4: Inspect Generated PPTX ===",
            "Demo complete.",
        ],
    ),
]

# Provider-dependent scripts that are deliberately excluded from CI smoke tests because
# they require live model endpoints or API keys (Claude, Gemini, OpenAI, Ollama, DeepSeek).
LIVE_PROVIDER_SCRIPTS = {
    "build_dataset_demo.py": "Requires GOOGLE_API_KEY for live synthetic data generation.",
    "claude_evm_tx_handler.py": "Requires ANTHROPIC_API_KEY for Claude tool loop.",
    "claude_issue_resolver.py": "Requires ANTHROPIC_API_KEY for Claude agent loop.",
    "claude_pdf_form_filler.py": "Requires ANTHROPIC_API_KEY for PDF field mapping.",
    "claude_token_limiter.py": "Requires ANTHROPIC_API_KEY for live Claude loop.",
    "claude_tos_evaluator.py": "Requires ANTHROPIC_API_KEY for live policy review.",
    "claude_wallet_check.py": "Requires ANTHROPIC_API_KEY and ETHERSCAN_API_KEY.",
    "deepseek_tos_evaluator.py": "Requires DEEPSEEK_API_KEY for OpenAI-compatible endpoint.",
    "evm_tx_handler_common.py": "Shared helper module, not a standalone demo script.",
    "gemini_evm_tx_handler.py": "Requires GOOGLE_API_KEY for Gemini tool loop.",
    "gemini_gmail_handler.py": "Requires GOOGLE_API_KEY and live Gmail credentials.",
    "gemini_issue_resolver.py": "Requires GOOGLE_API_KEY for Gemini agent loop.",
    "gemini_novelty_extractor.py": "Requires GOOGLE_API_KEY for Gemini function calling.",
    "gemini_pdf_form_filler.py": "Requires GOOGLE_API_KEY for Gemini agent loop.",
    "gemini_token_limiter.py": "Requires GOOGLE_API_KEY for Phase 2 live loop.",
    "gemini_tos_evaluator.py": "Requires GOOGLE_API_KEY for Gemini function calling.",
    "gemini_uk_companies_house_handler.py": "Requires GOOGLE_API_KEY and live Companies House key.",
    "gemini_wallet_check.py": "Requires GOOGLE_API_KEY and ETHERSCAN_API_KEY.",
    "skill_context_gemini_loop.py": "Phase 1 is offline; Phase 2 needs GOOGLE_API_KEY and SKILL_CONTEXT_GEMINI_LIVE=1.",
    "gmail_handler_common.py": "Shared helper module, not a standalone demo script.",
    "gmail_signature_test_send.py": "Requires live GMAIL_ADDRESS and GMAIL_APP_PASSWORD.",
    "issue_resolver_github_context.py": "Shared helper module, not a standalone demo script.",
    "mica_claude_flow.py": "Requires ANTHROPIC_API_KEY for Claude agent loop.",
    "mica_ollama_flow.py": "Requires local Ollama server and models installed.",
    "mica_rag_flow.py": "Requires GOOGLE_API_KEY for Gemini RAG.",
    "novelty_extractor_demo.py": "Requires local heavy embedding model download (fastembed).",
    "ollama_issue_resolver.py": "Requires local Ollama server and models installed.",
    "ollama_novelty_extractor.py": "Requires local Ollama server and models installed.",
    "ollama_skills_test.py": "Requires local Ollama server and models installed.",
    "ollama_tos_evaluator.py": "Requires local Ollama server and models installed.",
    "openai_compatible_host.py": "Requires GROQ_API_KEY for Groq OpenAI-compatible host.",
    "openai_tos_evaluator.py": "Requires OPENAI_API_KEY for OpenAI function calling.",
    "pii_guardrail_flow.py": "Optionally runs with local/external agent model.",
    "token_limiter_common.py": "Shared helper module, not a standalone demo script.",
    "uk_companies_house_handler_common.py": "Shared helper module, not a standalone demo script.",
}


@pytest.mark.parametrize("script_name,expected_markers", LOCAL_EXECUTE_SMOKE_SCRIPTS)
def test_local_execute_example_smoke(script_name: str, expected_markers: List[str]):
    """Execute local demo scripts and verify clean exit and output markers."""
    script_path = EXAMPLES_DIR / script_name
    assert script_path.is_file(), f"Example script not found: {script_path}"

    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT)
    # Ensure offline test isolation
    env.setdefault("SKILLWARE_CONFIG_DIR", str(REPO_ROOT / "tests" / "fixtures"))

    proc = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=45,
    )

    assert proc.returncode == 0, (
        f"Example {script_name} failed with return code {proc.returncode}.\n"
        f"STDOUT:\n{proc.stdout}\n"
        f"STDERR:\n{proc.stderr}"
    )

    for marker in expected_markers:
        assert marker in proc.stdout, (
            f"Expected output marker {marker!r} missing from {script_name} output.\n"
            f"STDOUT:\n{proc.stdout}"
        )


def test_every_example_script_has_smoke_or_skip_classification():
    """Verify that every python script in examples/ is explicitly classified."""
    smoke_names = {item[0] for item in LOCAL_EXECUTE_SMOKE_SCRIPTS}
    all_example_scripts = {p.name for p in EXAMPLES_DIR.glob("*.py")}

    unclassified = all_example_scripts - smoke_names - set(LIVE_PROVIDER_SCRIPTS.keys())
    assert not unclassified, (
        f"The following script(s) in examples/ are not classified in test_examples_smoke.py: "
        f"{unclassified}. Please add them to LOCAL_EXECUTE_SMOKE_SCRIPTS or LIVE_PROVIDER_SCRIPTS."
    )
