"""Tests for EVM operator configuration (evm.yaml merge and helpers)."""

from pathlib import Path

import pytest
import yaml

from skillware.core.config import (
    GLOBAL_CONFIG_DIR_ENV,
    PROJECT_CONFIG_FILENAME,
    clear_config_cache,
    load_merged_config,
)
from skillware.core.evm_config import (
    ENV_EVM_CONFIG_PATH,
    clear_evm_config_cache,
    init_evm_config_file,
    load_merged_evm_config,
    normalize_evm_address,
    resolve_chain,
    resolve_evm_config_path,
    resolve_rpc_url,
    validate_evm_config_data,
)


@pytest.fixture(autouse=True)
def _reset_caches():
    clear_config_cache()
    clear_evm_config_cache()
    yield
    clear_config_cache()
    clear_evm_config_cache()


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def test_load_merged_evm_config_includes_bundled_defaults():
    merged = load_merged_evm_config(refresh=True)
    assert "ethereum" in merged.chains
    assert "base" in merged.chains
    assert merged.chains["ethereum"]["chain_id"] == 1
    assert merged.tokens.get("base", {}).get("degen", {}).get("decimals") == 18


def test_merge_precedence_bundled_global_project(tmp_path, monkeypatch):
    config_dir = tmp_path / "cfg"
    config_dir.mkdir()
    monkeypatch.setenv(GLOBAL_CONFIG_DIR_ENV, str(config_dir))

    user_evm = config_dir / "evm.yaml"
    _write(
        user_evm,
        """
version: 1
chains:
  ethereum:
    enabled: true
    chain_id: 1
    rpc_env: ETHEREUM_RPC_URL
    native_symbol: eth
    native_decimals: 18
    router_v2: "0x7a250d5630B4cF539739dF2C5dA4bF9C15291ECE"
  custom_chain:
    enabled: true
    chain_id: 999
    rpc_env: CUSTOM_RPC_URL
    native_symbol: eth
    native_decimals: 18
""",
    )

    project = tmp_path / "project"
    project.mkdir()
    _write(
        project / PROJECT_CONFIG_FILENAME,
        """
evm:
  chains:
    ethereum:
      enabled: false
    project_only:
      enabled: true
      chain_id: 4242
      rpc_env: PROJECT_RPC_URL
      native_symbol: eth
      native_decimals: 18
""",
    )
    monkeypatch.chdir(project)

    merged = load_merged_evm_config(refresh=True)
    assert merged.chains["ethereum"]["enabled"] is False
    assert merged.chains["custom_chain"]["chain_id"] == 999
    assert merged.chains["project_only"]["chain_id"] == 4242


def test_resolve_evm_config_path_env_override(tmp_path, monkeypatch):
    override = tmp_path / "custom-evm.yaml"
    override.write_text("version: 1\nchains: {}\n", encoding="utf-8")
    monkeypatch.setenv(ENV_EVM_CONFIG_PATH, str(override))
    assert resolve_evm_config_path() == override.resolve()


def test_init_evm_config_file_and_enable_subset(tmp_path):
    target = tmp_path / "evm.yaml"
    init_evm_config_file(target, enabled_chains=["ethereum"], overwrite=False)
    data = yaml.safe_load(target.read_text(encoding="utf-8"))
    assert data["chains"]["ethereum"]["enabled"] is True
    assert data["chains"]["base"]["enabled"] is False


def test_resolve_rpc_url_from_env(monkeypatch):
    monkeypatch.setenv("ETHEREUM_RPC_URL", "https://example.invalid/eth")
    url = resolve_rpc_url("ethereum")
    assert url == "https://example.invalid/eth"


def test_resolve_chain_rejects_disabled(tmp_path, monkeypatch):
    config_dir = tmp_path / "cfg"
    config_dir.mkdir()
    monkeypatch.setenv(GLOBAL_CONFIG_DIR_ENV, str(config_dir))
    init_evm_config_file(
        config_dir / "evm.yaml",
        enabled_chains=["base"],
        overwrite=True,
    )
    with pytest.raises(ValueError, match="disabled"):
        resolve_chain("ethereum")


def test_normalize_evm_address_checksum():
    web3 = pytest.importorskip("web3").Web3
    lower = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
    expected = web3.to_checksum_address(lower)
    assert normalize_evm_address(lower) == expected
    assert lower != expected


def test_validate_evm_config_data_detects_duplicate_chain_id():
    pytest.importorskip("web3")
    errors = validate_evm_config_data(
        {
            "chains": {
                "a": {
                    "chain_id": 1,
                    "rpc_env": "A_RPC",
                    "router_v2": "0x7a250d5630B4cF539739dF2C5dA4bF9C15291ECE",
                },
                "b": {
                    "chain_id": 1,
                    "rpc_env": "B_RPC",
                    "router_v2": "0x7a250d5630B4cF539739dF2C5dA4bF9C15291ECE",
                },
            }
        }
    )
    assert any("duplicate chain_id" in err for err in errors)


def test_config_merge_parses_evm_block(tmp_path, monkeypatch):
    config_dir = tmp_path / "cfg"
    config_dir.mkdir()
    monkeypatch.setenv(GLOBAL_CONFIG_DIR_ENV, str(config_dir))
    _write(
        config_dir / "config.yaml",
        """
evm:
  config_path: ./project-evm.yaml
  chains:
    arbitrum:
      enabled: true
      chain_id: 42161
      rpc_env: ARBITRUM_RPC_URL
""",
    )
    config = load_merged_config(refresh=True)
    assert config.evm.config_path == "./project-evm.yaml"
    assert config.evm.chains["arbitrum"]["chain_id"] == 42161


def test_bundled_defaults_file_exists_in_package():
    from skillware.core.evm_config import bundled_evm_defaults_path

    path = bundled_evm_defaults_path()
    assert path.is_file()
    assert path.name == "evm_defaults.yaml"


def test_validate_merged_defaults_passes_without_web3(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def _block_web3_only(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "web3" or (fromlist and "web3" in fromlist):
            raise ImportError("blocked for test")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _block_web3_only)
    merged = load_merged_evm_config(refresh=True)
    errors = validate_evm_config_data(
        {
            "version": merged.version,
            "chains": merged.chains,
            "tokens": merged.tokens,
        }
    )
    assert errors == []


def test_get_web3_uses_resolved_rpc(monkeypatch):
    pytest.importorskip("web3")
    from unittest.mock import MagicMock, patch

    monkeypatch.setenv("ETHEREUM_RPC_URL", "https://rpc.example/eth")
    mock_web3 = MagicMock()
    with patch("web3.Web3", mock_web3) as web3_cls:
        web3_cls.HTTPProvider = MagicMock()
        web3_cls.return_value = MagicMock()
        from skillware.core.evm_config import get_web3

        client = get_web3("ethereum")
        assert client is not None
        web3_cls.HTTPProvider.assert_called_once_with("https://rpc.example/eth")


def test_resolve_rpc_url_prefers_inline_rpc_url():
    from skillware.core.evm_config import MergedEvmConfig, resolve_rpc_url

    config = MergedEvmConfig(
        version=1,
        chains={
            "anvil_local": {
                "enabled": True,
                "chain_id": 31337,
                "rpc_url": "http://127.0.0.1:8545",
                "native_symbol": "eth",
                "native_decimals": 18,
            }
        },
        tokens={},
        sources=("test",),
        resolved_config_path=None,
    )
    assert resolve_rpc_url("anvil_local", config=config) == "http://127.0.0.1:8545"


def test_init_evm_refuses_existing_without_force(tmp_path):
    target = tmp_path / "evm.yaml"
    target.write_text("version: 1\nchains: {}\n", encoding="utf-8")
    with pytest.raises(FileExistsError):
        init_evm_config_file(target, overwrite=False)


def test_add_token_degen_on_base(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILLWARE_CONFIG_DIR", str(tmp_path))
    from skillware.core.evm_config import add_token_to_config, default_global_evm_path

    path = default_global_evm_path()
    init_evm_config_file(path, overwrite=True, enabled_chains=["base"])
    add_token_to_config(
        path,
        "base",
        "degen",
        {
            "address": "0x4ed4E862860beD51a9570b96d89aF5E1B0Efefed",
            "decimals": 18,
        },
    )
    merged = load_merged_evm_config(refresh=True)
    assert merged.tokens["base"]["degen"]["decimals"] == 18


def test_add_chain_and_enable_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILLWARE_CONFIG_DIR", str(tmp_path))
    from skillware.core.evm_config import (
        add_chain_to_config,
        default_global_evm_path,
        enable_chain_in_config,
        load_evm_yaml,
    )

    path = default_global_evm_path()
    init_evm_config_file(path, overwrite=True, enabled_chains=["base"])
    add_chain_to_config(
        path,
        "optimism",
        {
            "enabled": False,
            "chain_id": 10,
            "rpc_env": "OPTIMISM_RPC_URL",
            "native_symbol": "eth",
            "native_decimals": 18,
        },
    )
    enable_chain_in_config(path, "optimism")
    data = load_evm_yaml(path)
    assert data["chains"]["optimism"]["enabled"] is True
    assert data["chains"]["ethereum"]["enabled"] is False


def test_invalid_address_rejected():
    with pytest.raises(ValueError, match="Invalid EVM address"):
        normalize_evm_address("0x123")


def test_web3_alias_merge(tmp_path, monkeypatch):
    config_dir = tmp_path / "cfg"
    config_dir.mkdir()
    monkeypatch.setenv(GLOBAL_CONFIG_DIR_ENV, str(config_dir))
    _write(
        config_dir / "config.yaml",
        """
web3:
  chains:
    optimism:
      enabled: true
      chain_id: 10
      rpc_env: OPTIMISM_RPC_URL
      native_symbol: eth
      native_decimals: 18
""",
    )
    merged = load_merged_evm_config(refresh=True)
    assert merged.chains["optimism"]["chain_id"] == 10
