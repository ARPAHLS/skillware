# Multi-Omics FAIR Normalizer

**Domain:** `bioinformatics`  
**Skill ID:** `bioinformatics/omics_data_normalizer`  
<!-- skill-doc-meta:begin -->
**Version**: `0.1.0` — 17 Sep 2026
<!-- skill-doc-meta:end -->

**Recommended install:** `pip install "skillware[bioinformatics_omics_data_normalizer]"`. See [Install extras](../usage/install_extras.md).

The Multi-Omics FAIR Normalizer validates local CSV or TSV genomics and transcriptomics tables before an AI agent reasons over them. It normalizes headers, preserves records, records column-level missingness, and reports expected metadata that is absent.

## Scope and safety

This is a deterministic formatting and validation skill. It does not diagnose disease, infer biological relationships, run alignment or quantification, or call external services. Missing metadata is reported as a warning rather than invented.

## Usage

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("bioinformatics/omics_data_normalizer")
skill = bundle["class"]()
result = skill.execute({
    "raw_csv_path": "./local_data/patient_transcriptome_raw.csv",
    "target_standard": "MIAME",
})
print(result["fair_compliant_json_path"])
print(result["missing_metadata_warnings"])
```

The generated file is written beside the input as `<input-stem>_fair.json` and contains `fair_metadata` plus the normalized `records`.

---

<!-- skill-history:begin -->
## Skill history

This skill is proposed in [Issue #49](https://github.com/ARPAHLS/skillware/issues/49).
<!-- skill-history:end -->
