"""Tests for mail operator configuration."""

from pathlib import Path

import pytest
import yaml

from skillware.core.config import (
    GLOBAL_CONFIG_DIR_ENV,
    PROJECT_CONFIG_FILENAME,
    clear_config_cache,
    load_merged_config,
)
from skillware.core.mail_config import (
    ARPACORP_URL,
    DEFAULT_SIGNATURE_HTML,
    DEFAULT_SIGNATURE_PLAIN,
    ENV_ADDRESSBOOK_PATH,
    ENV_SIGNATURE_PLAIN,
    MailSettings,
    SKILLWARE_GITHUB_URL,
    SKILLWARE_SITE_URL,
    add_addressbook_contact,
    init_signature_bundle,
    init_addressbook_file,
    load_project_mail_settings,
    merge_mail_settings,
    parse_mail_block,
    resolve_addressbook_path,
    resolve_signature_html,
    resolve_signature_plain,
    resolve_signature_profile,
    save_global_mail_settings,
    save_project_mail_settings,
    set_active_signature_profile,
    upsert_signature_profile,
    slugify_contact_id,
    validate_addressbook_data,
    validate_signature_text,
)


def _write_config(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


@pytest.fixture(autouse=True)
def _reset_config_cache():
    clear_config_cache()
    yield
    clear_config_cache()


def test_parse_mail_block_and_merge():
    global_layer = parse_mail_block(
        {
            "addressbook_path": "~/.config/skillware/addressbook.yaml",
            "signature_plain": "Global sig",
        }
    )
    project_layer = parse_mail_block(
        {
            "signature_plain": "Project sig",
            "send_ledger_path": "/tmp/ledger.json",
        }
    )
    merged = merge_mail_settings([global_layer, project_layer])
    assert merged.addressbook_path == "~/.config/skillware/addressbook.yaml"
    assert merged.signature_plain == "Project sig"
    assert merged.send_ledger_path == "/tmp/ledger.json"


def test_global_and_project_mail_merge(tmp_path, monkeypatch):
    global_dir = tmp_path / "global-config"
    _write_config(
        global_dir / "config.yaml",
        "mail:\n  signature_plain: |\n    Global\n",
    )
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(
        repo / PROJECT_CONFIG_FILENAME,
        "mail:\n  addressbook_path: /tmp/ab.yaml\n",
    )
    monkeypatch.chdir(repo)
    monkeypatch.setenv(GLOBAL_CONFIG_DIR_ENV, str(global_dir))

    config = load_merged_config(refresh=True)
    assert config.mail.addressbook_path == "/tmp/ab.yaml"
    assert config.mail.signature_plain == "Global"


def test_env_overrides_signature_plain(monkeypatch):
    monkeypatch.setenv(ENV_SIGNATURE_PLAIN, "Env signature")
    text, source = resolve_signature_plain(mail=MailSettings())
    assert text == "Env signature"
    assert source == "env_plain"


def test_signature_path_wins_over_plain_in_env(monkeypatch, tmp_path):
    sig_file = tmp_path / "sig.txt"
    sig_file.write_text("From file\n", encoding="utf-8")
    monkeypatch.setenv(ENV_SIGNATURE_PLAIN, "Inline ignored")
    monkeypatch.setenv("GMAIL_SIGNATURE_PATH", str(sig_file))
    text, source = resolve_signature_plain(mail=MailSettings())
    assert text == "From file"
    assert source == "env_path"


def test_resolve_addressbook_precedence(tmp_path, monkeypatch):
    bundled = tmp_path / "bundled.yaml"
    bundled.write_text("contacts: {}\norg_domains: {}\n", encoding="utf-8")
    config_path = tmp_path / "configured.yaml"
    config_path.write_text("contacts: {}\norg_domains: {}\n", encoding="utf-8")

    mail = MailSettings(addressbook_path=str(config_path))
    resolved = resolve_addressbook_path(
        mail=mail,
        skill_data_dir=tmp_path,
        bundled_addressbook=bundled,
    )
    assert resolved == config_path.resolve()

    monkeypatch.setenv(ENV_ADDRESSBOOK_PATH, str(tmp_path / "env.yaml"))
    resolved_env = resolve_addressbook_path(mail=mail, bundled_addressbook=bundled)
    assert resolved_env == (tmp_path / "env.yaml").resolve()


def test_validate_addressbook_and_signature():
    errors = validate_addressbook_data(
        {
            "contacts": {
                "bad": {"emails": ["not-an-email"]},
            },
            "org_domains": {},
        }
    )
    assert any("invalid email" in item for item in errors)

    assert validate_signature_text("") == ["signature is empty"]
    assert not validate_signature_text("Hello\nAgent")


def test_save_project_mail_settings(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.chdir(repo)
    monkeypatch.setenv(GLOBAL_CONFIG_DIR_ENV, str(tmp_path / "no-global"))

    target = save_project_mail_settings(
        MailSettings(
            addressbook_path=str(tmp_path / "ab.yaml"),
            signature_plain="—\nAgent",
        )
    )
    assert target == (repo / PROJECT_CONFIG_FILENAME).resolve()
    loaded = load_project_mail_settings()
    assert loaded.addressbook_path == str(tmp_path / "ab.yaml")
    assert loaded.signature_plain == "—\nAgent"


def test_init_addressbook_file(tmp_path):
    path = tmp_path / "nested" / "addressbook.yaml"
    init_addressbook_file(path)
    assert path.is_file()
    data = path.read_text(encoding="utf-8")
    assert "contacts:" in data


def test_default_signature_includes_links():
    assert SKILLWARE_SITE_URL in DEFAULT_SIGNATURE_PLAIN
    assert SKILLWARE_GITHUB_URL in DEFAULT_SIGNATURE_PLAIN
    assert ARPACORP_URL in DEFAULT_SIGNATURE_PLAIN
    assert (
        'height="40"' in DEFAULT_SIGNATURE_HTML
        or "height: 40px" in DEFAULT_SIGNATURE_HTML
    )
    assert "—" in DEFAULT_SIGNATURE_HTML


def test_init_signature_bundle(tmp_path):
    txt, html, logo = init_signature_bundle(tmp_path)
    assert txt.is_file()
    assert html.is_file()
    assert logo is not None and logo.is_file()


def test_add_addressbook_contact(tmp_path):
    path = tmp_path / "addressbook.yaml"
    init_addressbook_file(path)
    cid = add_addressbook_contact(
        path,
        display_name="Jane Doe",
        email="jane@example.com",
        aliases=["Jane"],
        org="Acme",
    )
    assert cid == "jane_doe"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["contacts"]["jane_doe"]["emails"] == ["jane@example.com"]


def test_slugify_contact_id():
    assert slugify_contact_id("John Taller") == "john_taller"


def test_resolve_signature_html_from_config(tmp_path, monkeypatch):
    html_file = tmp_path / "sig.html"
    html_file.write_text("<p>HTML sig</p>", encoding="utf-8")
    mail = MailSettings(signature_html_path=str(html_file))
    text, source = resolve_signature_html(mail=mail)
    assert text == "<p>HTML sig</p>"
    assert source == "profile_html_path:default"


def test_save_global_mail_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILLWARE_CONFIG_DIR", str(tmp_path / "global"))
    target = save_global_mail_settings(
        MailSettings(addressbook_path=str(tmp_path / "ab.yaml"))
    )
    assert target.is_file()
    assert "addressbook_path" in target.read_text(encoding="utf-8")


def test_signature_profiles_resolve(tmp_path):
    html_a = tmp_path / "a.html"
    html_b = tmp_path / "b.html"
    html_a.write_text("<p>A</p>", encoding="utf-8")
    html_b.write_text("<p>B</p>", encoding="utf-8")
    mail = MailSettings(
        signature_profile="formal",
        signatures={
            "default": {"signature_html_path": str(html_a)},
            "formal": {"signature_html_path": str(html_b)},
        },
    )
    text, source = resolve_signature_html(mail=mail, profile_id="formal")
    assert text == "<p>B</p>"
    assert source == "profile_html_path:formal"
    assert resolve_signature_profile(mail=mail) == "formal"


def test_upsert_and_set_signature_profile(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.chdir(repo)
    html = tmp_path / "sig.html"
    html.write_text("<p>Formal</p>", encoding="utf-8")
    upsert_signature_profile("formal", signature_html_path=str(html))
    set_active_signature_profile("formal")
    project = load_project_mail_settings()
    assert project.signature_profile == "formal"
    assert project.signatures["formal"]["signature_html_path"] == str(html)
