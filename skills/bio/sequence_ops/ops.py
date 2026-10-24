# Copyright (c) 2026 ARPA Hellenic Logical Systems
# SPDX-License-Identifier: MIT

"""Deterministic in-silico biological sequence operations engine."""

from __future__ import annotations

from collections import Counter
import json
import math
from pathlib import Path
import random
import re
from typing import Any, Dict, List, Optional, Set

from Bio.Align import PairwiseAligner
from Bio.Seq import Seq

# -----------------------------------------------------------------------------
# Knowledge Base Assets Cache
# -----------------------------------------------------------------------------

_KB_CACHE: Dict[str, Any] = {}


def get_kb_data(filename: str) -> Dict[str, Any]:
    """Retrieve and cache versioned JSON knowledge base assets."""
    if filename not in _KB_CACHE:
        kb_path = Path(__file__).resolve().parent / "kb" / filename
        if kb_path.is_file():
            with open(kb_path, "r", encoding="utf-8") as f:
                _KB_CACHE[filename] = json.load(f)
        else:
            _KB_CACHE[filename] = {}
    return _KB_CACHE[filename]


# -----------------------------------------------------------------------------
# Alphabet Constants
# -----------------------------------------------------------------------------

DNA_STANDARD_ALPHABET: Set[str] = set("ACGT")
DNA_IUPAC_ALPHABET: Set[str] = set("ACGTRYSWKMBDHVN-")

RNA_STANDARD_ALPHABET: Set[str] = set("ACGU")
RNA_IUPAC_ALPHABET: Set[str] = set("ACGURYSWKMBDHVN-")

PROTEIN_STANDARD_ALPHABET: Set[str] = set("ACDEFGHIKLMNPQRSTVWY")
PROTEIN_EXTENDED_ALPHABET: Set[str] = set("ACDEFGHIKLMNPQRSTVWYBZXJ*-")

PROTEIN_SPECIFIC_LETTERS: Set[str] = set("EFILPQZ")


def _clean_sequence(raw: Any) -> str:
    """Normalize input sequence by stripping FASTA headers, whitespace, and capitalizing."""
    if raw is None:
        return ""
    text = str(raw).strip()
    lines = text.splitlines()
    body_lines = [line.strip() for line in lines if not line.strip().startswith(">")]
    cleaned = "".join(body_lines)
    return re.sub(r"\s+", "", cleaned).upper()


def detect_molecule_type(seq: str) -> Dict[str, Any]:
    """
    Infer molecule type ('dna', 'rna', 'protein', or 'unknown') from sequence alphabet.

    Returns envelope with 'molecule_type', 'confidence', 'length', and 'alphabet_violations'.
    """
    clean = _clean_sequence(seq)
    if not clean:
        return {
            "status": "error",
            "action": "detect_type",
            "reason_codes": ["EMPTY_SEQUENCE"],
            "message": "Sequence cannot be empty.",
        }

    char_set = set(clean)
    has_t = "T" in char_set
    has_u = "U" in char_set
    has_protein_specific = bool(char_set & PROTEIN_SPECIFIC_LETTERS)

    # 1. Reject contradictory nucleotide states
    if has_t and has_u:
        return {
            "status": "ready",
            "action": "detect_type",
            "molecule_type": "unknown",
            "confidence": "low",
            "length": len(clean),
            "alphabet_violations": [
                "Mixed T and U nucleotide bases in single sequence."
            ],
        }

    # 2. Protein-specific indicators
    if has_protein_specific:
        invalid = char_set - PROTEIN_EXTENDED_ALPHABET
        if not invalid:
            return {
                "status": "ready",
                "action": "detect_type",
                "molecule_type": "protein",
                "confidence": "high",
                "length": len(clean),
                "alphabet_violations": [],
            }
        return {
            "status": "ready",
            "action": "detect_type",
            "molecule_type": "unknown",
            "confidence": "low",
            "length": len(clean),
            "alphabet_violations": [
                f"Invalid character(s) for protein: {sorted(list(invalid))}"
            ],
        }

    # 3. RNA detection (contains U, no T, no protein-specific)
    if has_u:
        invalid = char_set - RNA_IUPAC_ALPHABET
        if not invalid:
            conf = "high" if char_set.issubset(RNA_STANDARD_ALPHABET) else "medium"
            return {
                "status": "ready",
                "action": "detect_type",
                "molecule_type": "rna",
                "confidence": conf,
                "length": len(clean),
                "alphabet_violations": [],
            }
        return {
            "status": "ready",
            "action": "detect_type",
            "molecule_type": "unknown",
            "confidence": "low",
            "length": len(clean),
            "alphabet_violations": [
                f"Invalid character(s) for RNA: {sorted(list(invalid))}"
            ],
        }

    # 4. DNA detection (contains T, no U, no protein-specific)
    if has_t:
        invalid = char_set - DNA_IUPAC_ALPHABET
        if not invalid:
            conf = "high" if char_set.issubset(DNA_STANDARD_ALPHABET) else "medium"
            return {
                "status": "ready",
                "action": "detect_type",
                "molecule_type": "dna",
                "confidence": conf,
                "length": len(clean),
                "alphabet_violations": [],
            }
        return {
            "status": "ready",
            "action": "detect_type",
            "molecule_type": "unknown",
            "confidence": "low",
            "length": len(clean),
            "alphabet_violations": [
                f"Invalid character(s) for DNA: {sorted(list(invalid))}"
            ],
        }

    # 5. Ambiguous A, C, G, N nucleotide string
    if char_set.issubset(set("ACGN-")):
        return {
            "status": "ready",
            "action": "detect_type",
            "molecule_type": "dna",
            "confidence": "medium",
            "length": len(clean),
            "alphabet_violations": [],
        }

    # 6. Check if it's a valid protein without protein-specific letters
    if char_set.issubset(PROTEIN_EXTENDED_ALPHABET):
        return {
            "status": "ready",
            "action": "detect_type",
            "molecule_type": "protein",
            "confidence": "medium",
            "length": len(clean),
            "alphabet_violations": [],
        }

    invalid_chars = char_set - (
        DNA_IUPAC_ALPHABET | RNA_IUPAC_ALPHABET | PROTEIN_EXTENDED_ALPHABET
    )
    return {
        "status": "ready",
        "action": "detect_type",
        "molecule_type": "unknown",
        "confidence": "low",
        "length": len(clean),
        "alphabet_violations": [
            f"Unrecognized sequence character(s): {sorted(list(invalid_chars))}"
        ],
    }


def validate_sequence(
    seq: str,
    molecule_type: Optional[str] = None,
    min_length: int = 1,
    max_length: int = 1_000_000,
    allow_ambiguous: bool = True,
) -> Dict[str, Any]:
    """Validate character alphabet, ambiguity permissions, and length bounds."""
    clean = _clean_sequence(seq)
    errors: List[str] = []
    reason_codes: List[str] = []

    if not clean:
        return {
            "status": "ready",
            "action": "validate",
            "valid": False,
            "molecule_type": molecule_type or "unknown",
            "length": 0,
            "errors": ["Sequence cannot be empty."],
            "reason_codes": ["EMPTY_SEQUENCE", "MISSING_INPUT"],
        }

    if len(clean) < min_length:
        reason_codes.append("LENGTH_OUT_OF_BOUNDS")
        errors.append(
            f"Sequence length {len(clean)} is below minimum required length {min_length}."
        )
    if len(clean) > max_length:
        reason_codes.append("LENGTH_OUT_OF_BOUNDS")
        errors.append(
            f"Sequence length {len(clean)} exceeds maximum permitted length {max_length}."
        )

    inferred_mtype = molecule_type.strip().lower() if molecule_type else None
    if not inferred_mtype:
        detect_res = detect_molecule_type(clean)
        inferred_mtype = detect_res.get("molecule_type", "unknown")
        if inferred_mtype == "unknown":
            reason_codes.append("INVALID_ALPHABET")
            errors.extend(
                detect_res.get(
                    "alphabet_violations", ["Could not infer valid molecule type."]
                )
            )

    char_set = set(clean)
    if inferred_mtype == "dna":
        valid_set = DNA_IUPAC_ALPHABET if allow_ambiguous else DNA_STANDARD_ALPHABET
        invalid = char_set - valid_set
        if invalid:
            reason_codes.append("INVALID_ALPHABET")
            errors.append(f"Invalid DNA base(s) detected: {sorted(list(invalid))}.")
    elif inferred_mtype == "rna":
        valid_set = RNA_IUPAC_ALPHABET if allow_ambiguous else RNA_STANDARD_ALPHABET
        invalid = char_set - valid_set
        if invalid:
            reason_codes.append("INVALID_ALPHABET")
            errors.append(f"Invalid RNA base(s) detected: {sorted(list(invalid))}.")
    elif inferred_mtype == "protein":
        valid_set = (
            PROTEIN_EXTENDED_ALPHABET if allow_ambiguous else PROTEIN_STANDARD_ALPHABET
        )
        invalid = char_set - valid_set
        if invalid:
            reason_codes.append("INVALID_ALPHABET")
            errors.append(
                f"Invalid amino acid residue(s) detected: {sorted(list(invalid))}."
            )
    elif inferred_mtype != "unknown":
        reason_codes.append("UNSUPPORTED_MOLECULE_TYPE")
        errors.append(
            f"Unsupported molecule_type '{inferred_mtype}'. Must be 'dna', 'rna', or 'protein'."
        )

    return {
        "status": "ready",
        "action": "validate",
        "valid": len(errors) == 0,
        "molecule_type": inferred_mtype,
        "length": len(clean),
        "errors": errors,
        "reason_codes": sorted(list(set(reason_codes))),
    }


def reverse_complement_dna(
    seq: str, molecule_type: Optional[str] = None
) -> Dict[str, Any]:
    """Compute reverse complement for DNA sequences."""
    clean = _clean_sequence(seq)
    if not clean:
        return {
            "status": "error",
            "action": "revcom",
            "reason_codes": ["EMPTY_SEQUENCE", "MISSING_INPUT"],
            "message": "Sequence cannot be empty.",
        }

    detected = detect_molecule_type(clean)
    mtype = (molecule_type or detected.get("molecule_type", "")).strip().lower()
    if mtype != "dna" or "U" in clean or set(clean) & PROTEIN_SPECIFIC_LETTERS:
        return {
            "status": "error",
            "action": "revcom",
            "reason_codes": ["UNSUPPORTED_MOLECULE_TYPE"],
            "message": "revcom requires DNA input",
        }

    output = str(Seq(clean).reverse_complement())
    return {
        "status": "ready",
        "action": "revcom",
        "input_sequence": clean,
        "output_sequence": output,
        "molecule_type": "dna",
        "length": len(output),
    }


def transcribe_to_rna(seq: str) -> Dict[str, Any]:
    """Transcribe DNA sequence to RNA by converting thymine (T) to uracil (U)."""
    clean = _clean_sequence(seq)
    if not clean:
        return {
            "status": "error",
            "action": "transcribe",
            "reason_codes": ["EMPTY_SEQUENCE"],
            "message": "Sequence cannot be empty.",
        }

    detected = detect_molecule_type(clean)
    if detected.get("molecule_type") == "protein":
        return {
            "status": "error",
            "action": "transcribe",
            "reason_codes": ["UNSUPPORTED_MOLECULE_TYPE"],
            "message": "transcribe requires nucleotide input (DNA or RNA)",
        }

    # If already RNA (has U and no T), pass through
    if "U" in clean and "T" not in clean:
        return {
            "status": "ready",
            "action": "transcribe",
            "input_sequence": clean,
            "output_sequence": clean,
            "molecule_type": "rna",
            "length": len(clean),
        }

    output = str(Seq(clean).transcribe())
    return {
        "status": "ready",
        "action": "transcribe",
        "input_sequence": clean,
        "output_sequence": output,
        "molecule_type": "rna",
        "length": len(output),
    }


def translate_sequence(
    seq: str,
    reading_frame: int = 0,
    to_stop: bool = False,
    table_id: int = 1,
) -> Dict[str, Any]:
    """Translate DNA or RNA sequence into amino acid protein string."""
    clean = _clean_sequence(seq)
    if not clean:
        return {
            "status": "error",
            "action": "translate",
            "reason_codes": ["EMPTY_SEQUENCE", "MISSING_INPUT"],
            "message": "Sequence cannot be empty.",
        }

    if reading_frame not in (0, 1, 2):
        return {
            "status": "error",
            "action": "translate",
            "reason_codes": ["INVALID_READING_FRAME"],
            "message": f"Invalid reading_frame {reading_frame}. Must be 0, 1, or 2.",
        }

    subseq = clean[reading_frame:]
    trailing = len(subseq) % 3
    if trailing:
        subseq = subseq[:-trailing]

    if not subseq:
        return {
            "status": "ready",
            "action": "translate",
            "input_sequence": clean,
            "output_sequence": "",
            "molecule_type": "protein",
            "reading_frame": reading_frame,
            "table_id": table_id,
            "length": 0,
            "stop_codons_count": 0,
        }

    # Bio.Seq translation
    bio_seq = Seq(subseq)
    try:
        translated = str(bio_seq.translate(table=table_id, to_stop=to_stop))
    except Exception as exc:
        return {
            "status": "error",
            "action": "translate",
            "reason_codes": ["INVALID_GENETIC_CODE_TABLE"],
            "message": f"Invalid genetic code table {table_id}: {exc}",
        }
    stop_count = translated.count("*")

    return {
        "status": "ready",
        "action": "translate",
        "input_sequence": clean,
        "output_sequence": translated,
        "molecule_type": "protein",
        "reading_frame": reading_frame,
        "table_id": table_id,
        "length": len(translated),
        "stop_codons_count": stop_count,
    }


def pairwise_alignment(
    seq_a: str,
    seq_b: str,
    mode: str = "global",
) -> Dict[str, Any]:
    """Perform deterministic pairwise alignment using Biopython PairwiseAligner."""
    clean_a = _clean_sequence(seq_a)
    clean_b = _clean_sequence(seq_b)

    if not clean_a or not clean_b:
        return {
            "status": "error",
            "action": "pairwise_align",
            "reason_codes": ["EMPTY_SEQUENCE", "MISSING_INPUT"],
            "message": "Both sequence and sequence_b must be non-empty strings.",
        }

    norm_mode = mode.strip().lower()
    if norm_mode not in ("global", "local"):
        return {
            "status": "error",
            "action": "pairwise_align",
            "reason_codes": ["INVALID_ALIGNMENT_MODE"],
            "message": f"Unsupported alignment mode '{mode}'. Must be 'global' or 'local'.",
        }

    aligner = PairwiseAligner()
    aligner.mode = norm_mode

    alignments = aligner.align(clean_a, clean_b)
    if not alignments:
        return {
            "status": "ready",
            "action": "pairwise_align",
            "mode": norm_mode,
            "score": 0.0,
            "identity_percent": 0.0,
            "matches": 0,
            "mismatches": 0,
            "gaps": 0,
            "alignment_length": 0,
            "alignment_a": "",
            "alignment_b": "",
        }

    best_aln = alignments[0]
    aligned_a = best_aln[0]
    aligned_b = best_aln[1]

    matches = sum(1 for a, b in zip(aligned_a, aligned_b) if a == b and a != "-")
    gaps = sum(1 for a, b in zip(aligned_a, aligned_b) if a == "-" or b == "-")
    mismatches = sum(
        1 for a, b in zip(aligned_a, aligned_b) if a != b and a != "-" and b != "-"
    )
    total_aligned = len(aligned_a)
    identity_percent = (
        round((matches / total_aligned) * 100, 2) if total_aligned else 0.0
    )

    return {
        "status": "ready",
        "action": "pairwise_align",
        "mode": norm_mode,
        "score": float(best_aln.score),
        "identity_percent": identity_percent,
        "matches": matches,
        "mismatches": mismatches,
        "gaps": gaps,
        "alignment_length": total_aligned,
        "alignment_a": aligned_a,
        "alignment_b": aligned_b,
    }


def variant_diffing(
    reference: str,
    query: str,
    ref_id: str = "ref",
    query_id: str = "query",
    min_length: int = 1,
) -> Dict[str, Any]:
    """Call sequence mutations (substitutions, insertions, deletions) vs. reference."""
    clean_ref = _clean_sequence(reference)
    clean_query = _clean_sequence(query)

    if not clean_ref or not clean_query:
        return {
            "status": "error",
            "action": "variant_diff",
            "reason_codes": ["EMPTY_SEQUENCE", "MISSING_INPUT"],
            "message": "Both reference and query sequences must be non-empty.",
        }

    # Align ref and query
    aligner = PairwiseAligner()
    aligner.mode = "global"
    alignments = aligner.align(clean_ref, clean_query)
    best_aln = alignments[0]
    aln_ref = best_aln[0]
    aln_query = best_aln[1]

    mutations: List[Dict[str, Any]] = []
    ref_pos = 1

    i = 0
    while i < len(aln_ref):
        r = aln_ref[i]
        q = aln_query[i]

        if r != "-" and q != "-":
            if r != q:
                mutations.append(
                    {
                        "type": "substitution",
                        "position": ref_pos,
                        "ref": r,
                        "alt": q,
                    }
                )
            ref_pos += 1
            i += 1
        elif r == "-" and q != "-":
            # Insertion in query
            ins_bases = [q]
            j = i + 1
            while j < len(aln_ref) and aln_ref[j] == "-" and aln_query[j] != "-":
                ins_bases.append(aln_query[j])
                j += 1
            ins_str = "".join(ins_bases)
            mutations.append(
                {
                    "type": "insertion",
                    "position": ref_pos,
                    "length": len(ins_str),
                    "alt": ins_str,
                }
            )
            i = j
        elif r != "-" and q == "-":
            # Deletion from reference
            del_bases = [r]
            start_pos = ref_pos
            ref_pos += 1
            j = i + 1
            while j < len(aln_ref) and aln_ref[j] != "-" and aln_query[j] == "-":
                del_bases.append(aln_ref[j])
                ref_pos += 1
                j += 1
            del_str = "".join(del_bases)
            mutations.append(
                {
                    "type": "deletion",
                    "position": start_pos,
                    "length": len(del_str),
                    "ref": del_str,
                }
            )
            i = j
        else:
            i += 1

    # Check for potential inversion blocks
    inversions: List[Dict[str, Any]] = []
    if len(clean_ref) >= 6 and len(clean_query) >= 6:
        # Check if query contains inverted/reverse-complement chunks of reference >= 6 bp
        for w in (12, 8, 6):
            if w <= len(clean_ref):
                for k in range(len(clean_ref) - w + 1):
                    sub = clean_ref[k : k + w]
                    rev_sub = (
                        str(Seq(sub).reverse_complement())
                        if "U" not in sub and not (set(sub) & PROTEIN_SPECIFIC_LETTERS)
                        else sub[::-1]
                    )
                    if rev_sub in clean_query and sub not in clean_query:
                        inv_pos = clean_query.find(rev_sub) + 1
                        inversions.append(
                            {
                                "type": "inversion",
                                "reference_position": k + 1,
                                "query_position": inv_pos,
                                "length": w,
                                "sequence": rev_sub,
                            }
                        )
                        break
            if inversions:
                break

    return {
        "status": "ready",
        "action": "variant_diff",
        "reference_id": ref_id,
        "query_id": query_id,
        "reference_length": len(clean_ref),
        "query_length": len(clean_query),
        "mutations_count": len(mutations),
        "mutations": mutations,
        "inversions": inversions,
    }


def calculate_kmer_profile(
    seq: str,
    k: int = 3,
    top_n: int = 10,
) -> Dict[str, Any]:
    """Profile k-mer frequency counts, unique counts, and Shannon entropy."""
    clean = _clean_sequence(seq)
    if not clean:
        return {
            "status": "error",
            "action": "kmer_profile",
            "reason_codes": ["EMPTY_SEQUENCE"],
            "message": "Sequence cannot be empty.",
        }

    if k < 1:
        return {
            "status": "error",
            "action": "kmer_profile",
            "reason_codes": ["INVALID_K_VALUE"],
            "message": "k must be a positive integer >= 1.",
        }

    if len(clean) < k:
        return {
            "status": "error",
            "action": "kmer_profile",
            "reason_codes": ["SEQUENCE_TOO_SHORT"],
            "message": f"Sequence length {len(clean)} is shorter than k-mer window {k}.",
        }

    kmers = [clean[i : i + k] for i in range(len(clean) - k + 1)]
    total_kmers = len(kmers)
    counts = Counter(kmers)
    unique_kmers = len(counts)

    # Shannon entropy
    entropy = 0.0
    for count in counts.values():
        p = count / total_kmers
        entropy -= p * math.log2(p)
    entropy = round(entropy, 4)

    # Top-N k-mers
    top_list: List[Dict[str, Any]] = []
    for kmer, count in counts.most_common(top_n):
        top_list.append(
            {
                "kmer": kmer,
                "count": count,
                "frequency": round(count / total_kmers, 4),
            }
        )

    return {
        "status": "ready",
        "action": "kmer_profile",
        "k": k,
        "total_kmers": total_kmers,
        "unique_kmers": unique_kmers,
        "entropy": entropy,
        "top_kmers": top_list,
    }


def generate_sequence(
    molecule_type: str = "dna",
    length: int = 100,
    seed: int = 42,
    gc_content: Optional[float] = None,
) -> Dict[str, Any]:
    """Generate reproducible pseudo-random sequence with fixed seed for tests."""
    mtype = molecule_type.strip().lower()
    if mtype not in ("dna", "rna", "protein"):
        return {
            "status": "error",
            "action": "generate",
            "reason_codes": ["INVALID_MOLECULE_TYPE"],
            "message": f"Unsupported molecule_type '{molecule_type}'. Must be 'dna', 'rna', or 'protein'.",
        }

    if length < 1 or length > 1_000_000:
        return {
            "status": "error",
            "action": "generate",
            "reason_codes": ["INVALID_LENGTH"],
            "message": f"length must be between 1 and 1,000,000 (requested {length}).",
        }

    rng = random.Random(seed)

    if mtype in ("dna", "rna"):
        t_or_u = "T" if mtype == "dna" else "U"
        bases = ["A", "C", "G", t_or_u]
        if gc_content is not None:
            gc = max(0.0, min(1.0, float(gc_content)))
            at = 1.0 - gc
            weights = [at / 2.0, gc / 2.0, gc / 2.0, at / 2.0]
            sampled = rng.choices(bases, weights=weights, k=length)
        else:
            sampled = rng.choices(bases, k=length)
    else:
        # 20 standard amino acids
        aa_list = sorted(list(PROTEIN_STANDARD_ALPHABET))
        sampled = rng.choices(aa_list, k=length)

    generated_str = "".join(sampled)
    return {
        "status": "ready",
        "action": "generate",
        "molecule_type": mtype,
        "length": len(generated_str),
        "seed": seed,
        "sequence": generated_str,
    }


def find_orfs(
    seq: str,
    min_protein_length: int = 30,
    table_id: int = 1,
    strand: str = "both",
) -> Dict[str, Any]:
    """
    Identify Open Reading Frames (ORFs) across forward and reverse reading frames.

    Scans reading frames for valid start codons (ATG/AUG) and downstream in-frame stop
    codons, translating candidate coding sequences.
    """
    clean = _clean_sequence(seq)
    if not clean:
        return {
            "status": "error",
            "action": "find_orfs",
            "reason_codes": ["EMPTY_SEQUENCE", "MISSING_INPUT"],
            "message": "Sequence cannot be empty.",
        }

    detected = detect_molecule_type(clean)
    mtype = detected.get("molecule_type", "dna")
    if mtype == "protein":
        return {
            "status": "error",
            "action": "find_orfs",
            "reason_codes": ["UNSUPPORTED_MOLECULE_TYPE"],
            "message": "find_orfs requires nucleotide sequence (DNA or RNA), not protein.",
        }

    valid_strands = ("both", "forward", "reverse")
    norm_strand = strand.strip().lower() if strand else "both"
    if norm_strand not in valid_strands:
        return {
            "status": "error",
            "action": "find_orfs",
            "reason_codes": ["INVALID_STRAND"],
            "message": f"Invalid strand '{strand}'. Must be 'both', 'forward', or 'reverse'.",
        }

    # Load genetic code table definitions from KB
    codes_data = get_kb_data("genetic_codes.json")
    table_info = codes_data.get("tables", {}).get(str(table_id))
    if table_info:
        start_codons = set(table_info.get("start_codons", ["ATG", "AUG"]))
        stop_codons = set(
            table_info.get("stop_codons", ["TAA", "TAG", "TGA", "UAA", "UAG", "UGA"])
        )
    else:
        # Standard NCBI Table 1 fallback
        start_codons = {"ATG", "AUG"}
        stop_codons = {"TAA", "TAG", "TGA", "UAA", "UAG", "UGA"}

    orfs: List[Dict[str, Any]] = []
    seq_len = len(clean)

    # 1. Forward strand (+1, +2, +3)
    if norm_strand in ("both", "forward"):
        for frame in (0, 1, 2):
            i = frame
            while i + 3 <= seq_len:
                codon = clean[i : i + 3]
                if codon in start_codons:
                    start_idx = i
                    stop_found = False
                    j = start_idx + 3
                    while j + 3 <= seq_len:
                        test_codon = clean[j : j + 3]
                        if test_codon in stop_codons:
                            stop_found = True
                            orf_nt = clean[start_idx:j]
                            aa_len = len(orf_nt) // 3
                            if aa_len >= min_protein_length:
                                bio_seq = Seq(orf_nt)
                                prot = str(bio_seq.translate(table=table_id))
                                orfs.append(
                                    {
                                        "id": f"orf_{len(orfs) + 1}",
                                        "frame": f"+{frame + 1}",
                                        "strand": "+",
                                        "start": start_idx + 1,
                                        "end": j + 3,
                                        "nucleotide_length": (j + 3) - start_idx,
                                        "protein_length": aa_len,
                                        "start_codon": codon,
                                        "stop_codon": test_codon,
                                        "protein_sequence": prot,
                                        "nucleotide_sequence": clean[start_idx : j + 3],
                                    }
                                )
                            i = j
                            break
                        j += 3
                    if not stop_found:
                        break
                i += 3

    # 2. Reverse strand (-1, -2, -3) for DNA
    if norm_strand in ("both", "reverse") and mtype != "rna":
        revcom = str(Seq(clean).reverse_complement())
        for frame in (0, 1, 2):
            i = frame
            while i + 3 <= seq_len:
                codon = revcom[i : i + 3]
                if codon in start_codons:
                    start_idx = i
                    stop_found = False
                    j = start_idx + 3
                    while j + 3 <= seq_len:
                        test_codon = revcom[j : j + 3]
                        if test_codon in stop_codons:
                            stop_found = True
                            orf_nt = revcom[start_idx:j]
                            aa_len = len(orf_nt) // 3
                            if aa_len >= min_protein_length:
                                bio_seq = Seq(orf_nt)
                                prot = str(bio_seq.translate(table=table_id))
                                orig_end = seq_len - start_idx
                                orig_start = seq_len - (j + 3) + 1
                                orfs.append(
                                    {
                                        "id": f"orf_{len(orfs) + 1}",
                                        "frame": f"-{frame + 1}",
                                        "strand": "-",
                                        "start": orig_start,
                                        "end": orig_end,
                                        "nucleotide_length": (j + 3) - start_idx,
                                        "protein_length": aa_len,
                                        "start_codon": codon,
                                        "stop_codon": test_codon,
                                        "protein_sequence": prot,
                                        "nucleotide_sequence": revcom[
                                            start_idx : j + 3
                                        ],
                                    }
                                )
                            i = j
                            break
                        j += 3
                    if not stop_found:
                        break
                i += 3

    # Sort ORFs by protein length descending
    orfs.sort(key=lambda x: x["protein_length"], reverse=True)
    for idx, orf in enumerate(orfs, start=1):
        orf["id"] = f"orf_{idx}"

    return {
        "status": "ready",
        "action": "find_orfs",
        "molecule_type": mtype,
        "sequence_length": seq_len,
        "table_id": table_id,
        "min_protein_length": min_protein_length,
        "orfs_count": len(orfs),
        "orfs": orfs,
    }


def format_fasta(
    seq: str,
    header: str = "sequence",
    line_width: int = 60,
) -> Dict[str, Any]:
    """Format biological sequence string as a standard multi-line FASTA record."""
    clean = _clean_sequence(seq)
    if not clean:
        return {
            "status": "error",
            "action": "format_fasta",
            "reason_codes": ["EMPTY_SEQUENCE", "MISSING_INPUT"],
            "message": "Sequence cannot be empty.",
        }

    clean_header = str(header or "sequence").strip()
    if clean_header.startswith(">"):
        clean_header = clean_header[1:].strip()

    width = max(10, min(1000, int(line_width)))
    lines = [f">{clean_header}"]
    for i in range(0, len(clean), width):
        lines.append(clean[i : i + width])

    fasta_text = "\n".join(lines) + "\n"
    return {
        "status": "ready",
        "action": "format_fasta",
        "header": clean_header,
        "length": len(clean),
        "line_width": width,
        "fasta": fasta_text,
    }


def list_genetic_tables() -> Dict[str, Any]:
    """List all supported NCBI genetic code tables bundled in the knowledge base."""
    codes_data = get_kb_data("genetic_codes.json")
    tables_list = []
    for tid, info in sorted(
        codes_data.get("tables", {}).items(), key=lambda x: int(x[0])
    ):
        tables_list.append(
            {
                "table_id": int(tid),
                "name": info.get("name"),
                "description": info.get("description"),
                "start_codons": info.get("start_codons", []),
                "stop_codons": info.get("stop_codons", []),
            }
        )
    return {
        "status": "ready",
        "action": "list_tables",
        "tables_count": len(tables_list),
        "tables": tables_list,
    }


def lookup_iupac_code(code: str) -> Dict[str, Any]:
    """Look up biological notation details for a single nucleotide or amino acid code."""
    if not code or not str(code).strip():
        return {
            "status": "error",
            "action": "lookup_iupac",
            "reason_codes": ["MISSING_INPUT"],
            "message": "code parameter cannot be empty.",
        }

    clean_code = str(code).strip().upper()
    iupac_data = get_kb_data("iupac_codes.json")
    amino_data = get_kb_data("amino_acids.json")

    # Check nucleotide
    nt_info = iupac_data.get("nucleotides", {}).get(clean_code)
    # Check amino acid
    aa_info = iupac_data.get("amino_acids", {}).get(clean_code)
    aa_props = amino_data.get("standard_amino_acids", {}).get(clean_code)

    if not nt_info and not aa_info:
        return {
            "status": "error",
            "action": "lookup_iupac",
            "reason_codes": ["UNKNOWN_CODE"],
            "message": f"Code '{clean_code}' not found in IUPAC standard nucleotide or amino acid tables.",
        }

    return {
        "status": "ready",
        "action": "lookup_iupac",
        "code": clean_code,
        "nucleotide": nt_info,
        "amino_acid": aa_info,
        "biophysical_properties": aa_props,
    }
