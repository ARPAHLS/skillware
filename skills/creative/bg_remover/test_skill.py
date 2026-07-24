import base64
import io
import os

import pytest
import yaml
from PIL import Image

from .skill import BackgroundRemover

import sys
import types


@pytest.fixture(autouse=True)
def mock_remove(monkeypatch):
    """Mock rembg so tests stay offline."""

    def fake_remove(image_bytes, *args, **kwargs):
        img = Image.new("RGBA", (100, 100), (255, 0, 0, 0))
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()

    def fake_new_session(model_name="u2net", *args, **kwargs):
        return object()

    fake_module = types.SimpleNamespace(
        remove=fake_remove,
        new_session=fake_new_session,
    )

    monkeypatch.setitem(sys.modules, "rembg", fake_module)


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

    return base64.b64encode(buffer.getvalue()).decode()


def test_base64_image(skill):

    img = create_image()

    result = skill.execute({"image": img})

    assert result["success"] is True
    assert result["mime_type"] == "image/png"
    assert result["width"] > 0
    assert result["height"] > 0


def test_output_keys(skill):

    img = create_image()

    result = skill.execute({"image": img})

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

    result = skill.execute({"image": "not_base64"})

    assert result["success"] is False
    assert result["error_code"] == "INVALID_INPUT"

def test_missing_dependency(monkeypatch, skill):
    """Returns MISSING_DEPENDENCY when optional libraries are unavailable."""

    monkeypatch.delitem(sys.modules, "rembg", raising=False)
    monkeypatch.delitem(sys.modules, "PIL", raising=False)
    monkeypatch.delitem(sys.modules, "PIL.Image", raising=False)

    original_import = __import__

    def fake_import(name, *args, **kwargs):
        if name in ("rembg", "PIL", "PIL.Image"):
            raise ImportError
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)

    result = skill.execute({"image": create_image()})

    assert result["success"] is False
    assert result["error_code"] == "MISSING_DEPENDENCY"

def test_input_path(skill, tmp_path):
    image = Image.new("RGB", (64, 64), "white")

    input_file = tmp_path / "input.png"
    image.save(input_file)

    result = skill.execute(
        {
            "input_path": str(input_file),
        }
    )

    assert result["success"] is True
    assert result["mime_type"] == "image/png"


def test_output_path(skill, tmp_path):
    image = Image.new("RGB", (64, 64), "white")

    input_file = tmp_path / "input.png"
    output_file = tmp_path / "output.png"

    image.save(input_file)

    result = skill.execute(
        {
            "input_path": str(input_file),
            "output_path": str(output_file),
        }
    )

    assert result["success"] is True
    assert output_file.exists()
    assert result["output_path"] == str(output_file)

def test_session_reuse(monkeypatch, skill):
    """Verify rembg sessions are reused for the same model."""

    call_count = 0

    def fake_new_session(model_name="u2net", *args, **kwargs):
        nonlocal call_count
        call_count += 1
        return object()

    def fake_remove(image_bytes, *args, **kwargs):
        img = Image.new("RGBA", (100, 100), (255, 0, 0, 0))
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()

    fake_module = types.SimpleNamespace(
        remove=fake_remove,
        new_session=fake_new_session,
    )

    monkeypatch.setitem(sys.modules, "rembg", fake_module)

    # Reset cached sessions so the test starts clean
    BackgroundRemover._sessions.clear()

    image = create_image()

    skill.execute({"image": image})
    skill.execute({"image": image})

    assert call_count == 1

def test_missing_input_file(skill):
    result = skill.execute(
        {
            "input_path": "does_not_exist.png",
        }
    )

    assert result["success"] is False
    assert result["error_code"] == "FILE_NOT_FOUND"

def test_empty_input_file(skill, tmp_path):
    empty_file = tmp_path / "empty.png"
    empty_file.write_bytes(b"")

    result = skill.execute(
        {
            "input_path": str(empty_file),
        }
    )

    assert result["success"] is False
    assert result["error_code"] == "INVALID_INPUT"

def test_invalid_image(skill):
    invalid_image = base64.b64encode(
        b"this is not an image"
    ).decode()

    result = skill.execute(
        {
            "image": invalid_image,
        }
    )

    assert result["success"] is False
    assert result["error_code"] == "INVALID_INPUT"