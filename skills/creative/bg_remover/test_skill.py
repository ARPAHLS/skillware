import base64
import io
import importlib.util
import os

import pytest
import yaml
from PIL import Image

from skillware.core.loader import SkillLoader

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

    fake_module = types.ModuleType("rembg")
    fake_module.remove = fake_remove
    fake_module.new_session = fake_new_session
    fake_module.__spec__ = importlib.util.spec_from_loader("rembg", loader=None)

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


def test_skill_loader_can_import():
    bundle = SkillLoader.load_skill("creative/bg_remover")
    assert bundle["manifest"]["name"] == "creative/bg_remover"
    assert hasattr(bundle["module"], "BackgroundRemover")


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
    assert result["error_code"] == "PROCESSING_FAILED"


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


def test_image_precedence_over_input_path(skill, tmp_path, monkeypatch):
    """When both image and input_path are sent, base64 image wins."""

    path_file = tmp_path / "path.png"
    Image.new("RGB", (32, 32), "blue").save(path_file)

    seen = {}

    def fake_remove(image_bytes, *args, **kwargs):
        seen["size"] = len(image_bytes)
        img = Image.new("RGBA", (100, 100), (255, 0, 0, 0))
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()

    fake_module = types.SimpleNamespace(
        remove=fake_remove,
        new_session=lambda *args, **kwargs: object(),
    )
    monkeypatch.setitem(sys.modules, "rembg", fake_module)

    b64 = create_image()
    result = skill.execute(
        {
            "image": b64,
            "input_path": str(path_file),
        }
    )

    assert result["success"] is True
    assert seen["size"] == len(base64.b64decode(b64))


def test_custom_model(skill):
    result = skill.execute({"image": create_image(), "model": "u2net"})

    assert result["success"] is True
    assert result["model_used"] == "u2net"


def test_alpha_matting_forwarded(skill, monkeypatch):
    seen = {}

    def fake_remove(image_bytes, *args, **kwargs):
        seen["alpha_matting"] = kwargs.get("alpha_matting")
        img = Image.new("RGBA", (100, 100), (255, 0, 0, 0))
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()

    fake_module = types.SimpleNamespace(
        remove=fake_remove,
        new_session=lambda *args, **kwargs: object(),
    )
    monkeypatch.setitem(sys.modules, "rembg", fake_module)

    result = skill.execute(
        {
            "image": create_image(),
            "alpha_matting": True,
        }
    )

    assert result["success"] is True
    assert seen["alpha_matting"] is True


def test_missing_input_path(skill):
    result = skill.execute({"input_path": "/nonexistent/path/image.png"})

    assert result["success"] is False
    assert result["error_code"] == "PROCESSING_FAILED"
