import pytest
from unittest.mock import MagicMock
import sys
import os

# Add repo root to path so we can import 'skills' and 'skillware'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture
def mock_anthropic():
    """Mocks the Anthropic client."""
    mock_client = MagicMock()
    # Mock the messages.create return structure
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text='{"field_id": "value"}')]
    return mock_client


@pytest.fixture
def mock_skill_loader():
    """Mocks the SkillLoader to return a dummy skill bundle."""
    # This might not be needed if we import the class directly, but good to have.
    return MagicMock()


@pytest.fixture(autouse=True)
def isolate_skillware_config(tmp_path_factory, monkeypatch):
    """Isolate tests from any real global config.yaml on the developer's machine."""
    from skillware.core.config import GLOBAL_CONFIG_DIR_ENV, clear_config_cache

    isolated_dir = tmp_path_factory.mktemp("isolated_skillware_config")
    monkeypatch.setenv(GLOBAL_CONFIG_DIR_ENV, str(isolated_dir))
    clear_config_cache()
    yield
    clear_config_cache()
