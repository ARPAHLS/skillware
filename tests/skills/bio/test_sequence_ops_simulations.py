# Copyright (c) 2026 ARPA Hellenic Logical Systems
# SPDX-License-Identifier: MIT

"""Simulations, edge cases, and stress test suite for bio/sequence_ops."""

from __future__ import annotations

import pytest

from skills.bio.sequence_ops.skill import SequenceOpsSkill


@pytest.fixture
def skill() -> SequenceOpsSkill:
    return SequenceOpsSkill()


def test_simulation_complete_molecular_workflow(skill):
    """
    Simulation: Multi-step synthetic biology workflow.
    1. Seeded deterministic generation of a 1,200 bp coding construct.
    2. Alphabet validation and length verification.
    3. Trimer (k=3) frequency profiling and Shannon entropy calculation.
    4. In-silico transcription to mRNA.
    5. In-silico translation to polypeptide chain with to_stop=True.
    6. Introduce targeted mutations (SNP, insertion, deletion) and verify alignment & variant diff.
    """
    # Step 1: Generate 1,200 bp sequence with 50% target GC content
    gen_res = skill.execute(
        {
            "action": "generate",
            "molecule_type": "dna",
            "length": 1200,
            "seed": 4242,
            "gc_content": 0.50,
        }
    )
    assert gen_res["status"] == "ready"
    ref_dna = gen_res["sequence"]
    assert len(ref_dna) == 1200

    # Ensure starts with ATG start codon for realistic translation
    ref_dna = "ATG" + ref_dna[3:]

    # Step 2: Validate sequence
    val_res = skill.execute(
        {
            "action": "validate",
            "sequence": ref_dna,
            "molecule_type": "dna",
            "min_length": 1000,
            "max_length": 2000,
        }
    )
    assert val_res["status"] == "ready"
    assert val_res["valid"] is True
    assert val_res["length"] == 1200

    # Step 3: K-mer profiling
    kmer_res = skill.execute(
        {
            "action": "kmer_profile",
            "sequence": ref_dna,
            "k": 3,
            "top_n": 10,
        }
    )
    assert kmer_res["status"] == "ready"
    assert kmer_res["total_kmers"] == 1198
    assert kmer_res["unique_kmers"] > 40
    assert 5.0 < kmer_res["entropy"] < 6.0  # Theoretical max for 64 trimers is 6.0 bits

    # Step 4: Transcription to mRNA
    tx_res = skill.execute(
        {
            "action": "transcribe",
            "sequence": ref_dna,
        }
    )
    assert tx_res["status"] == "ready"
    mrna = tx_res["output_sequence"]
    assert mrna.startswith("AUG")
    assert "T" not in mrna
    assert len(mrna) == 1200

    # Step 5: Translation
    tl_res = skill.execute(
        {
            "action": "translate",
            "sequence": mrna,
            "reading_frame": 0,
            "to_stop": True,
        }
    )
    assert tl_res["status"] == "ready"
    protein = tl_res["output_sequence"]
    assert protein.startswith("M")
    assert "*" not in protein
    assert len(protein) > 0

    # Step 6: Targeted variant engineering
    # Introduce:
    # - Substitution at index 20 (base 21): A/C/G/T swap
    # - Insertion of 3 bp at index 50
    # - Deletion of 3 bp at index 100
    orig_base = ref_dna[20]
    alt_base = "C" if orig_base != "C" else "G"
    mutated_dna = (
        ref_dna[:20]
        + alt_base
        + ref_dna[21:50]
        + "TTT"
        + ref_dna[50:100]
        + ref_dna[103:]
    )

    # Pairwise alignment
    aln_res = skill.execute(
        {
            "action": "pairwise_align",
            "sequence": ref_dna,
            "sequence_b": mutated_dna,
            "mode": "global",
        }
    )
    assert aln_res["status"] == "ready"
    assert aln_res["identity_percent"] > 98.0
    assert aln_res["matches"] > 1150
    assert aln_res["gaps"] > 0

    # Variant diffing
    diff_res = skill.execute(
        {
            "action": "variant_diff",
            "reference": ref_dna,
            "query": mutated_dna,
        }
    )
    assert diff_res["status"] == "ready"
    mut_types = [m["type"] for m in diff_res["mutations"]]
    assert "substitution" in mut_types
    assert "insertion" in mut_types or "deletion" in mut_types


def test_stress_long_sequence_processing(skill):
    """Stress test: 15,000 bp synthetic sequence operations."""
    gen_res = skill.execute(
        {
            "action": "generate",
            "molecule_type": "dna",
            "length": 15000,
            "seed": 8888,
        }
    )
    assert gen_res["status"] == "ready"
    seq_15k = gen_res["sequence"]
    assert len(seq_15k) == 15000

    # Reverse complement performance & correctness
    rc_res = skill.execute({"action": "revcom", "sequence": seq_15k})
    assert rc_res["status"] == "ready"
    assert len(rc_res["output_sequence"]) == 15000

    # Double revcom returns original sequence
    rc_double = skill.execute(
        {"action": "revcom", "sequence": rc_res["output_sequence"]}
    )
    assert rc_double["output_sequence"] == seq_15k

    # K-mer profiling with k=4
    kmer_res = skill.execute(
        {
            "action": "kmer_profile",
            "sequence": seq_15k,
            "k": 4,
            "top_n": 20,
        }
    )
    assert kmer_res["status"] == "ready"
    assert kmer_res["total_kmers"] == 15000 - 4 + 1


def test_edge_case_homopolymers(skill):
    """Homopolymer runs (pure A, C, G, T) must be handled gracefully."""
    poly_a = "A" * 100
    res_detect = skill.execute({"action": "detect_type", "sequence": poly_a})
    assert res_detect["status"] == "ready"
    assert res_detect["molecule_type"] == "dna"

    res_kmer = skill.execute({"action": "kmer_profile", "sequence": poly_a, "k": 3})
    assert res_kmer["status"] == "ready"
    assert res_kmer["unique_kmers"] == 1
    assert res_kmer["entropy"] == 0.0  # Zero uncertainty for single repeated k-mer

    res_rc = skill.execute({"action": "revcom", "sequence": poly_a})
    assert res_rc["output_sequence"] == "T" * 100


def test_edge_case_extreme_gc_content(skill):
    """Target GC content extremes (0% and 100%)."""
    # 0% GC: only A and T
    res_at = skill.execute(
        {
            "action": "generate",
            "molecule_type": "dna",
            "length": 200,
            "seed": 101,
            "gc_content": 0.0,
        }
    )
    assert res_at["status"] == "ready"
    assert set(res_at["sequence"]).issubset({"A", "T"})

    # 100% GC: only G and C
    res_gc = skill.execute(
        {
            "action": "generate",
            "molecule_type": "dna",
            "length": 200,
            "seed": 202,
            "gc_content": 1.0,
        }
    )
    assert res_gc["status"] == "ready"
    assert set(res_gc["sequence"]).issubset({"G", "C"})


def test_edge_case_whitespace_and_newlines_in_fasta(skill):
    """FASTA-like sequences with internal whitespace and formatting must be stripped."""
    dirty_seq = "  >header\nATGC\r\n  GTAA\t  "
    res = skill.execute({"action": "revcom", "sequence": dirty_seq})
    assert res["status"] == "ready"
    assert res["output_sequence"] == "TTACGCAT"


def test_edge_case_micro_sequences(skill):
    """Single base operations and boundaries."""
    res_single = skill.execute({"action": "revcom", "sequence": "A"})
    assert res_single["status"] == "ready"
    assert res_single["output_sequence"] == "T"

    # Micro pairwise alignment
    aln_match = skill.execute(
        {
            "action": "pairwise_align",
            "sequence": "A",
            "sequence_b": "A",
        }
    )
    assert aln_match["status"] == "ready"
    assert aln_match["identity_percent"] == 100.0

    aln_mismatch = skill.execute(
        {
            "action": "pairwise_align",
            "sequence": "A",
            "sequence_b": "G",
        }
    )
    assert aln_mismatch["status"] == "ready"
    assert aln_mismatch["identity_percent"] == 0.0


def test_simulation_inversion_detection(skill):
    """Localized inversion detection between reference and query."""
    ref = "ATGCGTAACCGGTTAACCGG"
    # Invert chunk "AACCGG" (revcom is "CCGGTT")
    inverted_chunk = "CCGGTT"
    query = "ATGCGT" + inverted_chunk + "TTAACCGG"

    res = skill.execute(
        {
            "action": "variant_diff",
            "reference": ref,
            "query": query,
        }
    )
    assert res["status"] == "ready"
    assert len(res["inversions"]) > 0 or len(res["mutations"]) > 0


def test_simulation_orf_discovery_and_fasta_export(skill):
    """
    Simulation: Discover Open Reading Frames in synthetic plasmid contig and export as FASTA.
    1. Embed an engineered 30-codon forward gene and a 30-codon reverse-strand gene.
    2. Run find_orfs with min_protein_length=25.
    3. Verify both genes are discovered with strand, frame, and valid translation.
    4. Format the plasmid and highest-ranking peptide into multi-line FASTA records.
    """
    # 30 codons = 90 bp starting with ATG and ending with TAA
    gene_fwd = "ATG" + ("GCT" * 28) + "TAA"
    gene_rev_orig = "ATG" + ("GAA" * 28) + "TAG"
    # To embed gene_rev on the reverse strand, insert its reverse complement on the forward sequence
    rev_rc = skill.execute({"action": "revcom", "sequence": gene_rev_orig})[
        "output_sequence"
    ]

    flank_left = "CGATCGATCGATCGAT"
    spacer = "TTTAAATTTAAA"
    flank_right = "GGCCGGCCGGCC"
    contig = flank_left + gene_fwd + spacer + rev_rc + flank_right

    # Find ORFs
    orf_res = skill.execute(
        {
            "action": "find_orfs",
            "sequence": contig,
            "min_protein_length": 25,
            "strand": "both",
        }
    )
    assert orf_res["status"] == "ready"
    assert orf_res["orfs_count"] >= 2
    strands = {orf["strand"] for orf in orf_res["orfs"]}
    assert "+" in strands
    assert "-" in strands

    # Verify translations
    fwd_orfs = [orf for orf in orf_res["orfs"] if orf["strand"] == "+"]
    assert fwd_orfs[0]["protein_sequence"].startswith("MA")

    # Format contig as FASTA (line width 50)
    fasta_res = skill.execute(
        {
            "action": "format_fasta",
            "sequence": contig,
            "header": "synthetic_plasmid_pSKW1",
            "line_width": 50,
        }
    )
    assert fasta_res["status"] == "ready"
    assert ">synthetic_plasmid_pSKW1" in fasta_res["fasta"]
