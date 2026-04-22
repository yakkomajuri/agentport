from pydantic import Field

from agent_port.integrations.types import (
    ApiTool,
    AuthMethod,
    CustomIntegration,
    OAuthAuth,
    Param,
)

_CALENDAR_OAUTH = OAuthAuth(
    method="oauth",
    provider="google",
    authorization_url="https://accounts.google.com/o/oauth2/v2/auth",
    token_url="https://oauth2.googleapis.com/token",
    scopes=["https://www.googleapis.com/auth/calendar"],
    extra_auth_params={"access_type": "offline", "prompt": "consent"},
)

_TOOL_CATEGORIES: dict[str, str] = {
    "list_calendars": "Calendars",
    "get_calendar": "Calendars",
    "list_events": "Events",
    "get_event": "Events",
    "create_event": "Events",
    "update_event": "Events",
    "delete_event": "Events",
    "quick_add_event": "Events",
    "find_free_time": "Availability",
    "list_event_instances": "Events",
    "move_event": "Events",
}

_TIME_PARAM = schema_override = {
    "type": "object",
    "properties": {
        "dateTime": {
            "type": "string",
            "description": "RFC 3339 (e.g. '2024-01-15T09:00:00-05:00')",
        },
        "date": {"type": "string", "description": "All-day date (YYYY-MM-DD)"},
        "timeZone": {"type": "string", "description": "Time zone"},
    },
}

_SEND_UPDATES_PARAM = Param(
    name="sendUpdates",
    query=True,
    enum=["all", "externalOnly", "none"],
    description="Who to send update notifications to",
)

_TOOLS: list[ApiTool] = [
    # ── Calendars ─────────────────────────────────────────────────────────
    ApiTool(
        name="list_calendars",
        description="List all calendars the user has access to, including shared calendars.",
        method="GET",
        path="/calendar/v3/users/me/calendarList",
        params=[
            Param(
                name="maxResults",
                type="integer",
                query=True,
                description="Maximum number of calendars to return",
            ),
            Param(name="pageToken", query=True, description="Token for pagination"),
            Param(
                name="showDeleted",
                type="boolean",
                query=True,
                description="Include deleted calendars",
            ),
            Param(
                name="showHidden",
                type="boolean",
                query=True,
                description="Include hidden calendars",
            ),
        ],
    ),
    ApiTool(
        name="get_calendar",
        description="Get metadata for a specific calendar.",
        method="GET",
        path="/calendar/v3/users/me/calendarList/{calendarId}",
        params=[
            Param(
                name="calendarId",
                required=True,
                description="Calendar ID (use 'primary' for the user's main calendar)",
            ),
        ],
    ),
    # ── Events ────────────────────────────────────────────────────────────
    ApiTool(
        name="list_events",
        description=(
            "List events from a calendar. Filter by time range, search query, or other criteria. "
            "Times should be in RFC 3339 format (e.g. '2024-01-15T09:00:00Z')."
        ),
        method="GET",
        path="/calendar/v3/calendars/{calendarId}/events",
        params=[
            Param(
                name="calendarId",
                required=True,
                description="Calendar ID (use 'primary' for main calendar)",
                default="primary",
            ),
            Param(
                name="timeMin",
                query=True,
                description="Start of time range (RFC 3339, e.g. '2024-01-15T00:00:00Z')",
            ),
            Param(
                name="timeMax",
                query=True,
                description="End of time range (RFC 3339, e.g. '2024-01-31T23:59:59Z')",
            ),
            Param(name="q", query=True, description="Free text search query"),
            Param(
                name="maxResults",
                type="integer",
                query=True,
                description="Maximum number of events (default 250, max 2500)",
                default=50,
            ),
            Param(name="pageToken", query=True, description="Token for pagination"),
            Param(
                name="orderBy",
                query=True,
                enum=["startTime", "updated"],
                description="Sort order (startTime requires singleEvents=true)",
            ),
            Param(
                name="singleEvents",
                type="boolean",
                query=True,
                description="Expand recurring events into single instances",
                default=True,
            ),
            Param(
                name="showDeleted", type="boolean", query=True, description="Include deleted events"
            ),
            Param(name="timeZone", query=True, description="Time zone (e.g. 'America/New_York')"),
            Param(
                name="updatedMin",
                query=True,
                description="Only events updated after this time (RFC 3339)",
            ),
        ],
    ),
    ApiTool(
        name="get_event",
        description="Get full details of a specific calendar event.",
        method="GET",
        path="/calendar/v3/calendars/{calendarId}/events/{eventId}",
        params=[
            Param(
                name="calendarId",
                required=True,
                description="Calendar ID (use 'primary' for main calendar)",
                default="primary",
            ),
            Param(name="eventId", required=True, description="The event ID"),
            Param(name="timeZone", query=True, description="Time zone for the response"),
        ],
    ),
    ApiTool(
        name="create_event",
        description=(
            "Create a new calendar event. For timed events, use start.dateTime and "
            "end.dateTime with RFC 3339 format. For all-day events, use start.date and "
            "end.date with 'YYYY-MM-DD'."
        ),
        method="POST",
        path="/calendar/v3/calendars/{calendarId}/events",
        params=[
            Param(
                name="calendarId",
                required=True,
                description="Calendar ID (use 'primary' for main calendar)",
                default="primary",
            ),
            Param(name="summary", required=True, description="Event title"),
            Param(name="description", description="Event description"),
            Param(name="location", description="Event location"),
            Param(name="start", required=True, schema_override=_TIME_PARAM),
            Param(name="end", required=True, schema_override=_TIME_PARAM),
            Param(
                name="attendees",
                type="array",
                description="List of attendees",
                schema_override={
                    "type": "array",
                    "description": "List of attendees",
                    "items": {
                        "type": "object",
                        "properties": {
                            "email": {"type": "string"},
                            "optional": {"type": "boolean"},
                        },
                        "required": ["email"],
                    },
                },
            ),
            Param(
                name="recurrence",
                type="array",
                items="string",
                description="RRULE strings (e.g. ['RRULE:FREQ=WEEKLY;COUNT=10'])",
            ),
            Param(
                name="visibility",
                enum=["default", "public", "private", "confidential"],
                description="Event visibility",
            ),
            Param(name="colorId", description="Event color ID (1-11)"),
            _SEND_UPDATES_PARAM,
        ],
    ),
    ApiTool(
        name="update_event",
        description="Update an existing calendar event. Only include fields you want to change.",
        method="PATCH",
        path="/calendar/v3/calendars/{calendarId}/events/{eventId}",
        params=[
            Param(name="calendarId", required=True, description="Calendar ID", default="primary"),
            Param(name="eventId", required=True, description="The event ID to update"),
            Param(name="summary", description="Event title"),
            Param(name="description", description="Event description"),
            Param(name="location", description="Event location"),
            Param(name="start", schema_override=_TIME_PARAM),
            Param(name="end", schema_override=_TIME_PARAM),
            Param(
                name="attendees",
                schema_override={
                    "type": "array",
                    "description": "Updated attendee list (replaces existing)",
                    "items": {
                        "type": "object",
                        "properties": {
                            "email": {"type": "string"},
                            "optional": {"type": "boolean"},
                        },
                        "required": ["email"],
                    },
                },
            ),
            Param(
                name="status",
                enum=["confirmed", "tentative", "cancelled"],
                description="Event status",
            ),
            Param(name="visibility", enum=["default", "public", "private", "confidential"]),
            Param(name="colorId", description="Event color ID"),
            _SEND_UPDATES_PARAM,
        ],
    ),
    ApiTool(
        name="delete_event",
        description="Delete a calendar event.",
        method="DELETE",
        path="/calendar/v3/calendars/{calendarId}/events/{eventId}",
        params=[
            Param(name="calendarId", required=True, description="Calendar ID", default="primary"),
            Param(name="eventId", required=True, description="The event ID to delete"),
            _SEND_UPDATES_PARAM,
        ],
    ),
    ApiTool(
        name="quick_add_event",
        description=(
            "Create an event from a natural language string "
            "(e.g. 'Meeting with Bob tomorrow at 3pm for 1 hour')."
        ),
        method="POST",
        path="/calendar/v3/calendars/{calendarId}/events/quickAdd",
        params=[
            Param(
                name="calendarId",
                required=True,
                description="Calendar ID (use 'primary' for main calendar)",
                default="primary",
            ),
            Param(
                name="text",
                required=True,
                query=True,
                description=(
                    "Natural language event description (e.g. 'Lunch with Alice Friday noon')"
                ),
            ),
            _SEND_UPDATES_PARAM,
        ],
    ),
    # ── Availability ──────────────────────────────────────────────────────
    ApiTool(
        name="find_free_time",
        description=(
            "Check free/busy information for one or more calendars. "
            "Useful for finding available meeting slots."
        ),
        method="POST",
        path="/calendar/v3/freeBusy",
        params=[
            Param(name="timeMin", required=True, description="Start of the time range (RFC 3339)"),
            Param(name="timeMax", required=True, description="End of the time range (RFC 3339)"),
            Param(name="timeZone", description="Time zone (e.g. 'America/New_York')"),
            Param(
                name="items",
                required=True,
                schema_override={
                    "type": "array",
                    "description": "Calendars to check",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string", "description": "Calendar ID or email address"}
                        },
                        "required": ["id"],
                    },
                },
            ),
        ],
    ),
    # ── Recurring event instances ─────────────────────────────────────────
    ApiTool(
        name="list_event_instances",
        description="List individual instances of a recurring event.",
        method="GET",
        path="/calendar/v3/calendars/{calendarId}/events/{eventId}/instances",
        params=[
            Param(name="calendarId", required=True, description="Calendar ID", default="primary"),
            Param(name="eventId", required=True, description="The recurring event ID"),
            Param(name="timeMin", query=True, description="Start of time range (RFC 3339)"),
            Param(name="timeMax", query=True, description="End of time range (RFC 3339)"),
            Param(name="maxResults", type="integer", query=True, description="Max results"),
            Param(name="pageToken", query=True, description="Token for pagination"),
            Param(name="timeZone", query=True, description="Time zone"),
        ],
    ),
    ApiTool(
        name="move_event",
        description="Move an event from one calendar to another.",
        method="POST",
        path="/calendar/v3/calendars/{calendarId}/events/{eventId}/move",
        params=[
            Param(name="calendarId", required=True, description="Source calendar ID"),
            Param(name="eventId", required=True, description="The event ID to move"),
            Param(
                name="destination", required=True, query=True, description="Destination calendar ID"
            ),
            _SEND_UPDATES_PARAM,
        ],
    ),
]


class GoogleCalendarIntegration(CustomIntegration):
    id: str = "google_calendar"
    name: str = "Google Calendar"
    description: str = "Schedule, manage, and search calendar events"
    docs_url: str = "https://developers.google.com/calendar/api/v3/reference"
    base_url: str = "https://www.googleapis.com"
    auth: list[AuthMethod] = Field(default=[_CALENDAR_OAUTH])
    tools: list[ApiTool] = Field(default=_TOOLS)
    tool_categories: dict[str, str] = Field(default=_TOOL_CATEGORIES)

    def is_available(self) -> tuple[bool, str | None]:
        from agent_port.config import settings

        if settings.get_oauth_credentials("google"):
            return True, None
        return (
            False,
            "Set the env vars OAUTH_GOOGLE_CLIENT_ID and "
            "OAUTH_GOOGLE_CLIENT_SECRET to use this integration.",
        )
