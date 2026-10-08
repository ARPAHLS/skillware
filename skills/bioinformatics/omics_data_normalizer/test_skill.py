import json

import pytest
import yaml

from .skill import OmicsDataNormalizerSkill


@pytest.fixture
def skill():
    return OmicsDataNormalizerSkill()


@pytest.fixture
def manifest():
    with open(
        "skills/bioinformatics/omics_data_normalizer/manifest.yaml", encoding="utf-8"
    ) as handle:
        return yaml.safe_load(handle)


def test_manifest_matches_skill(skill, manifest):
    assert skill.manifest["name"] == manifest["name"]
    assert skill.manifest["version"] == manifest["version"]


def test_normalizes_headers_preserves_records_and_reports_missing_metadata(
    tmp_path, skill
):
    source = tmp_path / "transcriptome.csv"
    source.write_text(
        "Sample ID,collection date,TPM value\nS1,2026-01-02,3.5\n",
        encoding="utf-8",
    )

    result = skill.execute({"raw_csv_path": str(source), "target_standard": "MIAME"})

    assert result["status"] == "normalized"
    assert result["missing_metadata_warnings"] == ["organism", "tissue", "assay"]
    output = json.loads(
        (tmp_path / "transcriptome_fair.json").read_text(encoding="utf-8")
    )
    assert output["fair_metadata"]["columns"][0]["normalized_name"] == "sample_id"
    assert output["records"] == [
        {"sample_id": "S1", "collection_date": "2026-01-02", "tpm_value": 3.5}
    ]


def test_accepts_tsv_and_reports_complete_metadata(tmp_path, skill):
    source = tmp_path / "samples.tsv"
    source.write_text(
        "sample_id\torganism\ttissue\tcollection_date\tassay\n"
        "S1\tArabidopsis thaliana\tleaf\t2026-01-02\tRNA-seq\n",
        encoding="utf-8",
    )

    result = skill.execute({"raw_csv_path": str(source), "target_standard": "MIAME"})

    assert result["status"] == "normalized"
    assert result["missing_metadata_warnings"] == []


def test_rejects_non_tabular_input(tmp_path, skill):
    source = tmp_path / "sample.txt"
    source.write_text("not a table", encoding="utf-8")

    result = skill.execute({"raw_csv_path": str(source), "target_standard": "MIAME"})

    assert result["status"] == "error"
    assert "csv or .tsv" in result["message"]
