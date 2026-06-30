import unittest
from unittest.mock import patch

from app.tools.calendar_tools import create_calendar_event
from app.tools.gmail_tools import send_reply
from app.tools.tool_registry import IRREVERSIBLE_TOOLS


class _FakeThreadGet:
    def execute(self):
        return {
            "messages": [
                {
                    "payload": {
                        "headers": [
                            {"name": "From", "value": "client@example.com"},
                            {"name": "Subject", "value": "Internet issue"},
                            {"name": "Message-ID", "value": "<msg-1@example.com>"},
                        ]
                    }
                }
            ]
        }


class _FakeThreads:
    def get(self, userId, id):
        return _FakeThreadGet()


class _FakeSend:
    def __init__(self, body):
        self.body = body

    def execute(self):
        return {
            "id": "sent-123",
            "threadId": self.body["threadId"],
        }


class _FakeMessages:
    def send(self, userId, body):
        return _FakeSend(body)


class _FakeGmailUsers:
    def threads(self):
        return _FakeThreads()

    def messages(self):
        return _FakeMessages()


class _FakeGmailService:
    def users(self):
        return _FakeGmailUsers()


class _FakeInsert:
    def __init__(self, body):
        self.body = body

    def execute(self):
        return {
            "id": "event-123",
            "summary": self.body["summary"],
            "start": {"dateTime": self.body["start"]["dateTime"]},
            "end": {"dateTime": self.body["end"]["dateTime"]},
            "htmlLink": "https://calendar.google.com/event?eid=123",
        }


class _FakeEvents:
    def __init__(self):
        self.last_body = None

    def insert(self, calendarId, body):
        self.last_body = body
        return _FakeInsert(body)


class _FakeCalendarService:
    def __init__(self):
        self._events = _FakeEvents()

    def events(self):
        return self._events


class TestAssistantBehaviors(unittest.TestCase):
    def test_irreversible_tools_are_limited_to_high_impact_actions(self):
        self.assertIn("send_reply", IRREVERSIBLE_TOOLS)
        self.assertIn("complete_task", IRREVERSIBLE_TOOLS)
        self.assertIn("delete_calendar_event", IRREVERSIBLE_TOOLS)
        self.assertNotIn("draft_reply", IRREVERSIBLE_TOOLS)
        self.assertNotIn("create_calendar_event", IRREVERSIBLE_TOOLS)

    @patch("app.tools.gmail_tools.get_gmail_service", return_value=_FakeGmailService())
    def test_send_reply_sends_threaded_email(self, _mock_service):
        result = send_reply.invoke(
            {
                "thread_id": "thread-123",
                "body": "We can meet today at 4 PM IST.",
            }
        )

        self.assertEqual(result["status"], "sent")
        self.assertEqual(result["thread_id"], "thread-123")
        self.assertEqual(result["to"], "client@example.com")
        self.assertEqual(result["subject"], "Re: Internet issue")

    def test_create_calendar_event_adds_default_reminder(self):
        fake_service = _FakeCalendarService()

        with patch("app.tools.calendar_tools.get_calendar_service", return_value=fake_service):
            result = create_calendar_event.invoke(
                {
                    "summary": "Internet issue discussion",
                    "start_datetime": "2026-06-24T16:00:00",
                    "attendees": "client@example.com",
                }
            )

        self.assertEqual(result["status"], "created")
        self.assertEqual(fake_service.events().last_body["reminders"]["overrides"][0]["minutes"], 30)
        self.assertEqual(result["end"], "2026-06-24T17:00:00")


if __name__ == "__main__":
    unittest.main()
