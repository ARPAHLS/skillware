# Copyright (c) 2026 ARPA Hellenic Logical Systems
# SPDX-License-Identifier: MIT

"""Assurance test suite for bio/sequence_ops."""

from __future__ import annotations

import json
from pathlib import Path
import pytest
import yaml

from skillware.core.loader import SkillLoader
from .skill import SequenceOpsSkill


@pytest.fixture
def skill() -> SequenceOpsSkill:
    return SequenceOpsSkill()


@pytest.fixture
def manifest() -> dict:
    manifest_path = Path(__file__).parent / "manifest.yaml"
    with open(manifest_path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


@pytest.fixture
def card() -> dict:
    card_path = Path(__file__).parent / "card.json"
    with open(card_path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def test_manifest_and_card_integrity(skill, manifest, card):
    """Manifest and Card must contain matching metadata and correct category."""
    assert manifest["name"] == "bio/sequence_ops"
    assert manifest["category"] == "bio"
    assert manifest["tier"] == "core"
    assert manifest["shape"] == "atomic"
    assert manifest["target"] == ["software"]
    assert card["name"] == "Sequence Operations"
    assert card["issuer"]["org"] == "ARPAHLS"
    assert "ui_schema" in card


def test_skill_loader_discovery():
    """Skill must load cleanly through SkillLoader."""
    loaded_skill = SkillLoader.load_skill("bio/sequence_ops")
    assert loaded_skill is not None
    assert loaded_skill["manifest"]["name"] == "bio/sequence_ops"
    assert loaded_skill["manifest"]["category"] == "bio"


def test_detect_type_dna(skill):
    """DNA sequences must be identified with high confidence."""
    res = skill.execute({"action": "detect_type", "sequence": "ATGCGTAACCGTT"})
    assert res["status"] == "ready"
    assert res["molecule_type"] == "dna"
    assert res["confidence"] == "high"
    assert res["alphabet_violations"] == []
    assert res["length"] == 13


def test_detect_type_rna(skill):
    """RNA sequences containing Uracil must be detected as RNA."""
    res = skill.execute({"action": "detect_type", "sequence": "AUGCGUAAUUGCA"})
    assert res["status"] == "ready"
    assert res["molecule_type"] == "rna"
    assert res["confidence"] == "high"
    assert res["alphabet_violations"] == []


def test_detect_type_protein(skill):
    """Amino acid strings must be detected as protein."""
    seq = "MVLSPADKTNVKAAWGKVGAHAGEYGAEALERMFLSFPTTKTYFPHFDLSH"
    res = skill.execute({"action": "detect_type", "sequence": seq})
    assert res["status"] == "ready"
    assert res["molecule_type"] == "protein"
    assert res["confidence"] == "high"


def test_detect_type_unknown(skill):
    """Strings with non-biological characters must be flagged."""
    res = skill.execute({"action": "detect_type", "sequence": "ATGC123$$$ZZ"})
    assert res["status"] == "ready"
    assert res["molecule_type"] == "unknown"
    assert res["confidence"] == "low"
    assert len(res["alphabet_violations"]) > 0


def test_validate_success(skill):
    """Standard sequences must validate true."""
    res = skill.execute(
        {
            "action": "validate",
            "sequence": "ATGCGTAA",
            "molecule_type": "dna",
            "min_length": 5,
            "max_length": 50,
        }
    )
    assert res["status"] == "ready"
    assert res["valid"] is True
    assert res["length"] == 8


def test_validate_length_bounds(skill):
    """Sequences outside min/max length must fail validation."""
    res_short = skill.execute(
        {
            "action": "validate",
            "sequence": "ATG",
            "min_length": 5,
        }
    )
    assert res_short["status"] == "ready"
    assert res_short["valid"] is False
    assert "LENGTH_OUT_OF_BOUNDS" in res_short["reason_codes"]

    res_long = skill.execute(
        {
            "action": "validate",
            "sequence": "ATGCGTAA",
            "max_length": 4,
        }
    )
    assert res_long["status"] == "ready"
    assert res_long["valid"] is False
    assert "LENGTH_OUT_OF_BOUNDS" in res_long["reason_codes"]


def test_validate_ambiguous_codes(skill):
    """IUPAC ambiguity codes should be accepted or rejected based on allow_ambiguous."""
    ambiguous_seq = "ATGCRNY"
    res_allowed = skill.execute(
        {
            "action": "validate",
            "sequence": ambiguous_seq,
            "allow_ambiguous": True,
        }
    )
    assert res_allowed["status"] == "ready"
    assert res_allowed["valid"] is True

    res_strict = skill.execute(
        {
            "action": "validate",
            "sequence": ambiguous_seq,
            "allow_ambiguous": False,
        }
    )
    assert res_strict["status"] == "ready"
    assert res_strict["valid"] is False
    assert "INVALID_ALPHABET" in res_strict["reason_codes"]


def test_revcom_golden(skill):
    """Reverse complement of DNA must adhere to standard Watson-Crick pairing in 5'->3' inversion."""
    res = skill.execute({"action": "revcom", "sequence": "ATGCGTAA"})
    assert res["status"] == "ready"
    assert res["output_sequence"] == "TTACGCAT"
    assert res["molecule_type"] == "dna"

    # Palindrome test (EcoRI recognition site: GAATTC)
    res_pal = skill.execute({"action": "revcom", "sequence": "GAATTC"})
    assert res_pal["status"] == "ready"
    assert res_pal["output_sequence"] == "GAATTC"


def test_revcom_unsupported_type_error(skill):
    """Reverse complement must reject RNA and protein sequences."""
    res_rna = skill.execute({"action": "revcom", "sequence": "AUGCGUAA"})
    assert res_rna["status"] == "error"
    assert "UNSUPPORTED_MOLECULE_TYPE" in res_rna["reason_codes"]

    res_prot = skill.execute({"action": "revcom", "sequence": "MVLSPADKTNVK"})
    assert res_prot["status"] == "error"
    assert "UNSUPPORTED_MOLECULE_TYPE" in res_prot["reason_codes"]


def test_transcribe(skill):
    """Transcription must convert Thymine to Uracil deterministically."""
    res = skill.execute({"action": "transcribe", "sequence": "ATGCGTAA"})
    assert res["status"] == "ready"
    assert res["output_sequence"] == "AUGCGUAA"
    assert res["molecule_type"] == "rna"

    # Idempotent on RNA
    res_rna = skill.execute({"action": "transcribe", "sequence": "AUGCGUAA"})
    assert res_rna["status"] == "ready"
    assert res_rna["output_sequence"] == "AUGCGUAA"


def test_translate_reading_frames_and_to_stop(skill):
    """Translation must support reading frames 0, 1, 2 and to_stop termination."""
    dna_seq = "ATGGCCATTGTAATGGGCCGCTGAAAGGGTGCCCGATAG"
    # Frame 0:
    # ATG GCC ATT GTA ATG GGC CGC TGA AAG GGT GCC CGA TAG
    #  M   A   I   V   M   G   R   *   K   G   A   R   *
    res_f0 = skill.execute(
        {"action": "translate", "sequence": dna_seq, "reading_frame": 0}
    )
    assert res_f0["status"] == "ready"
    assert res_f0["output_sequence"] == "MAIVMGR*KGAR*"

    # to_stop=True terminates at first *
    res_stop = skill.execute(
        {
            "action": "translate",
            "sequence": dna_seq,
            "reading_frame": 0,
            "to_stop": True,
        }
    )
    assert res_stop["status"] == "ready"
    assert res_stop["output_sequence"] == "MAIVMGR"

    # Frame 1: offset by 1
    res_f1 = skill.execute(
        {"action": "translate", "sequence": dna_seq, "reading_frame": 1}
    )
    assert res_f1["status"] == "ready"
    assert len(res_f1["output_sequence"]) > 0

    # Incomplete codon at end (length not multiple of 3)
    res_incomplete = skill.execute({"action": "translate", "sequence": "ATGGCCA"})
    assert res_incomplete["status"] == "ready"
    assert res_incomplete["output_sequence"] == "MA"


def test_pairwise_align_global_and_local(skill):
    """Pairwise alignment must calculate identity, matches, mismatches, and gaps."""
    res = skill.execute(
        {
            "action": "pairwise_align",
            "sequence": "ATGCGTAA",
            "sequence_b": "ATGCGTGA",
            "mode": "global",
        }
    )
    assert res["status"] == "ready"
    assert res["identity_percent"] == 87.5
    assert res["matches"] == 7
    assert res["mismatches"] == 1
    assert res["gaps"] == 0
    assert "alignment_a" in res
    assert "alignment_b" in res

    # Local alignment
    res_local = skill.execute(
        {
            "action": "pairwise_align",
            "sequence": "NNNNATGCGTAANNNN",
            "sequence_b": "ATGCGTAA",
            "mode": "local",
        }
    )
    assert res_local["status"] == "ready"
    assert res_local["matches"] == 8


def test_variant_diff_structural_calls(skill):
    """Variant diff must call substitutions, insertions, and deletions."""
    # Substitution
    res_sub = skill.execute(
        {
            "action": "variant_diff",
            "reference": "ATGCGTAA",
            "query": "ATGCGTGA",
        }
    )
    assert res_sub["status"] == "ready"
    assert len(res_sub["mutations"]) == 1
    mut = res_sub["mutations"][0]
    assert mut["type"] == "substitution"
    assert mut["position"] == 7
    assert mut["ref"] == "A"
    assert mut["alt"] == "G"

    # Insertion
    res_ins = skill.execute(
        {
            "action": "variant_diff",
            "reference": "ATGCGTAA",
            "query": "ATGCGCTAA",
        }
    )
    assert res_ins["status"] == "ready"
    assert any(m["type"] == "insertion" for m in res_ins["mutations"])

    # Deletion
    res_del = skill.execute(
        {
            "action": "variant_diff",
            "reference": "ATGCGTAA",
            "query": "ATGC-TAA",
        }
    )
    assert res_del["status"] == "ready"
    assert any(m["type"] == "deletion" for m in res_del["mutations"])

    # Identical
    res_id = skill.execute(
        {
            "action": "variant_diff",
            "reference": "ATGCGTAA",
            "query": "ATGCGTAA",
        }
    )
    assert res_id["status"] == "ready"
    assert len(res_id["mutations"]) == 0


def test_kmer_profile_entropy_and_top_n(skill):
    """K-mer profiling must compute counts, top-N, and Shannon entropy."""
    res = skill.execute(
        {
            "action": "kmer_profile",
            "sequence": "AAAAATTTTT",
            "k": 2,
            "top_n": 5,
        }
    )
    assert res["status"] == "ready"
    assert res["total_kmers"] == 9
    assert res["entropy"] > 0.0
    assert len(res["top_kmers"]) > 0


def test_generate_seeded_determinism(skill):
    """Seeded sequence generation must be 100% reproducible."""
    res1 = skill.execute(
        {
            "action": "generate",
            "molecule_type": "dna",
            "length": 50,
            "seed": 12345,
        }
    )
    res2 = skill.execute(
        {
            "action": "generate",
            "molecule_type": "dna",
            "length": 50,
            "seed": 12345,
        }
    )
    res3 = skill.execute(
        {
            "action": "generate",
            "molecule_type": "dna",
            "length": 50,
            "seed": 99999,
        }
    )
    assert res1["status"] == "ready"
    assert res1["sequence"] == res2["sequence"]
    assert res1["sequence"] != res3["sequence"]
    assert len(res1["sequence"]) == 50

    # Protein generation
    res_prot = skill.execute(
        {
            "action": "generate",
            "molecule_type": "protein",
            "length": 25,
            "seed": 42,
        }
    )
    assert res_prot["status"] == "ready"
    assert len(res_prot["sequence"]) == 25


def test_error_handling_and_aliases(skill):
    """Errors for missing inputs, unknown actions, and parameter aliases."""
    # Missing sequence
    res_missing = skill.execute({"action": "revcom"})
    assert res_missing["status"] == "error"
    assert "MISSING_INPUT" in res_missing["reason_codes"]

    # Unknown action
    res_bad_action = skill.execute({"action": "unknown_op", "sequence": "ATGC"})
    assert res_bad_action["status"] == "error"
    assert "INVALID_ACTION" in res_bad_action["reason_codes"]

    # Parameter alias: seq instead of sequence
    res_alias = skill.execute({"action": "transcribe", "seq": "ATGC"})
    assert res_alias["status"] == "ready"
    assert res_alias["output_sequence"] == "AUGC"

    # Missing query in alignment
    res_no_query = skill.execute({"action": "pairwise_align", "sequence": "ATGC"})
    assert res_no_query["status"] == "error"
    assert "MISSING_INPUT" in res_no_query["reason_codes"]


def test_find_orfs_detection(skill):
    """find_orfs must discover coding regions and coordinates across reading frames."""
    # Construct with known ORF: ATG (start) + 33 bp coding (11 aa) + TAA (stop) = 39 bp
    # ATG GCC ATT GTA ATG GGC CGC AAG GGT GCC CGA TAA
    coding_chunk = "ATGGCCATTGTAATGGGCCGCAAGGGTGCCCGATAA"
    prefix = "CCC"
    suffix = "GGG"
    dna_seq = prefix + coding_chunk + suffix

    res = skill.execute(
        {
            "action": "find_orfs",
            "sequence": dna_seq,
            "min_protein_length": 5,
            "strand": "forward",
        }
    )
    assert res["status"] == "ready"
    assert res["orfs_count"] >= 1
    top_orf = res["orfs"][0]
    assert top_orf["strand"] == "+"
    assert top_orf["start_codon"] == "ATG"
    assert top_orf["stop_codon"] == "TAA"
    assert top_orf["protein_sequence"].startswith("M")
    assert top_orf["protein_length"] >= 5


def test_format_fasta(skill):
    """format_fasta must generate wrapped multi-line FASTA strings."""
    seq = "ATGC" * 15  # 60 bp
    res = skill.execute(
        {
            "action": "format_fasta",
            "sequence": seq,
            "header": "test_construct_1",
            "line_width": 20,
        }
    )
    assert res["status"] == "ready"
    assert res["header"] == "test_construct_1"
    lines = res["fasta"].strip().split("\n")
    assert lines[0] == ">test_construct_1"
    assert len(lines) == 4  # header + 3 lines of 20 bp
    assert all(len(line) == 20 for line in lines[1:])


def test_translate_mitochondrial_code(skill):
    """translate must support NCBI Table 2 (Vertebrate Mitochondrial)."""
    # In Table 1: AGA is Arg (R)
    # In Table 2: AGA is Stop (*)
    test_seq = "ATGAGA"
    res_std = skill.execute(
        {"action": "translate", "sequence": test_seq, "table_id": 1}
    )
    assert res_std["status"] == "ready"
    assert res_std["output_sequence"] == "MR"

    res_mito = skill.execute(
        {"action": "translate", "sequence": test_seq, "table_id": 2}
    )
    assert res_mito["status"] == "ready"
    assert res_mito["output_sequence"] == "M*"


def test_kb_catalog_integrity():
    """Verify that all knowledge base files exist and are valid JSON."""
    kb_dir = Path(__file__).resolve().parent / "kb"
    required_kb_files = [
        "codon_table.json",
        "iupac_codes.json",
        "amino_acids.json",
        "genetic_codes.json",
    ]
    for filename in required_kb_files:
        filepath = kb_dir / filename
        assert filepath.is_file(), f"Missing KB file: {filename}"
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert isinstance(data, dict)
            assert len(data) > 0


def test_list_genetic_tables(skill):
    """list_tables must return supported NCBI genetic code tables from KB."""
    res = skill.execute({"action": "list_tables"})
    assert res["status"] == "ready"
    assert res["tables_count"] >= 3
    table_ids = [t["table_id"] for t in res["tables"]]
    assert 1 in table_ids
    assert 2 in table_ids
    assert 11 in table_ids


def test_lookup_iupac_code(skill):
    """lookup_iupac must return accurate biological notation and properties."""
    # Look up ambiguous nucleotide R (puRine)
    res_r = skill.execute({"action": "lookup_iupac", "code": "R"})
    assert res_r["status"] == "ready"
    assert res_r["nucleotide"]["name"] == "puRine (A or G)"
    assert res_r["nucleotide"]["complement"] == "Y"
    assert set(res_r["nucleotide"]["bases"]) == {"A", "G"}

    # Look up standard amino acid M (Methionine)
    res_m = skill.execute({"action": "lookup_iupac", "code": "M"})
    assert res_m["status"] == "ready"
    assert res_m["amino_acid"]["name"] == "Methionine"
    assert res_m["biophysical_properties"]["molecular_weight"] == 149.21

    # Look up unknown code
    res_bad = skill.execute({"action": "lookup_iupac", "code": "1"})
    assert res_bad["status"] == "error"
    assert "UNKNOWN_CODE" in res_bad["reason_codes"]
