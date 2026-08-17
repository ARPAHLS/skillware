import json
import os
from unittest.mock import MagicMock, patch

import pytest
import yaml

from .addressbook import AddressBookResolver
from .mail import extract_bodies, message_snippet, strip_html
from .skill import GmailHandlerSkill


@pytest.fixture
def temp_paths(tmp_path):
    addressbook = tmp_path / "addressbook.yaml"
    addressbook.write_text(
        yaml.safe_dump(
            {
                "contacts": {
                    "george": {
                        "display_name": "George Papadopoulos",
                        "emails": ["george.pap@acme.com"],
                        "aliases": ["George", "G. Pap"],
                    },
                    "john_taller": {
                        "display_name": "John Taller",
                        "emails": ["john@skillware.site"],
                        "aliases": ["John", "Jon"],
                    },
                    "john_smith": {
                        "display_name": "John Smith",
                        "emails": ["john.smith@example.com"],
                        "aliases": ["John", "John Smith"],
                    },
                },
                "org_domains": {
                    "capgemini": {
                        "domains": ["capgemini.com"],
                        "keywords": ["Capgemini"],
                    }
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    scan_state = tmp_path / "scan.json"
    send_ledger = tmp_path / "ledger.json"
    return {
        "addressbook": str(addressbook),
        "scan_state": str(scan_state),
        "send_ledger": str(send_ledger),
    }


@pytest.fixture
def skill(temp_paths):
    with patch.dict(
        os.environ,
        {
            "GMAIL_ADDRESS": "agent@example.com",
            "GMAIL_APP_PASSWORD": "app-password",
            "GMAIL_ADDRESSBOOK_PATH": temp_paths["addressbook"],
            "GMAIL_SCAN_STATE_PATH": temp_paths["scan_state"],
            "GMAIL_SEND_LEDGER_PATH": temp_paths["send_ledger"],
        },
        clear=False,
    ):
        yield GmailHandlerSkill(config={})


@pytest.fixture
def manifest():
    path = os.path.join(os.path.dirname(__file__), "manifest.yaml")
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_manifest_consistency(skill, manifest):
    loaded = skill.manifest
    assert loaded["name"] == manifest["name"]
    assert loaded["version"] == manifest["version"]
    assert "resolve_recipients" in loaded["parameters"]["properties"]["action"]["enum"]


def test_missing_action(skill):
    result = skill.execute({})
    assert result["status"] == "error"
    assert result["code"] == "missing_action"


def test_invalid_action(skill):
    result = skill.execute({"action": "nope"})
    assert result["status"] == "error"
    assert result["code"] == "invalid_action"


def test_resolve_recipients_exact_alias(skill):
    result = skill.execute(
        {"action": "resolve_recipients", "query": ["George"]},
    )
    assert result["status"] == "ready"
    assert result["resolved"][0]["email"] == "george.pap@acme.com"
    assert result["ambiguous"] == []


def test_resolve_recipients_explicit_email(skill):
    result = skill.execute(
        {
            "action": "resolve_recipients",
            "query": ["george.pap@acme.com"],
        }
    )
    assert result["status"] == "ready"
    assert result["resolved"][0]["source"] == "addressbook:george"


def test_resolve_recipients_ambiguous_john(skill):
    result = skill.execute(
        {"action": "resolve_recipients", "query": ["John"]},
    )
    assert result["status"] == "needs_input"
    assert len(result["ambiguous"]) == 1
    assert len(result["ambiguous"][0]["candidates"]) == 2


def test_preview_send_missing_subject(skill):
    result = skill.execute(
        {
            "action": "preview_send",
            "to": ["George"],
            "body_plain": "Hello George",
        }
    )
    assert result["status"] == "needs_input"
    assert "subject" in result["missing_fields"]
    assert result["preview"]["to"] == ["george.pap@acme.com"]


def test_preview_send_ready(skill):
    result = skill.execute(
        {
            "action": "preview_send",
            "to": ["George"],
            "subject": "Templates ready",
            "body_plain": "Delivery by EOD.",
        }
    )
    assert result["status"] == "ready"
    assert result["needs_confirmation"] is True
    assert result["preview"]["recipient_count"] == 1


def test_send_requires_confirmation(skill):
    result = skill.execute(
        {
            "action": "send",
            "to": ["George"],
            "subject": "Hello",
            "body_plain": "Body",
        }
    )
    assert result["status"] == "needs_confirmation"


@patch.object(GmailHandlerSkill, "_get_transport")
def test_send_success(mock_transport, skill, temp_paths):
    transport = MagicMock()
    transport.send_message.return_value = ("<msg-id@test>", "250 OK")
    mock_transport.return_value = transport

    result = skill.execute(
        {
            "action": "send",
            "confirmed": True,
            "to": ["George"],
            "subject": "Hello",
            "body_plain": "Body",
        }
    )
    assert result["status"] == "sent"
    transport.send_message.assert_called_once()

    with open(temp_paths["send_ledger"], "r", encoding="utf-8") as handle:
        ledger = json.load(handle)
    assert len(ledger["entries"]) == 1


def test_send_recipient_cap(skill):
    capped = GmailHandlerSkill(config={})
    capped.skill_config = {**skill.skill_config, "max_recipients": 1}
    capped._addressbook_path = skill._addressbook_path
    capped._addressbook = skill._addressbook
    result = capped.execute(
        {
            "action": "preview_send",
            "to": ["George", "john@skillware.site"],
            "subject": "Hi",
            "body_plain": "Body",
        }
    )
    assert result["status"] == "error"
    assert result["code"] == "validation_error"


@patch.object(GmailHandlerSkill, "_get_transport")
def test_search_messages(mock_transport, skill, temp_paths):
    transport = MagicMock()
    transport.search_uids.return_value = [100, 101]
    transport.fetch_summaries.return_value = [
        {
            "uid": 101,
            "from": "Peter <peter@capgemini.com>",
            "from_email": "peter@capgemini.com",
            "to": "agent@example.com",
            "subject": "Capgemini sync",
            "date": "Sun, 24 May 2026 14:32:00 +0300",
            "snippet": "",
            "unread": True,
            "folder": "INBOX",
        }
    ]
    mock_transport.return_value = transport

    result = skill.execute(
        {
            "action": "search_messages",
            "domains": ["capgemini.com"],
            "keywords": ["Capgemini"],
            "since_uid": 100,
            "update_cursor": True,
        }
    )
    assert result["status"] == "ready"
    assert result["match_count"] == 1
    assert result["matches"][0]["uid"] == 101
    assert os.path.exists(temp_paths["scan_state"])


@patch.object(GmailHandlerSkill, "_get_transport")
def test_read_message(mock_transport, skill):
    transport = MagicMock()
    transport.fetch_message.return_value = {
        "uid": 55,
        "from_email": "john@skillware.site",
        "body_plain": "See you Friday",
        "untrusted_content": True,
        "message_id": "<abc@mail>",
    }
    mock_transport.return_value = transport

    result = skill.execute({"action": "read_message", "uid": 55})
    assert result["status"] == "ready"
    assert result["message"]["untrusted_content"] is True
    assert result["context"]["selected_uid"] == 55


@patch.object(GmailHandlerSkill, "_get_transport")
def test_preview_reply(mock_transport, skill):
    transport = MagicMock()
    transport.fetch_message.return_value = {
        "uid": 55,
        "from_email": "peter@capgemini.com",
        "subject": "Sync next week",
        "body_plain": "Tuesday works",
        "message_id": "<orig@mail>",
        "references": [],
    }
    mock_transport.return_value = transport

    result = skill.execute(
        {
            "action": "preview_reply",
            "uid": 55,
            "body_plain": "Can we do 10:30 instead?",
        }
    )
    assert result["status"] == "ready"
    assert result["preview"]["subject"].startswith("Re:")
    assert result["preview"]["in_reply_to"] == "<orig@mail>"


def test_mailbox_status_without_credentials(temp_paths):
    with patch.dict(os.environ, {}, clear=True):
        instance = GmailHandlerSkill(config={})
        instance._addressbook_path = temp_paths["addressbook"]
        result = instance.execute({"action": "mailbox_status"})
    assert result["status"] == "ready"
    assert result["credentials_configured"] is False


def test_update_addressbook(skill, temp_paths):
    result = skill.execute(
        {
            "action": "update_addressbook",
            "operation": "upsert",
            "entry": {
                "contact_id": "patrick",
                "display_name": "Patrick Lane",
                "emails": ["patrick@example.com"],
                "aliases": ["Patrick"],
            },
        }
    )
    assert result["status"] == "ready"
    with open(temp_paths["addressbook"], "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    assert "patrick" in data["contacts"]


def test_context_carry_forward(skill):
    first = skill.execute(
        {"action": "resolve_recipients", "query": ["George"]},
    )
    context = first["context"]
    second = skill.execute(
        {
            "action": "preview_send",
            "context": context,
            "to": ["George"],
            "subject": "Hi",
            "body_plain": "Body",
        }
    )
    assert second["status"] == "ready"
    assert second["context"]["last_action"] == "preview_send"
    assert second["context"]["resolved_recipients"]["George"] == "george.pap@acme.com"


def test_search_sent_ledger(skill, temp_paths):
    ledger = {
        "entries": [
            {
                "to": ["george.pap@acme.com"],
                "subject": "Templates ready",
                "sent_at": "2026-05-24T12:00:00+00:00",
                "message_id": "<sent@mail>",
                "action": "send",
            }
        ]
    }
    with open(temp_paths["send_ledger"], "w", encoding="utf-8") as handle:
        json.dump(ledger, handle)

    with patch.object(GmailHandlerSkill, "_get_transport") as mock_transport:
        transport = MagicMock()
        transport.search_uids.return_value = []
        transport.fetch_summaries.return_value = []
        mock_transport.return_value = transport

        result = skill.execute(
            {
                "action": "search_sent",
                "to_names": ["George"],
                "limit": 5,
            }
        )
    assert result["status"] == "ready"
    assert result["ledger_matches"]
    assert result["ledger_matches"][0]["subject"] == "Templates ready"


def test_addressbook_resolver_org_domain():
    book = {
        "contacts": {
            "peter": {
                "display_name": "Peter Janssen",
                "emails": ["peter@capgemini.com"],
                "org": "Capgemini",
            }
        },
        "org_domains": {
            "capgemini": {
                "domains": ["capgemini.com"],
                "keywords": ["Capgemini"],
            }
        },
    }
    resolver = AddressBookResolver(book)
    resolved, ambiguous, unresolved = resolver.resolve_queries(["Capgemini"])
    assert not unresolved
    assert not ambiguous
    assert resolved[0].email == "peter@capgemini.com"


def test_extract_bodies_plain():
    from email.message import EmailMessage

    msg = EmailMessage()
    msg.set_content("Hello plain")
    plain, html = extract_bodies(msg)
    assert plain == "Hello plain"
    assert html is None


def test_strip_html_helper():
    assert "Hello" in strip_html("<p>Hello <b>world</b></p>")


def test_message_snippet_truncates():
    text = "word " * 100
    assert message_snippet(text, limit=20).endswith("…")
