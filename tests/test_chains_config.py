"""Tests for chain config parsing."""

from skillware.core.chains_config import ChainDefinition, parse_chains_block


def test_parse_chains_legacy_placeholder():
    defs, legacy = parse_chains_block({"default": []})
    assert defs == {}
    assert legacy == {"default": []}


def test_parse_sanitize_input_chain():
    raw = {
        "sanitize_input": {
            "description": "Scan and compress",
            "steps": [
                {
                    "id": "scan",
                    "skill": "security/prompt_injection_firewall",
                    "input_from": {"source_text": "host.source_text"},
                    "map_out": {"sanitized_text": "next.raw_text"},
                },
                {
                    "skill": "optimization/prompt_rewriter",
                    "when": {
                        "prior_step": "scan",
                        "field": "is_safe",
                        "equals": True,
                    },
                },
            ],
        }
    }
    defs, legacy = parse_chains_block(raw)
    assert legacy == {}
    assert "sanitize_input" in defs
    chain: ChainDefinition = defs["sanitize_input"]
    assert len(chain.steps) == 2
    assert chain.steps[1].when is not None
    assert chain.steps[1].when.equals is True
