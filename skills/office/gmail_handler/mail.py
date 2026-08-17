"""SMTP/IMAP transport, message parsing, scan state, and send ledger."""

from __future__ import annotations

import email
import imaplib
import json
import os
import re
import smtplib
import ssl
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr, parseaddr, parsedate_to_datetime
from html import unescape
from typing import Any, Dict, List, Optional, Sequence, Tuple

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_address_header(value: str) -> Tuple[str, str]:
    name, addr = parseaddr(value or "")
    return (addr or "").strip(), (name or "").strip()


def strip_html(html: str) -> str:
    text = _HTML_TAG_RE.sub(" ", html or "")
    return " ".join(unescape(text).split())


def extract_bodies(msg: email.message.Message) -> Tuple[str, Optional[str]]:
    plain = ""
    html = None

    if msg.is_multipart():
        for part in msg.walk():
            content_type = (part.get_content_type() or "").lower()
            disposition = (part.get("Content-Disposition") or "").lower()
            if "attachment" in disposition:
                continue
            payload = part.get_payload(decode=True)
            if payload is None:
                continue
            charset = part.get_content_charset() or "utf-8"
            try:
                decoded = payload.decode(charset, errors="replace")
            except LookupError:
                decoded = payload.decode("utf-8", errors="replace")
            if content_type == "text/plain" and not plain:
                plain = decoded
            elif content_type == "text/html" and html is None:
                html = decoded
    else:
        payload = msg.get_payload(decode=True)
        if payload is not None:
            charset = msg.get_content_charset() or "utf-8"
            try:
                decoded = payload.decode(charset, errors="replace")
            except LookupError:
                decoded = payload.decode("utf-8", errors="replace")
            if (msg.get_content_type() or "").lower() == "text/html":
                html = decoded
            else:
                plain = decoded

    if not plain and html:
        plain = strip_html(html)
    html_stripped = strip_html(html) if html else None
    return plain.strip(), html_stripped


def message_snippet(text: str, limit: int = 240) -> str:
    compact = " ".join((text or "").split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


class JsonStateStore:
    """Small JSON persistence helper for scan cursor and send ledger."""

    def __init__(self, path: str):
        self.path = path

    def read(self) -> Dict[str, Any]:
        if not os.path.exists(self.path):
            return {}
        with open(self.path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}

    def write(self, data: Dict[str, Any]) -> None:
        directory = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, sort_keys=True)
            handle.write("\n")


class MailTransport:
    """Gmail-flavored IMAP/SMTP client using stdlib only."""

    def __init__(
        self,
        address: str,
        app_password: str,
        config: Dict[str, Any],
    ):
        self.address = address
        self.app_password = app_password
        imap_cfg = config.get("imap") or {}
        smtp_cfg = config.get("smtp") or {}
        self.imap_host = imap_cfg.get("host", "imap.gmail.com")
        self.imap_port = int(imap_cfg.get("port", 993))
        self.smtp_host = smtp_cfg.get("host", "smtp.gmail.com")
        self.smtp_port = int(smtp_cfg.get("port", 465))
        self.inbox_folder = imap_cfg.get("inbox_folder", "INBOX")
        self.sent_folder = imap_cfg.get("sent_folder", "[Gmail]/Sent Mail")

    def _imap_login(self) -> imaplib.IMAP4_SSL:
        client = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
        client.login(self.address, self.app_password)
        return client

    def _smtp_send(self, msg: EmailMessage) -> str:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, context=context) as smtp:
            smtp.login(self.address, self.app_password)
            refused = smtp.send_message(msg)
        if refused:
            raise RuntimeError(f"SMTP refused recipients: {refused}")
        return "250 2.0.0 OK"

    def mailbox_status(self, folder: Optional[str] = None) -> Dict[str, Any]:
        folder = folder or self.inbox_folder
        client = self._imap_login()
        try:
            status, data = client.select(folder, readonly=True)
            if status != "OK":
                raise RuntimeError(f"IMAP select failed for {folder!r}: {status}")
            unread = 0
            status, unread_data = client.search(None, "UNSEEN")
            if status == "OK" and unread_data and unread_data[0]:
                unread = len(unread_data[0].split())
            status, uid_data = client.uid("search", None, "ALL")
            highest_uid = 0
            if status == "OK" and uid_data and uid_data[0]:
                uids = [int(x) for x in uid_data[0].split()]
                highest_uid = max(uids) if uids else 0
            return {
                "mailbox": folder,
                "unread_count": unread,
                "highest_uid": highest_uid,
            }
        finally:
            try:
                client.logout()
            except Exception:
                pass

    def search_uids(
        self,
        folder: str,
        since_uid: Optional[int] = None,
        unread_only: bool = False,
        from_email: Optional[str] = None,
        to_email: Optional[str] = None,
    ) -> List[int]:
        client = self._imap_login()
        try:
            status, _ = client.select(folder, readonly=True)
            if status != "OK":
                raise RuntimeError(f"IMAP select failed for {folder!r}: {status}")

            criteria = []
            if unread_only:
                criteria.append("UNSEEN")
            if from_email:
                criteria.append(f'FROM "{from_email}"')
            if to_email:
                criteria.append(f'TO "{to_email}"')

            if since_uid is not None:
                criteria = ["UID", f"{int(since_uid) + 1}:*"] + criteria

            if criteria:
                status, data = client.uid("search", None, *criteria)
            else:
                status, data = client.uid("search", None, "ALL")

            if status != "OK" or not data or not data[0]:
                return []

            uids = sorted(int(x) for x in data[0].split())
            if since_uid is not None:
                uids = [uid for uid in uids if uid > int(since_uid)]
            return uids
        finally:
            try:
                client.logout()
            except Exception:
                pass

    def fetch_summaries(
        self,
        folder: str,
        uids: Sequence[int],
        limit: int,
    ) -> List[Dict[str, Any]]:
        if not uids:
            return []
        selected = list(uids)[-limit:]
        selected.reverse()
        client = self._imap_login()
        summaries: List[Dict[str, Any]] = []
        try:
            status, _ = client.select(folder, readonly=True)
            if status != "OK":
                raise RuntimeError(f"IMAP select failed for {folder!r}: {status}")

            for uid in selected:
                status, data = client.uid(
                    "fetch",
                    str(uid),
                    "(BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT DATE MESSAGE-ID)] FLAGS)",
                )
                if status != "OK" or not data or not isinstance(data[0], tuple):
                    continue
                raw = data[0][1]
                if isinstance(raw, bytes):
                    header_msg = email.message_from_bytes(raw)
                else:
                    header_msg = email.message_from_string(str(raw))

                from_addr, from_name = parse_address_header(header_msg.get("From", ""))
                subject = header_msg.get("Subject", "")
                date_hdr = header_msg.get("Date", "")
                flags_line = data[0][0].decode(errors="replace") if data[0][0] else ""
                unread = "\\Seen" not in flags_line

                summaries.append(
                    {
                        "uid": uid,
                        "from": (
                            formataddr((from_name, from_addr))
                            if from_name
                            else from_addr
                        ),
                        "from_email": from_addr,
                        "to": header_msg.get("To", ""),
                        "subject": subject,
                        "date": date_hdr,
                        "message_id": header_msg.get("Message-ID", ""),
                        "snippet": "",
                        "unread": unread,
                        "folder": folder,
                    }
                )
        finally:
            try:
                client.logout()
            except Exception:
                pass
        return summaries

    def fetch_message(
        self,
        folder: str,
        uid: int,
        mark_as_read: bool = False,
    ) -> Dict[str, Any]:
        client = self._imap_login()
        try:
            status, _ = client.select(folder, readonly=not mark_as_read)
            if status != "OK":
                raise RuntimeError(f"IMAP select failed for {folder!r}: {status}")

            fetch_cmd = "(RFC822)" if mark_as_read else "(BODY.PEEK[])"
            status, data = client.uid("fetch", str(uid), fetch_cmd)
            if status != "OK" or not data or not isinstance(data[0], tuple):
                raise RuntimeError(f"Message UID {uid} not found in {folder!r}")

            raw = data[0][1]
            if not isinstance(raw, (bytes, bytearray)):
                raise RuntimeError(f"Unexpected IMAP payload for UID {uid}")

            msg = email.message_from_bytes(raw)
            from_addr, from_name = parse_address_header(msg.get("From", ""))
            to_addrs = [
                parse_address_header(x)[0]
                for x in (msg.get("To") or "").split(",")
                if x.strip()
            ]
            plain, html_stripped = extract_bodies(msg)
            references = [
                ref.strip()
                for ref in (msg.get("References") or "").split()
                if ref.strip()
            ]

            if mark_as_read:
                client.uid("store", str(uid), "+FLAGS", "(\\Seen)")

            return {
                "uid": uid,
                "folder": folder,
                "from": formataddr((from_name, from_addr)) if from_name else from_addr,
                "from_email": from_addr,
                "to": to_addrs,
                "subject": msg.get("Subject", ""),
                "date": msg.get("Date", ""),
                "body_plain": plain,
                "body_html_stripped": html_stripped,
                "message_id": msg.get("Message-ID", ""),
                "in_reply_to": msg.get("In-Reply-To", ""),
                "references": references,
                "untrusted_content": True,
                "snippet": message_snippet(plain),
            }
        finally:
            try:
                client.logout()
            except Exception:
                pass

    def send_message(
        self,
        to: Sequence[str],
        subject: str,
        body_plain: str,
        cc: Optional[Sequence[str]] = None,
        bcc: Optional[Sequence[str]] = None,
        body_html: Optional[str] = None,
        reply_to: Optional[str] = None,
        in_reply_to: Optional[str] = None,
        references: Optional[Sequence[str]] = None,
    ) -> Tuple[str, str]:
        msg = EmailMessage()
        msg["From"] = self.address
        msg["To"] = ", ".join(to)
        if cc:
            msg["Cc"] = ", ".join(cc)
        if bcc:
            msg["Bcc"] = ", ".join(bcc)
        msg["Subject"] = subject
        if reply_to:
            msg["Reply-To"] = reply_to
        if in_reply_to:
            msg["In-Reply-To"] = in_reply_to
        if references:
            msg["References"] = " ".join(references)

        msg.set_content(body_plain or "")
        if body_html:
            msg.add_alternative(body_html, subtype="html")

        smtp_response = self._smtp_send(msg)
        message_id = msg.get("Message-ID") or ""
        return message_id, smtp_response

    @staticmethod
    def filter_summaries(
        summaries: Sequence[Dict[str, Any]],
        domains: Optional[Sequence[str]] = None,
        keywords: Optional[Sequence[str]] = None,
        from_emails: Optional[Sequence[str]] = None,
        to_emails: Optional[Sequence[str]] = None,
        direction: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        domain_set = {d.casefold().lstrip("@") for d in (domains or [])}
        keyword_set = [(k or "").casefold() for k in (keywords or []) if k]
        from_set = {e.casefold() for e in (from_emails or []) if e}
        to_set = {e.casefold() for e in (to_emails or []) if e}
        out: List[Dict[str, Any]] = []

        for item in summaries:
            from_email = (item.get("from_email") or "").casefold()
            subject = (item.get("subject") or "").casefold()
            snippet = (item.get("snippet") or "").casefold()
            to_field = (item.get("to") or "").casefold()

            if from_set and from_email not in from_set:
                continue
            if to_set and not any(addr in to_field for addr in to_set):
                continue
            if domain_set:
                email_domain = from_email.split("@")[-1] if "@" in from_email else ""
                if email_domain not in domain_set:
                    continue
            if keyword_set:
                haystack = " ".join([subject, snippet, item.get("from", "").casefold()])
                if not any(k in haystack for k in keyword_set):
                    continue
            if direction == "inbound" and item.get("folder") != "INBOX":
                continue
            if direction == "outbound" and "Sent" not in str(item.get("folder", "")):
                continue
            out.append(dict(item))
        return out

    @staticmethod
    def sort_by_date_desc(items: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        def sort_key(row: Dict[str, Any]) -> datetime:
            raw = row.get("date") or ""
            try:
                return parsedate_to_datetime(raw)
            except (TypeError, ValueError, IndexError):
                return datetime.min.replace(tzinfo=timezone.utc)

        return sorted(items, key=sort_key, reverse=True)
