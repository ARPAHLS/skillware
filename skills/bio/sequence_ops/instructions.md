# Sequence Operations Directive (`bio/sequence_ops`)

Provides deterministic, offline in-silico operations on biological sequences (DNA, RNA, and protein strings) using Biopython. Supports character validation, molecular transformations, pairwise sequence alignments, variant diffing, k-mer frequency profiling, 6-frame Open Reading Frame (ORF) discovery, FASTA formatting, and seeded pseudo-random sequence generation.

## When to invoke

- Invoke when receiving raw nucleotide strings, amino acid peptides, or FASTA files from molecular biology workflows, genomics pipelines, or synthetic DNA construct specifications.
- Invoke to infer molecule type (`detect_type`) or validate character sets and length bounds (`validate`) before passing sequences to downstream simulation or design pipelines.
- Invoke to perform reverse complementation (`revcom`), transcription (`transcribe`), or reading-frame translation (`translate`) across standard, vertebrate mitochondrial, or bacterial genetic codes.
- Invoke to compute Needleman-Wunsch global or Smith-Waterman local pairwise alignments (`pairwise_align`) with exact identity percentages and coordinate tracking.
- Invoke to call structural sequence mutations (`variant_diff`), including substitutions, insertions, deletions, and micro-inversions against a reference.
- Invoke to scan contigs for Open Reading Frames (`find_orfs`) across all 6 reading frames to identify candidate protein coding sequences.
- Invoke to calculate k-mer frequency distributions and Shannon entropy (`kmer_profile`) or format multi-line FASTA strings (`format_fasta`).

## When NOT to invoke

- Do not invoke for clinical medical diagnostics, patient care decisions, or in-vitro laboratory assays; this is an in-silico computational modeling tool only.
- Do not invoke for remote database homology searches over the network (e.g. NCBI BLAST); all operations execute strictly in-memory.
- Do not invoke for biophysical thermodynamic stability, melting temperature ($T_m$), or secondary structure MFE folding (use `bio/sequence_property_scan`).
- Do not invoke for neural protein folding or structure prediction (AlphaFold/ESMFold).

## Input Parameters

- `action`: Operation name (default `detect_type`). Supported: `detect_type`, `validate`, `revcom`, `transcribe`, `translate`, `pairwise_align`, `variant_diff`, `kmer_profile`, `generate`, `find_orfs`, `format_fasta`.
- `sequence`: Primary input sequence string. Whitespace, line breaks, and FASTA `>` comment headers are stripped automatically. Parameter aliases `seq`, `reference`, and `input_sequence` are also accepted.
- `sequence_b`: Secondary sequence string for pairwise alignment and variant calling. Parameter aliases `query` and `target_sequence` are also accepted.
- `molecule_type`: Optional explicit molecule specification (`dna`, `rna`, `protein`). Inferred automatically from character frequencies if omitted.
- `table_id` / `table`: NCBI genetic code table ID (1=Standard, 2=Vertebrate Mitochondrial, 11=Bacterial/Plastid). Default is 1.
- `reading_frame`: Translation reading frame offset (0, 1, or 2). Default is 0.
- `to_stop`: If true, translation terminates at the first encountered stop codon (`*`). Default is false.
- `mode`: Pairwise alignment algorithm (`global` for Needleman-Wunsch, `local` for Smith-Waterman). Default is `global`.
- `min_protein_length`: Minimum amino acid length for candidate ORFs in `find_orfs`. Default is 30.
- `strand`: Strand orientation for `find_orfs` (`both`, `forward`, or `reverse`). Default is `both`.
- `k`: K-mer window size for frequency profiling (e.g., 2 for dinucleotides, 3 for trinucleotides). Default is 3.
- `top_n`: Number of top frequent k-mers to return in `kmer_profile`. Default is 10.
- `header`: Header identifier for `format_fasta`. Default is `sequence`.
- `line_width`: Maximum characters per line for formatted FASTA output. Default is 60.
- `seed`: Integer seed for 100% reproducible sequence generation in `generate`. Default is 42.
- `length`: Target sequence length for `generate`. Default is 100.
- `gc_content`: Desired GC ratio (0.0 to 1.0) for nucleotide generation.

## Action Summary

| Action | Primary Input | Expected Output Fields | Common Use Case |
| :--- | :--- | :--- | :--- |
| `detect_type` | `sequence` | `molecule_type`, `confidence`, `length`, `alphabet_violations` | Sequence classification |
| `validate` | `sequence`, bounds | `valid`, `errors`, `reason_codes` | Gatekeeper prior to pipeline ingestion |
| `revcom` | DNA `sequence` | `output_sequence`, `molecule_type` | Watson-Crick reverse complement |
| `transcribe` | DNA/RNA `sequence` | `output_sequence`, `molecule_type` | Coding strand transcription ($T \rightarrow U$) |
| `translate` | `sequence`, `table_id` | `output_sequence`, `stop_codons_count` | Polypeptide translation |
| `pairwise_align` | `sequence`, `sequence_b` | `score`, `identity_percent`, `matches`, `gaps`, `alignment_a/b` | Homology & sequence comparison |
| `variant_diff` | `reference`, `query` | `mutations[]`, `inversions[]`, `mutations_count` | Structural mutation calling |
| `find_orfs` | `sequence`, `min_protein_length` | `orfs[]` (`id`, `frame`, `strand`, `start`, `end`, `protein_sequence`) | Gene and coding sequence discovery |
| `kmer_profile` | `sequence`, `k` | `total_kmers`, `unique_kmers`, `entropy`, `top_kmers[]` | Complexity and motif frequency analysis |
| `format_fasta` | `sequence`, `header` | `fasta` | Standard FASTA formatting |
| `generate` | `length`, `seed` | `sequence`, `length`, `seed` | Synthetic fixtures & reproducible testing |
| `list_tables` | None | `tables[]` (`table_id`, `name`, `start_codons`, `stop_codons`) | Inspect bundled NCBI genetic code tables |
| `lookup_iupac` | `code` | `nucleotide`, `amino_acid`, `biophysical_properties` | IUPAC notation & ambiguity lookup |

## Interpreting Status Envelopes

- **`status: "ready"`**: The operation executed deterministically. Inspect action-specific fields (`output_sequence`, `valid`, `identity_percent`, `orfs`, etc.).
- **`status: "error"`**: The operation failed closed due to invalid input. Always check `reason_codes`:
  - `EMPTY_SEQUENCE`: Sequence input was empty or whitespace only.
  - `UNSUPPORTED_MOLECULE_TYPE`: Operation cannot be applied to the molecule (e.g. attempting `revcom` on protein or RNA).
  - `INVALID_ACTION`: Action name not supported by the dispatcher.
  - `INVALID_ALIGNMENT_MODE`: Mode specified was not `global` or `local`.
  - `INVALID_READING_FRAME`: Reading frame specified was not 0, 1, or 2.
  - `INVALID_STRAND`: Strand specified was not `both`, `forward`, or `reverse`.
  - `INVALID_GENETIC_CODE_TABLE`: Table ID not recognized by NCBI genetic code tables.
  - `INVALID_ALPHABET`: Characters detected outside IUPAC standard or ambiguous sets.
  - `LENGTH_OUT_OF_BOUNDS`: Sequence length fell outside configured `min_length` or `max_length`.

## Chaining and Agent Patterns

1. **Ingestion & Validation Gate**:
   Call `validate` on untrusted sequence strings before proceeding. If `valid is False`, inspect `errors` and inform the caller rather than continuing.
2. **Gene Discovery & Translation**:
   Pass unannotated DNA sequences to `find_orfs` (`min_protein_length: 30`) to extract all putative coding sequences across both strands.
3. **Cloning & Mutation Analysis**:
   Pass wildtype template as `reference` and engineered construct as `query` to `variant_diff` to audit substitutions, indels, and micro-inversions.
4. **Data Export**:
   Format modified sequences with `format_fasta` for standardized file persistence or FASTA sharing.
