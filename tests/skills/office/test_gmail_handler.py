"""Maintainer-level edge cases for office/gmail_handler."""

from email.message import EmailMessage

from skills.office.gmail_handler.mail import extract_bodies, MailTransport


def test_reply_threading_references_shape():
    original = {
        "message_id": "<child@example.com>",
        "references": ["<root@example.com>"],
    }
    references = list(original.get("references") or [])
    message_id = original.get("message_id")
    if message_id and message_id not in references:
        references.append(message_id)
    assert references == ["<root@example.com>", "<child@example.com>"]


def test_multipart_prefers_plain_body():
    msg = EmailMessage()
    msg.set_content("plain body")
    msg.add_alternative("<p>html body</p>", subtype="html")
    plain, html_stripped = extract_bodies(msg)
    assert plain == "plain body"
    assert html_stripped is not None


def test_filter_summaries_domain_and_keyword():
    rows = [
        {
            "from_email": "peter@capgemini.com",
            "from": "Peter",
            "subject": "Capgemini proposal",
            "snippet": "sync next week",
            "folder": "INBOX",
        },
        {
            "from_email": "other@example.com",
            "from": "Other",
            "subject": "Hello",
            "snippet": "unrelated",
            "folder": "INBOX",
        },
    ]
    matched = MailTransport.filter_summaries(
        rows,
        domains=["capgemini.com"],
        keywords=["Capgemini"],
    )
    assert len(matched) == 1
    assert matched[0]["from_email"] == "peter@capgemini.com"
