# Sequence Operations Skill

**ID**: `bio/sequence_ops`
**Issuer**: [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS))
<!-- skill-doc-meta:begin -->
**Version**: `0.1.0` — 24 Oct 2026
**Tier**: `core`
**Shape**: `atomic`
**Target**: `software`
**Tags**: `dna`, `rna`, `protein`, `bioinformatics`, `in_silico`, `alignment`, `translation`, `transcription`, `genomics`, `fasta`
<!-- skill-doc-meta:end -->
<!-- skill-intent:begin -->
**Solves:** Deterministic in-silico operations on DNA, RNA, and protein sequence strings.
**Works with:** Gemini, Claude, OpenAI, DeepSeek, Ollama, and Bedrock-compatible host loops.
**Runtime:** 100% offline local Python execution with Biopython. No external API keys required.
<!-- skill-intent:end -->

**Recommended install:** `pip install "skillware[bio_sequence_ops]"`. See [Install extras](../../usage/install_extras.md).
[Skill Library](../README.md) · [Bio](README.md) · [Testing](../../TESTING.md)

A deterministic foundational life-sciences skill that performs sequence typing, alphabet and length validation, molecular transforms (reverse complement, transcription, translation), pairwise alignment, variant difference detection, k-mer frequency profiling, 6-frame Open Reading Frame (ORF) discovery, standard FASTA formatting, and reproducible seeded pseudo-random sequence generation.

## Capabilities

* **Sequence Typing (`detect_type`)**: Discovers whether an input sequence is DNA, RNA, protein, or invalid/unknown based on character frequencies.
* **Validation (`validate`)**: Strict alphabet verification, length constraints, and IUPAC ambiguity code handling.
* **Reverse Complement (`revcom`)**: Watson-Crick pairing reversal for DNA sequences.
* **Transcription (`transcribe`)**: Converts DNA thymine (T) to RNA uracil (U).
* **Translation (`translate`)**: Translates nucleotide triplets into amino acid polypeptide chains across reading frames (0, 1, 2) and NCBI genetic code tables (1=Standard, 2=Vertebrate Mitochondrial, 11=Bacterial/Plastid) with optional stop-codon termination.
* **Pairwise Alignment (`pairwise_align`)**: Deterministic Needleman-Wunsch global and Smith-Waterman local sequence alignments via Biopython PairwiseAligner.
* **Variant Diffing (`variant_diff`)**: Structural mutation calling (substitutions, insertions, deletions, micro-inversions) against reference templates.
* **Open Reading Frame Discovery (`find_orfs`)**: Comprehensive 6-frame scanning (+1, +2, +3, -1, -2, -3) to locate start/stop codon boundaries, coordinate spans, and translate candidate coding sequences.
* **K-mer Profiling (`kmer_profile`)**: Computes k-mer frequency distributions, top-N frequent words, and Shannon entropy.
* **FASTA Formatting (`format_fasta`)**: Standard multi-line FASTA record generation with configurable header and line-width wrapping.
* **Seeded Generation (`generate`)**: 100% reproducible pseudo-random sequence generation with configurable GC content bias for pipeline testing and fixtures.

## Bundle layout

The skill is self-contained in `skills/bio/sequence_ops/`. [Skill anatomy](../../introduction.md#skill-anatomy). Vocabulary: [glossary](../../glossary.md). **Contract** — see Manifest Details above. **Assurance** — `test_skill.py` in the bundle.

### Knowledge Base (`kb/`)
* `kb/codon_table.json`: Standard genetic code codon and start/stop codon mappings.
* `kb/genetic_codes.json`: Multi-table NCBI genetic code definitions (Table 1 Standard, Table 2 Vertebrate Mitochondrial, Table 11 Bacterial/Plastid).
* `kb/iupac_codes.json`: IUPAC nucleotide and amino acid ambiguity codes, base decompositions, and reverse complement pairings.
* `kb/amino_acids.json`: Complete 20 standard amino acid reference table with 1-letter, 3-letter, chemical classifications, formulas, and monoisotopic masses.

### Directive (`instructions.md`)
The directive provides operational guidance for host models to select actions, format sequence parameters, resolve aliases, and inspect structured outputs.

### Effect (`skill.py` & `ops.py`)
* **Biopython Engine**: Uses `Bio.Seq` and `Bio.Align.PairwiseAligner` for robust in-silico computational biology.
* **Pure Determinism**: Zero network requests or external model calls.
* **Structured Envelopes**: Consistent status codes (`ready`, `error`), typed `reason_codes`, and standard biological metrics.

## Integration Guide

### Environment

None. This skill operates entirely deterministically and offline in memory; no provider API keys or external services are required.

## Usage Examples

Guides: [Usage index](../../usage/README.md) · [Agent loops](../../usage/agent_loops.md) · [API keys](../../usage/api_keys.md).

Use `bundle["class"]()` in the snippets below; explicit `bundle["module"].SequenceOpsSkill()` also works.

### Direct execute

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("bio/sequence_ops")
skill = bundle["class"]()

# Step 1: Detect molecule type
res_type = skill.execute({"action": "detect_type", "sequence": "ATGCGTAACCGTT"})
print("Detected molecule:", res_type["molecule_type"])

# Step 2: Reverse complement
res_rc = skill.execute({"action": "revcom", "sequence": "ATGCGTAA"})
print("Reverse complement:", res_rc["output_sequence"])

# Step 3: Pairwise alignment
res_aln = skill.execute({
    "action": "pairwise_align",
    "sequence": "ATGCGTAA",
    "sequence_b": "ATGCGTGA",
    "mode": "global",
})
print(f"Alignment identity: {res_aln['identity_percent']}%")
```

### Gemini

```python
import os
import google.genai as genai
from google.genai import types
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("bio/sequence_ops")
skill = bundle["class"]()
client = genai.Client()
tool = SkillLoader.to_gemini_tool(bundle)
tool_name = SkillLoader._sanitize_gemini_tool_name(bundle["manifest"]["name"])
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Translate the DNA sequence ATGGCCATTGTAATGGGCCGCTGAAAGGGTGCCCGATAG to protein.",
    config=types.GenerateContentConfig(
        tools=[tool],
        system_instruction=bundle["instructions"],
    ),
)
for part in response.candidates[0].content.parts:
    if part.function_call and part.function_call.name == tool_name:
        result = skill.execute(dict(part.function_call.args))
        print("Result:", result["output_sequence"])
```

### Claude

```python
import os
import anthropic
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("bio/sequence_ops")
skill = bundle["class"]()
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
tools = [SkillLoader.to_claude_tool(bundle)]
response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    system=bundle["instructions"],
    tools=tools,
    messages=[{"role": "user", "content": "Align reference ATGCGTAA against query ATGCGTGA."}],
)
for block in response.content:
    if block.type == "tool_use":
        result = skill.execute(dict(block.input))
        print("Identity:", result.get("identity_percent"))
```

### OpenAI

```python
import json
import os
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("bio/sequence_ops")
skill = bundle["class"]()
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
tool = SkillLoader.to_openai_tool(bundle)
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": bundle["instructions"]},
        {"role": "user", "content": "Compute the reverse complement of DNA sequence ATGCGTAA."},
    ],
    tools=[tool],
)
message = response.choices[0].message
if message.tool_calls:
    args = json.loads(message.tool_calls[0].function.arguments)
    result = skill.execute(args)
    print("Output:", result.get("output_sequence"))
```

### DeepSeek

```python
import json
import os
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("bio/sequence_ops")
skill = bundle["class"]()
client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)
tool = SkillLoader.to_deepseek_tool(bundle)
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": bundle["instructions"]},
        {"role": "user", "content": "Generate a 100 bp DNA sequence with seed 42 and 50% GC."},
    ],
    tools=[tool],
)
message = response.choices[0].message
if message.tool_calls:
    args = json.loads(message.tool_calls[0].function.arguments)
    result = skill.execute(args)
    print("Sequence:", result.get("sequence"))
```

### Ollama

```python
import json
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("bio/sequence_ops")
skill = bundle["class"]()
prompt = (
    "You may call tools as JSON blocks.\n"
    f"Tool: {bundle['manifest']['name']}\n"
    f"Instructions:\n{bundle['instructions']}\n"
    f"User: Reverse complement the sequence ATGCGTAA."
)
print(prompt)
result = skill.execute({
    "action": "revcom",
    "sequence": "ATGCGTAA",
})
print(json.dumps(result, indent=2))
```

## Data Schema

The skill returns a structured envelope with standard fields:

```json
{
  "status": "ready",
  "action": "revcom",
  "input_sequence": "ATGCGTAA",
  "output_sequence": "TTACGCAT",
  "molecule_type": "dna",
  "length": 8
}
```

## Constitution & Disclaimers

1. **IN-SILICO COMPUTATION ONLY**: All outputs represent computational model evaluations and string operations, not physical laboratory assays or validated medical/therapeutic findings.
2. **STRICT DETERMINISM**: All operations yield bitwise-identical results across platforms.
3. **AIR-GAPPED INTEGRITY**: Never invokes external network endpoints. Operates purely in-memory.
4. **NO MEDICAL CLAIMS**: No medical, clinical, or diagnostic claims may be derived from outputs.

---

<!-- skill-history:begin -->
## Skill history

Commits that touched this skill bundle or its catalog page ([`bio/sequence_ops`](https://github.com/ARPAHLS/skillware/tree/main/skills/bio/sequence_ops)).

| Commit | Description | Date | Version | Contributors |
| :--- | :--- | :--- | :--- | :--- |
| `d48d59a` | feat(bio): introduce foundational bio category and sequence_ops skill (#427) | 24 Oct 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
<!-- skill-history:end -->

## Enterprise disclaimer

This skill is provided for demonstration and integration purposes. It is intended as a starting point that you can adapt to your own data, schemas, and operational requirements. For an enterprise-grade version of this skill with dedicated support, SLAs, and customization, contact skills@arpacorp.net.
