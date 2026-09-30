"""Calendar Helper integration for Home Assistant.

Provides actions to delete single or multiple events from local (and other supported) calendars.
"""
from __future__ import annotations

from collections.abc import Iterable
import datetime
import logging
import re
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

try:
    from homeassistant.components.calendar import CalendarEntity, CalendarEvent
except ImportError:
    CalendarEntity = Any  # type: ignore[misc,assignment]
    CalendarEvent = Any  # type: ignore[misc,assignment]

try:
    from homeassistant.components.calendar.const import (
        DATA_COMPONENT,
        CalendarEntityFeature,
    )
    DELETE_EVENT_FEATURE = CalendarEntityFeature.DELETE_EVENT
except (ImportError, AttributeError):
    DATA_COMPONENT = "calendar"  # type: ignore[misc,assignment]
    DELETE_EVENT_FEATURE = 2

from .const import (
    ATTR_ALL_TIME,
    ATTR_CONFIRM,
    ATTR_DELETE_ALL,
    ATTR_DESCRIPTION,
    ATTR_DRY_RUN,
    ATTR_END_DATE,
    ATTR_END_DATETIME,
    ATTR_LIMIT,
    ATTR_LOCATION,
    ATTR_ONLY_FUTURE,
    ATTR_ONLY_PAST,
    ATTR_RECURRENCE_ID,
    ATTR_RECURRENCE_RANGE,
    ATTR_START_DATE,
    ATTR_START_DATETIME,
    ATTR_SUMMARY,
    ATTR_SUMMARY_MATCH_MODE,
    ATTR_UID,
    ATTR_UIDS,
    CONF_REGISTER_CALENDAR_SERVICES,
    DEFAULT_REGISTER_CALENDAR_SERVICES,
    DOMAIN,
    MATCH_MODE_CONTAINS,
    MATCH_MODE_ENDSWITH,
    MATCH_MODE_EXACT,
    MATCH_MODE_EXACT_CASE_SENSITIVE,
    MATCH_MODE_REGEX,
    MATCH_MODE_STARTSWITH,
    SERVICE_CLEAR_CALENDAR,
    SERVICE_DELETE_EVENT,
    SERVICE_DELETE_EVENTS,
    VALID_MATCH_MODES,
)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)

# Schema for deleting a single calendar event
DELETE_EVENT_SCHEMA = vol.All(
    cv.has_at_least_one_key(ATTR_UID, ATTR_SUMMARY),
    cv.make_entity_service_schema(
        {
            vol.Optional(ATTR_UID): cv.string,
            vol.Optional(ATTR_SUMMARY): cv.string,
            vol.Optional(ATTR_SUMMARY_MATCH_MODE, default=MATCH_MODE_EXACT): vol.In(
                VALID_MATCH_MODES
            ),
            vol.Optional(ATTR_RECURRENCE_ID): vol.Any(cv.string, None),
            vol.Optional(ATTR_RECURRENCE_RANGE): vol.Any(
                vol.In(["THIS_AND_FUTURE", "NONE", None]), None
            ),
            vol.Optional(ATTR_START_DATETIME): cv.datetime,
            vol.Optional(ATTR_END_DATETIME): cv.datetime,
            vol.Optional(ATTR_START_DATE): cv.date,
            vol.Optional(ATTR_END_DATE): cv.date,
        }
    ),
)

# Schema for deleting multiple calendar events
DELETE_EVENTS_SCHEMA = cv.make_entity_service_schema(
    {
        vol.Optional(ATTR_UIDS): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(ATTR_SUMMARY): cv.string,
        vol.Optional(ATTR_SUMMARY_MATCH_MODE, default=MATCH_MODE_EXACT): vol.In(
            VALID_MATCH_MODES
        ),
        vol.Optional(ATTR_DESCRIPTION): cv.string,
        vol.Optional(ATTR_LOCATION): cv.string,
        vol.Optional(ATTR_START_DATETIME): cv.datetime,
        vol.Optional(ATTR_END_DATETIME): cv.datetime,
        vol.Optional(ATTR_START_DATE): cv.date,
        vol.Optional(ATTR_END_DATE): cv.date,
        vol.Optional(ATTR_ALL_TIME, default=False): cv.boolean,
        vol.Optional(ATTR_LIMIT): cv.positive_int,
        vol.Optional(ATTR_DELETE_ALL, default=False): cv.boolean,
        vol.Optional(ATTR_DRY_RUN, default=False): cv.boolean,
    }
)

# Schema for clearing a calendar (bulk removal of all/past/future events)
CLEAR_CALENDAR_SCHEMA = cv.make_entity_service_schema(
    {
        vol.Required(ATTR_CONFIRM): cv.boolean,
        vol.Optional(ATTR_START_DATETIME): cv.datetime,
        vol.Optional(ATTR_END_DATETIME): cv.datetime,
        vol.Optional(ATTR_START_DATE): cv.date,
        vol.Optional(ATTR_END_DATE): cv.date,
        vol.Optional(ATTR_ONLY_PAST, default=False): cv.boolean,
        vol.Optional(ATTR_ONLY_FUTURE, default=False): cv.boolean,
        vol.Optional(ATTR_DRY_RUN, default=False): cv.boolean,
    }
)


def _matches_summary(
    event_summary: str | None, pattern: str, match_mode: str
) -> bool:
    """Check if event summary matches pattern according to mode."""
    if event_summary is None:
        return False

    summary_clean = event_summary.strip()
    pattern_clean = pattern.strip()

    if match_mode == MATCH_MODE_EXACT:
        return summary_clean.lower() == pattern_clean.lower()
    if match_mode == MATCH_MODE_EXACT_CASE_SENSITIVE:
        return summary_clean == pattern_clean
    if match_mode == MATCH_MODE_CONTAINS:
        return pattern_clean.lower() in summary_clean.lower()
    if match_mode == MATCH_MODE_STARTSWITH:
        return summary_clean.lower().startswith(pattern_clean.lower())
    if match_mode == MATCH_MODE_ENDSWITH:
        return summary_clean.lower().endswith(pattern_clean.lower())
    if match_mode == MATCH_MODE_REGEX:
        try:
            return bool(re.search(pattern, summary_clean, re.IGNORECASE))
        except re.error as err:
            raise HomeAssistantError(
                f"Invalid regular expression '{pattern}': {err}"
            ) from err

    return summary_clean.lower() == pattern_clean.lower()


def _parse_time_boundary(
    data: dict[str, Any],
    datetime_key: str,
    date_key: str,
    is_end: bool,
    default: datetime.datetime,
) -> datetime.datetime:
    """Parse a datetime or date parameter into a timezone-aware datetime."""
    val = data.get(datetime_key)
    if val is not None:
        if isinstance(val, str):
            parsed = dt_util.parse_datetime(val)
            if parsed is None:
                raise HomeAssistantError(
                    f"Invalid datetime format for {datetime_key}: {val}"
                )
            val = parsed
        if isinstance(val, datetime.datetime):
            if val.tzinfo is None:
                return dt_util.as_local(val)
            return val

    date_val = data.get(date_key)
    if date_val is not None:
        if isinstance(date_val, str):
            parsed_date = dt_util.parse_date(date_val)
            if parsed_date is None:
                raise HomeAssistantError(
                    f"Invalid date format for {date_key}: {date_val}"
                )
            date_val = parsed_date
        if isinstance(date_val, datetime.date):
            time_part = datetime.time.max if is_end else datetime.time.min
            dt = datetime.datetime.combine(date_val, time_part)
            return dt_util.as_local(dt)

    return default


def _event_to_dict(event: Any, entity_id: str) -> dict[str, Any]:
    """Convert a CalendarEvent to a serializable dict for service response."""
    start_val = getattr(event, "start", None)
    end_val = getattr(event, "end", None)

    start_str = (
        start_val.isoformat()
        if hasattr(start_val, "isoformat")
        else str(start_val)
    )
    end_str = (
        end_val.isoformat()
        if hasattr(end_val, "isoformat")
        else str(end_val)
    )

    return {
        "entity_id": entity_id,
        "uid": getattr(event, "uid", None),
        "summary": getattr(event, "summary", ""),
        "description": getattr(event, "description", None),
        "location": getattr(event, "location", None),
        "start": start_str,
        "end": end_str,
        "recurrence_id": getattr(event, "recurrence_id", None),
        "all_day": getattr(event, "all_day", False),
    }


async def _async_get_calendar_entities(
    hass: HomeAssistant,
    call: ServiceCall,
) -> list[Any]:
    """Extract and validate CalendarEntity instances targeted by the service call."""
    component = hass.data.get(DATA_COMPONENT)
    if component is None:
        component = hass.data.get("calendar")

    if component is None:
        raise HomeAssistantError("Calendar integration is not loaded in Home Assistant")

    entity_ids: set[str] = set()

    # 1. Direct entity_id parameter (string or list)
    if ATTR_ENTITY_ID in call.data:
        val = call.data[ATTR_ENTITY_ID]
        if isinstance(val, str):
            entity_ids.add(val)
        elif isinstance(val, (list, tuple, set)):
            entity_ids.update(val)

    # 2. Extract from target (areas, devices, entities, groups)
    try:
        from homeassistant.helpers import service as ha_service

        try:
            extracted = await ha_service.async_extract_entity_ids(call)
        except TypeError:
            extracted = await ha_service.async_extract_entity_ids(hass, call)
        entity_ids.update(extracted)
    except Exception as err:
        _LOGGER.debug("Target extraction fallback: %s", err)

    # Filter to only calendar entities
    entity_ids = {eid for eid in entity_ids if eid.startswith("calendar.")}

    if not entity_ids:
        raise HomeAssistantError(
            "No calendar entity targeted. Please provide a target calendar entity (e.g. entity_id: calendar.my_calendar)."
        )

    entities: list[Any] = []
    for entity_id in entity_ids:
        entity = component.get_entity(entity_id)
        if entity is None:
            raise HomeAssistantError(f"Calendar entity '{entity_id}' not found")
        if not getattr(entity, "supported_features", 0) & DELETE_EVENT_FEATURE:
            raise HomeAssistantError(
                f"Calendar '{entity_id}' does not support deleting events (DELETE_EVENT feature is not supported by this integration)"
            )
        entities.append(entity)

    return entities


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Calendar Helper component from configuration.yaml."""
    hass.data.setdefault(DOMAIN, {})

    # Register services
    _async_register_services(hass, register_calendar_alias=DEFAULT_REGISTER_CALENDAR_SERVICES)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Calendar Helper from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    register_alias = entry.options.get(
        CONF_REGISTER_CALENDAR_SERVICES,
        entry.data.get(
            CONF_REGISTER_CALENDAR_SERVICES, DEFAULT_REGISTER_CALENDAR_SERVICES
        ),
    )

    _async_register_services(hass, register_calendar_alias=register_alias)

    entry.async_on_unload(entry.add_update_listener(async_update_listener))
    return True


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    register_alias = entry.options.get(
        CONF_REGISTER_CALENDAR_SERVICES,
        entry.data.get(
            CONF_REGISTER_CALENDAR_SERVICES, DEFAULT_REGISTER_CALENDAR_SERVICES
        ),
    )
    _async_register_services(hass, register_calendar_alias=register_alias)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Calendar Helper config entry."""
    _async_unregister_services(hass)
    return True


def _async_register_services(
    hass: HomeAssistant, register_calendar_alias: bool = True
) -> None:
    """Register all Calendar Helper services."""

    async def async_handle_delete_event(call: ServiceCall) -> ServiceResponse:
        """Handle deleting a single calendar event."""
        entities = await _async_get_calendar_entities(hass, call)
        uid = call.data.get(ATTR_UID)
        summary = call.data.get(ATTR_SUMMARY)
        match_mode = call.data.get(ATTR_SUMMARY_MATCH_MODE, MATCH_MODE_EXACT)
        recurrence_id = call.data.get(ATTR_RECURRENCE_ID)
        recurrence_range = call.data.get(ATTR_RECURRENCE_RANGE)

        deleted_items: list[dict[str, Any]] = []

        now = dt_util.now()
        default_start = now - datetime.timedelta(days=30)
        default_end = now + datetime.timedelta(days=365)

        start_dt = _parse_time_boundary(
            call.data, ATTR_START_DATETIME, ATTR_START_DATE, False, default_start
        )
        end_dt = _parse_time_boundary(
            call.data, ATTR_END_DATETIME, ATTR_END_DATE, True, default_end
        )

        for entity in entities:
            entity_id = entity.entity_id

            if uid:
                # Direct deletion by UID
                await entity.async_delete_event(
                    uid,
                    recurrence_id=recurrence_id,
                    recurrence_range=recurrence_range,
                )
                deleted_items.append(
                    {
                        "entity_id": entity_id,
                        "uid": uid,
                        "summary": summary,
                        "recurrence_id": recurrence_id,
                        "deleted": True,
                    }
                )
            elif summary:
                # Find matching event by summary
                events = await entity.async_get_events(hass, start_dt, end_dt)
                matched = [
                    ev
                    for ev in events
                    if _matches_summary(getattr(ev, "summary", None), summary, match_mode)
                ]

                if not matched:
                    raise HomeAssistantError(
                        f"No event matching summary '{summary}' found on calendar '{entity_id}' "
                        f"between {start_dt.isoformat()} and {end_dt.isoformat()}"
                    )

                target_event = matched[0]
                event_uid = getattr(target_event, "uid", None)
                if not event_uid:
                    raise HomeAssistantError(
                        f"Matched event '{getattr(target_event, 'summary', '')}' on '{entity_id}' has no UID"
                    )

                target_rec_id = recurrence_id or getattr(target_event, "recurrence_id", None)
                await entity.async_delete_event(
                    event_uid,
                    recurrence_id=target_rec_id,
                    recurrence_range=recurrence_range,
                )
                deleted_items.append(_event_to_dict(target_event, entity_id))

        return {
            "success": True,
            "deleted_count": len(deleted_items),
            "events": deleted_items,
        }

    async def async_handle_delete_events(call: ServiceCall) -> ServiceResponse:
        """Handle deleting multiple calendar events based on criteria."""
        entities = await _async_get_calendar_entities(hass, call)
        uids = call.data.get(ATTR_UIDS)
        summary = call.data.get(ATTR_SUMMARY)
        match_mode = call.data.get(ATTR_SUMMARY_MATCH_MODE, MATCH_MODE_EXACT)
        description = call.data.get(ATTR_DESCRIPTION)
        location = call.data.get(ATTR_LOCATION)
        limit = call.data.get(ATTR_LIMIT)
        delete_all = call.data.get(ATTR_DELETE_ALL, False)
        all_time = call.data.get(ATTR_ALL_TIME, False)
        dry_run = call.data.get(ATTR_DRY_RUN, False)

        has_filter = bool(uids or summary or description or location)
        if not has_filter and not delete_all:
            raise HomeAssistantError(
                "No filters (summary, description, location, uids) provided. "
                "To delete all events without filters, set 'delete_all: true'."
            )

        now = dt_util.now()
        if all_time:
            default_start = dt_util.as_local(datetime.datetime(1970, 1, 1, 0, 0, 0))
            default_end = dt_util.as_local(datetime.datetime(2099, 12, 31, 23, 59, 59))
        else:
            default_start = now - datetime.timedelta(days=30)
            default_end = now + datetime.timedelta(days=365)

        start_dt = _parse_time_boundary(
            call.data, ATTR_START_DATETIME, ATTR_START_DATE, False, default_start
        )
        end_dt = _parse_time_boundary(
            call.data, ATTR_END_DATETIME, ATTR_END_DATE, True, default_end
        )

        all_deleted_events: list[dict[str, Any]] = []

        for entity in entities:
            entity_id = entity.entity_id

            # If only UIDs are provided without search window and not all_time, delete directly
            if uids and not (summary or description or location or ATTR_START_DATETIME in call.data or ATTR_START_DATE in call.data):
                for uid in uids:
                    if dry_run:
                        all_deleted_events.append(
                            {"entity_id": entity_id, "uid": uid, "dry_run": True}
                        )
                    else:
                        try:
                            await entity.async_delete_event(uid)
                            all_deleted_events.append(
                                {"entity_id": entity_id, "uid": uid, "deleted": True}
                            )
                        except Exception as err:
                            _LOGGER.warning(
                                "Failed to delete event UID '%s' on %s: %s",
                                uid,
                                entity_id,
                                err,
                            )
                continue

            events = await entity.async_get_events(hass, start_dt, end_dt)

            matched_events: list[Any] = []
            for event in events:
                ev_uid = getattr(event, "uid", None)
                ev_summary = getattr(event, "summary", "")
                ev_desc = getattr(event, "description", None)
                ev_loc = getattr(event, "location", None)

                if uids and ev_uid not in uids:
                    continue
                if summary and not _matches_summary(ev_summary, summary, match_mode):
                    continue
                if description and (not ev_desc or description.lower() not in ev_desc.lower()):
                    continue
                if location and (not ev_loc or location.lower() not in ev_loc.lower()):
                    continue

                matched_events.append(event)

            if limit is not None:
                matched_events = matched_events[:limit]

            processed_keys: set[tuple[str | None, str | None]] = set()

            for event in matched_events:
                ev_uid = getattr(event, "uid", None)
                ev_rec_id = getattr(event, "recurrence_id", None)
                if not ev_uid:
                    continue

                dedup_key = (ev_uid, ev_rec_id)
                if dedup_key in processed_keys:
                    continue
                processed_keys.add(dedup_key)

                event_dict = _event_to_dict(event, entity_id)

                if dry_run:
                    event_dict["dry_run"] = True
                    all_deleted_events.append(event_dict)
                else:
                    try:
                        await entity.async_delete_event(
                            ev_uid,
                            recurrence_id=ev_rec_id,
                        )
                        event_dict["deleted"] = True
                        all_deleted_events.append(event_dict)
                    except Exception as err:
                        _LOGGER.warning(
                            "Failed to delete event '%s' (uid=%s) on %s: %s",
                            getattr(event, "summary", ""),
                            ev_uid,
                            entity_id,
                            err,
                        )

        return {
            "success": True,
            "dry_run": dry_run,
            "deleted_count": len(all_deleted_events),
            "events": all_deleted_events,
        }

    async def async_handle_clear_calendar(call: ServiceCall) -> ServiceResponse:
        """Handle clearing all events or events in a time span from calendar."""
        confirm = call.data.get(ATTR_CONFIRM, False)
        if not confirm:
            raise HomeAssistantError(
                "Action aborted: 'confirm: true' is required to clear calendar events."
            )

        entities = await _async_get_calendar_entities(hass, call)
        only_past = call.data.get(ATTR_ONLY_PAST, False)
        only_future = call.data.get(ATTR_ONLY_FUTURE, False)
        dry_run = call.data.get(ATTR_DRY_RUN, False)

        now = dt_util.now()
        default_start = dt_util.as_local(datetime.datetime(1970, 1, 1, 0, 0, 0))
        default_end = dt_util.as_local(datetime.datetime(2099, 12, 31, 23, 59, 59))

        if only_past:
            default_end = now
        elif only_future:
            default_start = now

        start_dt = _parse_time_boundary(
            call.data, ATTR_START_DATETIME, ATTR_START_DATE, False, default_start
        )
        end_dt = _parse_time_boundary(
            call.data, ATTR_END_DATETIME, ATTR_END_DATE, True, default_end
        )

        all_cleared_events: list[dict[str, Any]] = []

        for entity in entities:
            entity_id = entity.entity_id
            events = await entity.async_get_events(hass, start_dt, end_dt)

            processed_keys: set[tuple[str | None, str | None]] = set()

            for event in events:
                ev_uid = getattr(event, "uid", None)
                ev_rec_id = getattr(event, "recurrence_id", None)
                if not ev_uid:
                    continue

                dedup_key = (ev_uid, ev_rec_id)
                if dedup_key in processed_keys:
                    continue
                processed_keys.add(dedup_key)

                event_dict = _event_to_dict(event, entity_id)

                if dry_run:
                    event_dict["dry_run"] = True
                    all_cleared_events.append(event_dict)
                else:
                    try:
                        await entity.async_delete_event(
                            ev_uid,
                            recurrence_id=ev_rec_id,
                        )
                        event_dict["deleted"] = True
                        all_cleared_events.append(event_dict)
                    except Exception as err:
                        _LOGGER.warning(
                            "Failed to clear event '%s' (uid=%s) on %s: %s",
                            getattr(event, "summary", ""),
                            ev_uid,
                            entity_id,
                            err,
                        )

        return {
            "success": True,
            "dry_run": dry_run,
            "deleted_count": len(all_cleared_events),
            "events": all_cleared_events,
        }

    # Register services under calendar_helper domain
    services_to_register = [
        (SERVICE_DELETE_EVENT, async_handle_delete_event, DELETE_EVENT_SCHEMA),
        (SERVICE_DELETE_EVENTS, async_handle_delete_events, DELETE_EVENTS_SCHEMA),
        (SERVICE_CLEAR_CALENDAR, async_handle_clear_calendar, CLEAR_CALENDAR_SCHEMA),
    ]

    for service_name, handler, schema in services_to_register:
        hass.services.async_register(
            DOMAIN,
            service_name,
            handler,
            schema=schema,
            supports_response=SupportsResponse.OPTIONAL,
        )

        # Optionally register as alias under calendar domain if not present
        if register_calendar_alias and not hass.services.has_service("calendar", service_name):
            try:
                hass.services.async_register(
                    "calendar",
                    service_name,
                    handler,
                    schema=schema,
                    supports_response=SupportsResponse.OPTIONAL,
                )
                hass.data[DOMAIN].setdefault("calendar_aliases", set()).add(service_name)
                _LOGGER.debug("Registered alias service 'calendar.%s'", service_name)
            except Exception as err:
                _LOGGER.debug(
                    "Could not register alias 'calendar.%s': %s", service_name, err
                )


def _async_unregister_services(hass: HomeAssistant) -> None:
    """Unregister all Calendar Helper services."""
    services = [
        SERVICE_DELETE_EVENT,
        SERVICE_DELETE_EVENTS,
        SERVICE_CLEAR_CALENDAR,
    ]
    for service_name in services:
        if hass.services.has_service(DOMAIN, service_name):
            hass.services.async_remove(DOMAIN, service_name)

    # Remove registered aliases on calendar domain
    if DOMAIN in hass.data and "calendar_aliases" in hass.data[DOMAIN]:
        for alias_service in hass.data[DOMAIN]["calendar_aliases"]:
            if hass.services.has_service("calendar", alias_service):
                hass.services.async_remove("calendar", alias_service)
        hass.data[DOMAIN]["calendar_aliases"].clear()
