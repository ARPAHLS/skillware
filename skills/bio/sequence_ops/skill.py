# Copyright (c) 2026 ARPA Hellenic Logical Systems
# SPDX-License-Identifier: MIT

"""Effect implementation for bio/sequence_ops."""

from __future__ import annotations

import os
from pathlib import Path
import sys
from typing import Any, Dict, Optional

import yaml

from skillware.core.base_skill import BaseSkill

try:
    from . import ops
except ImportError:  # pragma: no cover
    sys.path.insert(0, os.path.dirname(__file__))
    import ops


class SequenceOpsSkill(BaseSkill):
    """Deterministic in-silico operations on DNA, RNA, and protein sequence strings."""

    @property
    def manifest(self) -> Dict[str, Any]:
        manifest_path = Path(__file__).resolve().parent / "manifest.yaml"
        if manifest_path.is_file():
            with open(manifest_path, "r", encoding="utf-8") as handle:
                data = yaml.safe_load(handle)
                if isinstance(data, dict):
                    return data
        return {
            "name": "bio/sequence_ops",
            "version": "0.1.0",
        }

    def execute(
        self,
        params: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Execute in-silico biological sequence operation.

        Supports positional dictionary (e.g. execute({"action": "..."})),
        nested params envelope (e.g. execute(params={...})),
        and direct kwargs (e.g. execute(action="...", sequence="...")).
        """
        merged_params: Dict[str, Any] = {}
        if isinstance(params, dict):
            merged_params.update(params)
        nested = kwargs.get("params")
        if isinstance(nested, dict):
            merged_params.update(nested)
        for k, v in kwargs.items():
            if k != "params" and v is not None:
                merged_params[k] = v

        action = str(merged_params.get("action") or "detect_type").strip().lower()

        # Parameter aliases resolution
        seq = (
            merged_params.get("sequence")
            or merged_params.get("seq")
            or merged_params.get("input_sequence")
            or merged_params.get("reference")
            or merged_params.get("sequence_a")
        )
        seq_b = (
            merged_params.get("sequence_b")
            or merged_params.get("query")
            or merged_params.get("target_sequence")
        )

        if action in ("detect_type", "type_detect", "detect"):
            return ops.detect_molecule_type(seq)

        if action == "validate":
            return ops.validate_sequence(
                seq=seq,
                molecule_type=merged_params.get("molecule_type"),
                min_length=int(merged_params.get("min_length", 1)),
                max_length=int(merged_params.get("max_length", 1_000_000)),
                allow_ambiguous=bool(merged_params.get("allow_ambiguous", True)),
            )

        if action in ("revcom", "reverse_complement"):
            return ops.reverse_complement_dna(
                seq=seq,
                molecule_type=merged_params.get("molecule_type"),
            )

        if action == "transcribe":
            return ops.transcribe_to_rna(seq=seq)

        if action == "translate":
            table_val = merged_params.get("table") or merged_params.get("table_id") or 1
            return ops.translate_sequence(
                seq=seq,
                reading_frame=int(merged_params.get("reading_frame", 0)),
                to_stop=bool(merged_params.get("to_stop", False)),
                table_id=int(table_val),
            )

        if action in ("pairwise_align", "align"):
            return ops.pairwise_alignment(
                seq_a=seq,
                seq_b=seq_b,
                mode=str(merged_params.get("mode") or "global"),
            )

        if action in ("variant_diff", "diff", "mutations"):
            return ops.variant_diffing(
                reference=seq,
                query=seq_b,
                ref_id=str(merged_params.get("reference_id") or "ref"),
                query_id=str(merged_params.get("query_id") or "query"),
            )

        if action in ("kmer_profile", "kmer", "kmers"):
            return ops.calculate_kmer_profile(
                seq=seq,
                k=int(merged_params.get("k", 3)),
                top_n=int(merged_params.get("top_n", 10)),
            )

        if action == "generate":
            return ops.generate_sequence(
                molecule_type=str(merged_params.get("molecule_type") or "dna"),
                length=int(merged_params.get("length", 100)),
                seed=int(merged_params.get("seed", 42)),
                gc_content=merged_params.get("gc_content"),
            )

        if action in ("find_orfs", "orfs", "find_orf"):
            table_val = merged_params.get("table") or merged_params.get("table_id") or 1
            min_len_val = (
                merged_params.get("min_protein_length")
                or merged_params.get("min_length")
                or 30
            )
            return ops.find_orfs(
                seq=seq,
                min_protein_length=int(min_len_val),
                table_id=int(table_val),
                strand=str(merged_params.get("strand") or "both"),
            )

        if action in ("format_fasta", "fasta", "to_fasta"):
            return ops.format_fasta(
                seq=seq,
                header=str(merged_params.get("header") or "sequence"),
                line_width=int(merged_params.get("line_width", 60)),
            )

        if action in ("list_tables", "tables", "genetic_codes", "get_tables"):
            return ops.list_genetic_tables()

        if action in ("lookup_iupac", "iupac", "lookup_code", "code"):
            code_val = merged_params.get("code") or seq
            return ops.lookup_iupac_code(code=str(code_val or ""))

        return {
            "status": "error",
            "action": action,
            "reason_codes": ["INVALID_ACTION"],
            "message": (
                f"Unsupported action '{action}'. Supported actions: 'detect_type', 'validate', "
                "'revcom', 'transcribe', 'translate', 'pairwise_align', 'variant_diff', "
                "'kmer_profile', 'generate', 'find_orfs', 'format_fasta', "
                "'list_tables', 'lookup_iupac'."
            ),
        }
