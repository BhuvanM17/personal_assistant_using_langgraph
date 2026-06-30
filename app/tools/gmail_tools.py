import base64
from email.mime.text import MIMEText
from typing import List, Dict, Any
from langchain_core.tools import tool
from app.auth.google_auth import get_gmail_service


def _extract_body_text(payload: dict) -> str:
    """Recursively extracts plain text body from a Gmail message payload."""
    body_text = ""

    mime_type = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data", "")

    if mime_type == "text/plain" and body_data:
        body_text = base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")
    elif mime_type.startswith("multipart/"):
        for part in payload.get("parts", []):
            extracted = _extract_body_text(part)
            if extracted:
                body_text = extracted
                if part.get("mimeType") == "text/plain":
                    break  # Prefer plain text over HTML

    return body_text


@tool
def read_emails(query: str = "is:unread", max_results: int = 5, include_body: bool = False) -> List[Dict[str, Any]]:
    """Reads Gmail messages based on a query and returns summaries with optional full body.

    Args:
        query: Gmail search query (e.g. 'is:unread', 'from:manager', 'subject:complaint',
               'newer_than:2d', '{complaint OR issue OR problem}').
               Supports all Gmail search operators.
        max_results: Maximum number of emails to retrieve.
        include_body: If True, fetches the full plain-text body of each email.

    Returns:
        A list of dictionary objects, each representing an email message.
    """
    try:
        service = get_gmail_service()
        results = service.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
        messages = results.get("messages", [])

        summaries = []
        for msg in messages:
            msg_id = msg["id"]
            thread_id = msg["threadId"]

            # Fetch email details
            fmt = "full" if include_body else "metadata"
            detail = service.users().messages().get(
                userId="me", id=msg_id, format=fmt,
                metadataHeaders=["From", "To", "Subject", "Date", "Message-ID"]
            ).execute()

            headers = detail.get("payload", {}).get("headers", [])
            sender = next((h["value"] for h in headers if h["name"].lower() == "from"), "Unknown")
            to = next((h["value"] for h in headers if h["name"].lower() == "to"), "")
            subject = next((h["value"] for h in headers if h["name"].lower() == "subject"), "(No Subject)")
            date = next((h["value"] for h in headers if h["name"].lower() == "date"), "")
            msg_id_header = next((h["value"] for h in headers if h["name"].lower() == "message-id"), "")
            snippet = detail.get("snippet", "")

            email_data = {
                "id": msg_id,
                "thread_id": thread_id,
                "sender": sender,
                "to": to,
                "subject": subject,
                "snippet": snippet,
                "date": date,
                "message_id_header": msg_id_header
            }

            if include_body:
                body = _extract_body_text(detail.get("payload", {}))
                # Truncate very long bodies to avoid token overload
                email_data["body"] = body[:3000] if body else snippet

            summaries.append(email_data)
        return summaries
    except Exception as e:
        return [{"error": f"Failed to read emails: {str(e)}"}]


@tool
def get_email_body(email_id: str) -> Dict[str, Any]:
    """Fetches the full body content of a specific email by its message ID.

    Use this when you have an email ID and need to read the full message content.

    Args:
        email_id: The Gmail message ID to fetch.

    Returns:
        Dict containing the email headers and full body text.
    """
    try:
        service = get_gmail_service()
        detail = service.users().messages().get(userId="me", id=email_id, format="full").execute()

        headers = detail.get("payload", {}).get("headers", [])
        sender = next((h["value"] for h in headers if h["name"].lower() == "from"), "Unknown")
        to = next((h["value"] for h in headers if h["name"].lower() == "to"), "")
        subject = next((h["value"] for h in headers if h["name"].lower() == "subject"), "(No Subject)")
        date = next((h["value"] for h in headers if h["name"].lower() == "date"), "")

        body = _extract_body_text(detail.get("payload", {}))

        return {
            "id": email_id,
            "thread_id": detail.get("threadId", ""),
            "sender": sender,
            "to": to,
            "subject": subject,
            "date": date,
            "body": body[:5000] if body else detail.get("snippet", ""),
        }
    except Exception as e:
        return {"error": f"Failed to get email body: {str(e)}"}


@tool
def search_emails(
    keywords: str = "",
    sender: str = "",
    newer_than: str = "7d",
    max_results: int = 10,
) -> List[Dict[str, Any]]:
    """Searches Gmail with advanced filters and returns emails with full body content.

    This is the best tool for finding specific emails. Use this when the user asks about
    emails with certain topics, complaints, issues, or from specific people.

    Args:
        keywords: Search keywords or phrases. Use Gmail OR syntax for multiple terms,
                  e.g. '{complaint OR issue OR problem OR outage}'.
        sender: Filter by sender email (e.g. 'boss@company.com'). Leave empty for all senders.
        newer_than: Only return emails newer than this duration (e.g. '1d', '3d', '7d', '30d').
        max_results: Maximum number of results to return.

    Returns:
        A list of email dictionaries with full body content for analysis.
    """
    try:
        # Build Gmail search query
        query_parts = []
        if keywords:
            query_parts.append(keywords)
        if sender:
            query_parts.append(f"from:{sender}")
        if newer_than:
            query_parts.append(f"newer_than:{newer_than}")

        query = " ".join(query_parts) if query_parts else "is:inbox"

        service = get_gmail_service()
        results = service.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
        messages = results.get("messages", [])

        email_list = []
        for msg in messages:
            msg_id = msg["id"]
            thread_id = msg["threadId"]

            detail = service.users().messages().get(userId="me", id=msg_id, format="full").execute()

            headers = detail.get("payload", {}).get("headers", [])
            email_sender = next((h["value"] for h in headers if h["name"].lower() == "from"), "Unknown")
            to = next((h["value"] for h in headers if h["name"].lower() == "to"), "")
            subject = next((h["value"] for h in headers if h["name"].lower() == "subject"), "(No Subject)")
            date = next((h["value"] for h in headers if h["name"].lower() == "date"), "")

            body = _extract_body_text(detail.get("payload", {}))

            email_list.append({
                "id": msg_id,
                "thread_id": thread_id,
                "sender": email_sender,
                "to": to,
                "subject": subject,
                "date": date,
                "snippet": detail.get("snippet", ""),
                "body": body[:3000] if body else detail.get("snippet", ""),
            })

        return email_list
    except Exception as e:
        return [{"error": f"Failed to search emails: {str(e)}"}]


@tool
def draft_reply(thread_id: str, body: str) -> Dict[str, Any]:
    """Creates a draft reply threaded to the original message/thread.

    Args:
        thread_id: The thread ID (or message ID) of the email to reply to.
        body: The markdown/text content of the draft reply.

    Returns:
        Dict containing status and draft_id.
    """
    try:
        service = get_gmail_service()

        # Get the original thread or message to reply to
        # First try to get the thread to find the latest message details
        thread = service.users().threads().get(userId="me", id=thread_id).execute()
        messages = thread.get("messages", [])

        if not messages:
            return {"error": f"No messages found for thread ID: {thread_id}"}

        # Reply to the latest message in the thread
        orig_msg = messages[-1]
        orig_headers = orig_msg.get("payload", {}).get("headers", [])

        # Find headers for thread continuation
        to_email = next((h["value"] for h in orig_headers if h["name"].lower() == "from"), "")
        subject = next((h["value"] for h in orig_headers if h["name"].lower() == "subject"), "")
        msg_id = next((h["value"] for h in orig_headers if h["name"].lower() == "message-id"), "")

        # Set reply subject
        if subject and not subject.lower().startswith("re:"):
            subject = "Re: " + subject

        # Compose MIME message
        mime_msg = MIMEText(body)
        mime_msg["To"] = to_email
        mime_msg["Subject"] = subject

        # Set threading headers
        if msg_id:
            mime_msg["In-Reply-To"] = msg_id
            mime_msg["References"] = msg_id

        # Encode message
        raw = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode("utf-8")

        draft_body = {
            "message": {
                "threadId": thread_id,
                "raw": raw
            }
        }

        draft = service.users().drafts().create(userId="me", body=draft_body).execute()
        return {
            "status": "drafted",
            "draft_id": draft["id"],
            "thread_id": thread_id,
            "to": to_email,
            "subject": subject
        }
    except Exception as e:
        return {"error": f"Failed to draft reply: {str(e)}"}


@tool
def send_reply(thread_id: str, body: str) -> Dict[str, Any]:
    """Sends a reply email directly in the existing Gmail thread.

    Args:
        thread_id: The thread ID (or message ID) of the email to reply to.
        body: The markdown/text content of the reply.

    Returns:
        Dict containing send status and Gmail message metadata.
    """
    try:
        service = get_gmail_service()

        thread = service.users().threads().get(userId="me", id=thread_id).execute()
        messages = thread.get("messages", [])
        if not messages:
            return {"error": f"No messages found for thread ID: {thread_id}"}

        orig_msg = messages[-1]
        orig_headers = orig_msg.get("payload", {}).get("headers", [])

        to_email = next((h["value"] for h in orig_headers if h["name"].lower() == "from"), "")
        subject = next((h["value"] for h in orig_headers if h["name"].lower() == "subject"), "")
        msg_id = next((h["value"] for h in orig_headers if h["name"].lower() == "message-id"), "")

        if subject and not subject.lower().startswith("re:"):
            subject = "Re: " + subject

        mime_msg = MIMEText(body)
        mime_msg["To"] = to_email
        mime_msg["Subject"] = subject

        if msg_id:
            mime_msg["In-Reply-To"] = msg_id
            mime_msg["References"] = msg_id

        raw = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode("utf-8")
        sent_message = (
            service.users()
            .messages()
            .send(
                userId="me",
                body={
                    "threadId": thread_id,
                    "raw": raw,
                },
            )
            .execute()
        )

        return {
            "status": "sent",
            "message_id": sent_message.get("id"),
            "thread_id": sent_message.get("threadId", thread_id),
            "to": to_email,
            "subject": subject,
        }
    except Exception as e:
        return {"error": f"Failed to send reply: {str(e)}"}
