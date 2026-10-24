#!/usr/bin/env python3
# Copyright (c) 2026 ARPA Hellenic Logical Systems
# SPDX-License-Identifier: MIT

"""
bio_sequence_ops_demo.py

Offline demonstration of deterministic in-silico life sciences operations using
the bio/sequence_ops foundational skill bundle.
"""

from __future__ import annotations

import json
from skillware.core.loader import SkillLoader


def main() -> None:
    print("=" * 70)
    print("Skillware: bio/sequence_ops In-Silico Demo")
    print("=" * 70)

    # 1. Load skill bundle
    bundle = SkillLoader.load_skill("bio/sequence_ops")
    skill = bundle["class"]()
    print(
        f"Loaded skill: {bundle['manifest']['name']} (v{bundle['manifest']['version']})"
    )
    print(
        f"Target: {bundle['manifest']['target']} | Tier: {bundle['manifest']['tier']}"
    )
    print("-" * 70)

    # 2. Sequence Type Detection and Validation
    raw_dna = "ATGGCCATTGTAATGGGCCGCTGAAAGGGTGCCCGATAG"
    print(f"1. Primary DNA construct: {raw_dna}")
    type_res = skill.execute({"action": "detect_type", "sequence": raw_dna})
    print(
        f"   Inferred Type: {type_res['molecule_type']} (confidence: {type_res['confidence']})"
    )

    val_res = skill.execute(
        {
            "action": "validate",
            "sequence": raw_dna,
            "molecule_type": "dna",
            "min_length": 10,
            "max_length": 500,
        }
    )
    print(
        f"   Validation status: valid={val_res['valid']}, length={val_res['length']} bp"
    )
    print("-" * 70)

    # 3. Molecular Transforms: Transcription, Translation, Reverse Complement
    print("2. Molecular Transforms:")
    mrna_res = skill.execute({"action": "transcribe", "sequence": raw_dna})
    print(f"   mRNA transcript (T->U): {mrna_res['output_sequence']}")

    protein_res = skill.execute(
        {
            "action": "translate",
            "sequence": raw_dna,
            "reading_frame": 0,
            "to_stop": True,
        }
    )
    print(f"   Translated peptide (frame 0, to stop): {protein_res['output_sequence']}")

    revcom_res = skill.execute({"action": "revcom", "sequence": raw_dna})
    print(f"   Reverse complement (5'->3'): {revcom_res['output_sequence'][:20]}...")
    print("-" * 70)

    # 4. Pairwise Alignment & Variant Diffing
    mutated_dna = (
        "ATGGCCATTGTAATGGGGCGCTGAAAGGGTGCCCGATAG"  # G substituted at index 19 (C->G)
    )
    print("3. Pairwise Alignment & Mutation Calling:")
    print(f"   Query sequence: {mutated_dna}")
    aln_res = skill.execute(
        {
            "action": "pairwise_align",
            "sequence": raw_dna,
            "sequence_b": mutated_dna,
            "mode": "global",
        }
    )
    print(
        f"   Alignment score: {aln_res['score']}, identity: {aln_res['identity_percent']}%"
    )
    print(
        f"   Matches: {aln_res['matches']}, Mismatches: {aln_res['mismatches']}, Gaps: {aln_res['gaps']}"
    )

    diff_res = skill.execute(
        {
            "action": "variant_diff",
            "reference": raw_dna,
            "query": mutated_dna,
        }
    )
    print(f"   Mutations called: {json.dumps(diff_res['mutations'], indent=2)}")
    print("-" * 70)

    # 5. K-mer Profiling & Shannon Entropy
    print("4. Trinucleotide K-mer Profiling (k=3):")
    kmer_res = skill.execute(
        {
            "action": "kmer_profile",
            "sequence": raw_dna,
            "k": 3,
            "top_n": 5,
        }
    )
    print(
        f"   Total 3-mers: {kmer_res['total_kmers']}, Unique: {kmer_res['unique_kmers']}"
    )
    print(f"   Shannon entropy: {kmer_res['entropy']} bits")
    print(f"   Top 5 k-mers: {kmer_res['top_kmers']}")
    print("-" * 70)

    # 6. Open Reading Frame (ORF) Discovery & FASTA Export
    print("5. 6-Frame Open Reading Frame Discovery & FASTA Formatting:")
    orf_res = skill.execute(
        {
            "action": "find_orfs",
            "sequence": raw_dna,
            "min_protein_length": 5,
            "strand": "both",
        }
    )
    print(f"   Identified ORFs count: {orf_res['orfs_count']}")
    if orf_res["orfs"]:
        top_orf = orf_res["orfs"][0]
        print(
            f"   Top ORF ({top_orf['id']}): frame={top_orf['frame']}, span={top_orf['start']}..{top_orf['end']} bp"
        )
        print(
            f"   Protein: {top_orf['protein_sequence']} ({top_orf['protein_length']} aa)"
        )

    fasta_res = skill.execute(
        {
            "action": "format_fasta",
            "sequence": raw_dna,
            "header": "synthetic_construct_alpha",
            "line_width": 20,
        }
    )
    print("   Formatted FASTA representation:")
    for line in fasta_res["fasta"].strip().split("\n"):
        print(f"     {line}")
    print("-" * 70)

    print("Bio sequence operations demo completed successfully.")


if __name__ == "__main__":
    main()
