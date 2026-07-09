import base64
import io
import os

import pytest
import yaml
from PIL import Image

from .skill import BackgroundRemover
from . import skill as bg_skill

print("Loaded module:", bg_skill.__name__)

@pytest.fixture(autouse=True)
def mock_remove(monkeypatch):
    """Mock rembg.remove so tests stay offline."""

    def fake_remove(image_bytes):
        img = Image.new("RGBA", (100, 100), (255, 0, 0, 0))
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()

    monkeypatch.setattr(
        "skills.creative.bg_remover.skill.remove",
        fake_remove,
    )

@pytest.fixture
def skill():
    return BackgroundRemover()

@pytest.fixture
def manifest():
    manifest_path = os.path.join(
        os.path.dirname(__file__),
        "manifest.yaml",
    )

    with open(manifest_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
    
def test_manifest(skill, manifest):
    assert skill.manifest["name"] == manifest["name"]
    assert skill.manifest["version"] == manifest["version"]


def test_missing_input(skill):
    result = skill.execute({})

    assert result["success"] is False
    assert result["error_code"] == "INVALID_INPUT"
    
def create_image():

    image = Image.new("RGB", (64, 64), "white")

    buffer = io.BytesIO()

    image.save(buffer, format="PNG")

    return base64.b64encode(
        buffer.getvalue()
    ).decode()

def test_base64_image(skill):

    img = create_image()

    result = skill.execute(
        {
            "image": img
        }
    )

    assert result["success"] is True
    assert result["mime_type"] == "image/png"
    assert result["width"] > 0
    assert result["height"] > 0 

def test_output_keys(skill):

    img = create_image()

    result = skill.execute(
        {
            "image": img
        }
    )

    expected = {
        "success",
        "image_base64",
        "mime_type",
        "output_path",
        "width",
        "height",
        "model_used",
    }

    assert expected.issubset(result.keys())

def test_invalid_base64(skill):

    result = skill.execute(
        {
            "image": "not_base64"
        }
    )

    assert result["success"] is False
    assert result["error_code"] == "PROCESSING_FAILED"