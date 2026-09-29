"""Constants for the Calendar Helper integration."""
from __future__ import annotations

from typing import Final

DOMAIN: Final = "calendar_helper"

# Services / Actions
SERVICE_DELETE_EVENT: Final = "delete_event"
SERVICE_DELETE_EVENTS: Final = "delete_events"
SERVICE_CLEAR_CALENDAR: Final = "clear_calendar"

# Configuration options
CONF_REGISTER_CALENDAR_SERVICES: Final = "register_calendar_services"
DEFAULT_REGISTER_CALENDAR_SERVICES: Final = True

# Service parameters
ATTR_UID: Final = "uid"
ATTR_UIDS: Final = "uids"
ATTR_SUMMARY: Final = "summary"
ATTR_SUMMARY_MATCH_MODE: Final = "summary_match_mode"
ATTR_DESCRIPTION: Final = "description"
ATTR_LOCATION: Final = "location"
ATTR_START_DATETIME: Final = "start_date_time"
ATTR_END_DATETIME: Final = "end_date_time"
ATTR_START_DATE: Final = "start_date"
ATTR_END_DATE: Final = "end_date"
ATTR_RECURRENCE_ID: Final = "recurrence_id"
ATTR_RECURRENCE_RANGE: Final = "recurrence_range"
ATTR_LIMIT: Final = "limit"
ATTR_DELETE_ALL: Final = "delete_all"
ATTR_ALL_TIME: Final = "all_time"
ATTR_DRY_RUN: Final = "dry_run"
ATTR_CONFIRM: Final = "confirm"
ATTR_ONLY_PAST: Final = "only_past"
ATTR_ONLY_FUTURE: Final = "only_future"

# Match modes for event summary
MATCH_MODE_EXACT: Final = "exact"
MATCH_MODE_EXACT_CASE_SENSITIVE: Final = "exact_case_sensitive"
MATCH_MODE_CONTAINS: Final = "contains"
MATCH_MODE_STARTSWITH: Final = "startswith"
MATCH_MODE_ENDSWITH: Final = "endswith"
MATCH_MODE_REGEX: Final = "regex"

VALID_MATCH_MODES: Final = [
    MATCH_MODE_EXACT,
    MATCH_MODE_EXACT_CASE_SENSITIVE,
    MATCH_MODE_CONTAINS,
    MATCH_MODE_STARTSWITH,
    MATCH_MODE_ENDSWITH,
    MATCH_MODE_REGEX,
]
