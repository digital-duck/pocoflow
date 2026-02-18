"""PocoFlow Google Calendar — manage calendar events via Google Calendar API.

Demonstrates: Google API integration, OAuth2, event creation and listing.
"""

import os
import pickle
import click
from datetime import datetime, timedelta
from pocoflow import Node, Flow, Store

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    HAS_GOOGLE = True
except ImportError:
    HAS_GOOGLE = False

SCOPES = ["https://www.googleapis.com/auth/calendar"]
TOKEN_FILE = "token.pickle"
CREDENTIALS_FILE = "credentials.json"


def get_calendar_service():
    """Authenticate and return Google Calendar service."""
    if not HAS_GOOGLE:
        raise ImportError("Install google-api-python-client google-auth-oauthlib")

    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "wb") as f:
            pickle.dump(creds, f)

    return build("calendar", "v3", credentials=creds)


class ListCalendarsNode(Node):
    def exec(self, prep_result):
        service = get_calendar_service()
        result = service.calendarList().list().execute()
        return result.get("items", [])

    def post(self, store, prep_result, exec_result):
        store["calendars"] = exec_result
        print("\n=== Your Calendars ===")
        for cal in exec_result:
            print(f"  - {cal.get('summary', 'Untitled')}")
        return "done"


class CreateEventNode(Node):
    def prep(self, store):
        return {
            "summary": store["event_summary"],
            "description": store.get("event_description", ""),
            "start": store["event_start"],
            "end": store["event_end"],
        }

    def exec(self, prep_result):
        service = get_calendar_service()
        event = {
            "summary": prep_result["summary"],
            "description": prep_result["description"],
            "start": {"dateTime": prep_result["start"].isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": prep_result["end"].isoformat(), "timeZone": "UTC"},
        }
        return service.events().insert(calendarId="primary", body=event).execute()

    def post(self, store, prep_result, exec_result):
        store["created_event"] = exec_result
        print(f"\nEvent created: {exec_result.get('summary')}")
        print(f"  ID: {exec_result.get('id')}")
        print(f"  Link: {exec_result.get('htmlLink')}")
        return "default"


class ListEventsNode(Node):
    def prep(self, store):
        return store.get("days_to_list", 7)

    def exec(self, prep_result):
        service = get_calendar_service()
        now = datetime.utcnow().isoformat() + "Z"
        end = (datetime.utcnow() + timedelta(days=prep_result)).isoformat() + "Z"
        result = service.events().list(
            calendarId="primary", timeMin=now, timeMax=end,
            singleEvents=True, orderBy="startTime",
        ).execute()
        return result.get("items", [])

    def post(self, store, prep_result, exec_result):
        store["events"] = exec_result
        print(f"\n=== Upcoming Events ({len(exec_result)}) ===")
        for event in exec_result:
            start = event["start"].get("dateTime", event["start"].get("date"))
            print(f"  {start}: {event.get('summary', 'No title')}")
        return "done"


@click.group()
def cli():
    """Manage Google Calendar events with PocoFlow."""
    pass


@cli.command()
def calendars():
    """List all calendars."""
    store = Store(data={"calendars": []}, name="gcal")
    flow = Flow(start=ListCalendarsNode())
    flow.run(store)


@cli.command()
@click.argument("summary")
@click.option("--hours", default=1, help="Duration in hours")
def create(summary, hours):
    """Create a calendar event starting tomorrow."""
    start = datetime.utcnow() + timedelta(days=1)
    end = start + timedelta(hours=hours)

    create_node = CreateEventNode()
    list_node = ListEventsNode()
    create_node.then("default", list_node)

    store = Store(
        data={
            "event_summary": summary,
            "event_description": "Created by PocoFlow",
            "event_start": start,
            "event_end": end,
            "days_to_list": 7,
        },
        name="gcal",
    )

    flow = Flow(start=create_node)
    flow.run(store)


@cli.command()
@click.option("--days", default=7, help="Number of days to look ahead")
def events(days):
    """List upcoming events."""
    store = Store(data={"days_to_list": days}, name="gcal")
    flow = Flow(start=ListEventsNode())
    flow.run(store)


if __name__ == "__main__":
    cli()
