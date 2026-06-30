from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from langchain_core.tools import tool
from app.auth.google_auth import get_calendar_service

DEFAULT_TIMEZONE = "Asia/Kolkata"


@tool
def create_calendar_event(
    summary: str,
    start_datetime: str,
    end_datetime: str = "",
    description: str = "",
    attendees: str = "",
    location: str = "",
    reminder_minutes: int = 30,
) -> Dict[str, Any]:
    """Creates a new Google Calendar event.

    Args:
        summary: Title/summary of the event (e.g. 'Team standup meeting').
        start_datetime: Start date-time in ISO format (e.g. '2026-06-23T10:00:00').
        end_datetime: End date-time in ISO format. If empty, defaults to 1 hour after start.
        description: Optional longer description or agenda for the event.
        attendees: Comma-separated email addresses of attendees (e.g. 'alice@example.com,bob@example.com'). Leave empty for no attendees.
        location: Optional location string for the event.
        reminder_minutes: Popup reminder lead time in minutes. Defaults to 30 minutes.

    Returns:
        Dict containing status, event_id, and event link.
    """
    try:
        service = get_calendar_service()

        # Parse start time
        start_dt = datetime.fromisoformat(start_datetime)

        # Default end time: 1 hour after start
        if end_datetime:
            end_dt = datetime.fromisoformat(end_datetime)
        else:
            end_dt = start_dt + timedelta(hours=1)

        event_body = {
            "summary": summary,
            "start": {
                "dateTime": start_dt.isoformat(),
                "timeZone": DEFAULT_TIMEZONE,
            },
            "end": {
                "dateTime": end_dt.isoformat(),
                "timeZone": DEFAULT_TIMEZONE,
            },
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "popup", "minutes": reminder_minutes},
                ],
            },
        }

        if description:
            event_body["description"] = description

        if location:
            event_body["location"] = location

        if attendees:
            attendee_list = [
                {"email": email.strip()}
                for email in attendees.split(",")
                if email.strip()
            ]
            if attendee_list:
                event_body["attendees"] = attendee_list

        event = (
            service.events()
            .insert(calendarId="primary", body=event_body)
            .execute()
        )

        return {
            "status": "created",
            "event_id": event.get("id"),
            "summary": event.get("summary"),
            "start": event["start"].get("dateTime"),
            "end": event["end"].get("dateTime"),
            "link": event.get("htmlLink"),
        }
    except Exception as e:
        return {"error": f"Failed to create calendar event: {str(e)}"}


@tool
def list_calendar_events(
    max_results: int = 10,
    time_min: str = "",
    time_max: str = "",
) -> List[Dict[str, Any]]:
    """Lists upcoming Google Calendar events.

    Args:
        max_results: Maximum number of events to return (default 10).
        time_min: Start of time range in ISO format (e.g. '2026-06-23T00:00:00'). Defaults to now.
        time_max: End of time range in ISO format. Leave empty for no upper bound.

    Returns:
        A list of event dictionaries with id, summary, start, end, and attendees.
    """
    try:
        service = get_calendar_service()

        # Default: from now
        if time_min:
            t_min = datetime.fromisoformat(time_min).isoformat() + "+05:30"
        else:
            t_min = datetime.now().isoformat() + "+05:30"

        params = {
            "calendarId": "primary",
            "timeMin": t_min,
            "maxResults": max_results,
            "singleEvents": True,
            "orderBy": "startTime",
        }

        if time_max:
            params["timeMax"] = datetime.fromisoformat(time_max).isoformat() + "+05:30"

        events_result = service.events().list(**params).execute()
        events = events_result.get("items", [])

        results = []
        for event in events:
            start = event["start"].get("dateTime", event["start"].get("date"))
            end = event["end"].get("dateTime", event["end"].get("date"))
            attendee_emails = [
                a.get("email", "") for a in event.get("attendees", [])
            ]

            results.append(
                {
                    "event_id": event["id"],
                    "summary": event.get("summary", "(No title)"),
                    "start": start,
                    "end": end,
                    "location": event.get("location", ""),
                    "description": event.get("description", ""),
                    "attendees": attendee_emails,
                    "link": event.get("htmlLink", ""),
                }
            )

        return results
    except Exception as e:
        return [{"error": f"Failed to list calendar events: {str(e)}"}]


@tool
def delete_calendar_event(event_id: str) -> Dict[str, Any]:
    """Deletes a Google Calendar event by its event ID.

    Args:
        event_id: The unique ID of the calendar event to delete.

    Returns:
        Dict containing status of the deletion.
    """
    try:
        service = get_calendar_service()
        service.events().delete(calendarId="primary", eventId=event_id).execute()
        return {"status": "deleted", "event_id": event_id}
    except Exception as e:
        return {"error": f"Failed to delete calendar event: {str(e)}"}
