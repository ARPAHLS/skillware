# Instructions: Multi-Omics FAIR Normalizer (`bioinformatics/omics_data_normalizer`)

Use this skill to validate and restructure local CSV or TSV genomics, transcriptomics, or other multi-omics tables before an agent reasons over them.

### Scope

- Normalize column headers to stable `snake_case` names.
- Preserve the tabular records in a JSON package.
- Report row counts, column types, missing values, and missing metadata fields.
- Use the requested metadata standard as a declared target; do not claim compliance when required metadata is missing.

This skill performs formatting and validation only. It does not diagnose disease, infer biological relationships, run alignments, quantify reads, or call external services.

### Parameters

- `raw_csv_path`: local `.csv` or `.tsv` file.
- `target_standard`: non-empty metadata standard name, such as `MIAME`.

### Output handling

The skill writes `<input-stem>_fair.json` beside the input file. Treat `missing_metadata_warnings` as actionable validation findings and do not silently fill those fields.

### Example

```text
Run bioinformatics/omics_data_normalizer with raw_csv_path="./local_data/patient_transcriptome_raw.csv" and target_standard="MIAME".
```
