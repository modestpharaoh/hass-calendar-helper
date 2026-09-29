"""Unit tests for Calendar Helper integration."""
from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

# Create mock homeassistant modules before importing custom_components
import sys
import types

# Build minimal mock homeassistant structure if not already installed
if "homeassistant" not in sys.modules:
    ha = types.ModuleType("homeassistant")
    sys.modules["homeassistant"] = ha

    ha_const = types.ModuleType("homeassistant.const")
    ha_const.ATTR_ENTITY_ID = "entity_id"
    sys.modules["homeassistant.const"] = ha_const

    ha_core = types.ModuleType("homeassistant.core")
    class HomeAssistant:
        def __init__(self):
            self.data = {}
            self.services = MagicMock()
            self.services.has_service = MagicMock(return_value=False)
            self.services.async_register = MagicMock()
            self.services.async_remove = MagicMock()

    class ServiceCall:
        def __init__(self, domain, service, data=None):
            self.domain = domain
            self.service = service
            self.data = data or {}

    class SupportsResponse:
        OPTIONAL = "optional"
        ONLY = "only"
        NONE = "none"

    def callback(func):
        return func

    ha_core.HomeAssistant = HomeAssistant
    ha_core.ServiceCall = ServiceCall
    ha_core.ServiceResponse = dict
    ha_core.SupportsResponse = SupportsResponse
    ha_core.callback = callback
    sys.modules["homeassistant.core"] = ha_core

    ha_exc = types.ModuleType("homeassistant.exceptions")
    class HomeAssistantError(Exception):
        pass
    ha_exc.HomeAssistantError = HomeAssistantError
    sys.modules["homeassistant.exceptions"] = ha_exc

    ha_dt = types.ModuleType("homeassistant.util.dt")
    def as_local(dt):
        if dt.tzinfo is None:
            return dt.replace(tzinfo=datetime.timezone.utc)
        return dt
    def now():
        return datetime.datetime(2026, 9, 29, 12, 0, 0, tzinfo=datetime.timezone.utc)
    def parse_datetime(val):
        try:
            return datetime.datetime.fromisoformat(val)
        except Exception:
            return None
    def parse_date(val):
        try:
            return datetime.date.fromisoformat(val)
        except Exception:
            return None

    ha_dt.as_local = as_local
    ha_dt.now = now
    ha_dt.parse_datetime = parse_datetime
    ha_dt.parse_date = parse_date
    sys.modules["homeassistant.util"] = types.ModuleType("homeassistant.util")
    sys.modules["homeassistant.util.dt"] = ha_dt

    ha_cv = types.ModuleType("homeassistant.helpers.config_validation")
    ha_cv.string = str
    ha_cv.boolean = bool
    ha_cv.datetime = lambda v: v
    ha_cv.date = lambda v: v
    ha_cv.positive_int = int
    ha_cv.ensure_list = lambda v: v if isinstance(v, list) else [v]
    def has_at_least_one_key(*keys):
        def validate(obj):
            if not any(k in obj for k in keys):
                raise ha_exc.HomeAssistantError(f"Must have at least one of {keys}")
            return obj
        return validate
    def make_entity_service_schema(schema):
        import voluptuous as vol
        full = {**schema, vol.Optional("entity_id"): vol.Any(str, list)}
        return vol.Schema(full)
    ha_cv.has_at_least_one_key = has_at_least_one_key
    ha_cv.make_entity_service_schema = make_entity_service_schema
    sys.modules["homeassistant.helpers"] = types.ModuleType("homeassistant.helpers")
    sys.modules["homeassistant.helpers.config_validation"] = ha_cv
    sys.modules["homeassistant.helpers.typing"] = types.ModuleType("homeassistant.helpers.typing")
    sys.modules["homeassistant.helpers.typing"].ConfigType = dict

    ha_cfg = types.ModuleType("homeassistant.config_entries")
    class ConfigEntry:
        def __init__(self, entry_id="test", data=None, options=None):
            self.entry_id = entry_id
            self.data = data or {}
            self.options = options or {}
            self._update_listeners = []
        def add_update_listener(self, listener):
            self._update_listeners.append(listener)
            return listener
        def async_on_unload(self, func):
            pass
    class ConfigFlow:
        def __init_subclass__(cls, domain=None, **kwargs):
            super().__init_subclass__(**kwargs)
            cls.domain = domain
        def _async_current_entries(self):
            return []
        def async_show_form(self, step_id, data_schema, errors=None):
            return {"type": "form", "step_id": step_id, "data_schema": data_schema}
        def async_create_entry(self, title, data):
            return {"type": "create_entry", "title": title, "data": data}
        def async_abort(self, reason):
            return {"type": "abort", "reason": reason}
    class OptionsFlow:
        def __init__(self, config_entry):
            self._config_entry = config_entry
        def async_show_form(self, step_id, data_schema, errors=None):
            return {"type": "form", "step_id": step_id, "data_schema": data_schema}
        def async_create_entry(self, title, data):
            return {"type": "create_entry", "title": title, "data": data}

    ha_cfg.ConfigEntry = ConfigEntry
    ha_cfg.ConfigFlow = ConfigFlow
    ha_cfg.OptionsFlow = OptionsFlow
    ha_cfg.ConfigFlowResult = dict
    sys.modules["homeassistant.config_entries"] = ha_cfg

    ha_cal = types.ModuleType("homeassistant.components.calendar")
    class CalendarEvent:
        def __init__(self, summary, start, end, uid=None, description=None, location=None, recurrence_id=None):
            self.summary = summary
            self.start = start
            self.end = end
            self.uid = uid
            self.description = description
            self.location = location
            self.recurrence_id = recurrence_id
            self.all_day = not isinstance(start, datetime.datetime)
    class CalendarEntity:
        pass
    ha_cal.CalendarEvent = CalendarEvent
    ha_cal.CalendarEntity = CalendarEntity
    sys.modules["homeassistant.components"] = types.ModuleType("homeassistant.components")
    sys.modules["homeassistant.components.calendar"] = ha_cal

    ha_cal_const = types.ModuleType("homeassistant.components.calendar.const")
    ha_cal_const.DATA_COMPONENT = "calendar"
    class CalendarEntityFeature:
        DELETE_EVENT = 2
    ha_cal_const.CalendarEntityFeature = CalendarEntityFeature
    sys.modules["homeassistant.components.calendar.const"] = ha_cal_const


from custom_components.calendar_helper import (
    _matches_summary,
    _parse_time_boundary,
    _event_to_dict,
    _async_register_services,
    _async_unregister_services,
    async_setup,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.calendar_helper.const import (
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
)
from custom_components.calendar_helper.config_flow import CalendarHelperConfigFlow
from homeassistant.exceptions import HomeAssistantError


class MockCalendarEntity:
    def __init__(self, entity_id="calendar.test", supported_features=2):
        self.entity_id = entity_id
        self.supported_features = supported_features
        self.events = []
        self.async_delete_event = AsyncMock()
        self.async_get_events = AsyncMock(side_effect=self._mock_get_events)

    async def _mock_get_events(self, hass, start_dt, end_dt):
        return [
            ev for ev in self.events
            if ev.end >= start_dt and ev.start <= end_dt
        ]


class MockCalendarComponent:
    def __init__(self):
        self.entities = {}

    def get_entity(self, entity_id):
        return self.entities.get(entity_id)


def test_matches_summary_modes():
    """Test all match modes for _matches_summary."""
    # Exact (case-insensitive)
    assert _matches_summary("Doctor Visit", "doctor visit", MATCH_MODE_EXACT) is True
    assert _matches_summary(" Doctor Visit ", "doctor visit", MATCH_MODE_EXACT) is True
    assert _matches_summary("Doctor", "doctor visit", MATCH_MODE_EXACT) is False

    # Exact case sensitive
    assert _matches_summary("Doctor", "Doctor", MATCH_MODE_EXACT_CASE_SENSITIVE) is True
    assert _matches_summary("Doctor", "doctor", MATCH_MODE_EXACT_CASE_SENSITIVE) is False

    # Contains
    assert _matches_summary("Recycling bin day", "recycling", MATCH_MODE_CONTAINS) is True
    assert _matches_summary("Recycling bin day", "trash", MATCH_MODE_CONTAINS) is False

    # Starts with
    assert _matches_summary("Dentist checkup", "dentist", MATCH_MODE_STARTSWITH) is True
    assert _matches_summary("Dentist checkup", "checkup", MATCH_MODE_STARTSWITH) is False

    # Ends with
    assert _matches_summary("Gym Workout", "workout", MATCH_MODE_ENDSWITH) is True
    assert _matches_summary("Gym Workout", "gym", MATCH_MODE_ENDSWITH) is False

    # Regex
    assert _matches_summary("Meeting #123 with team", r"Meeting #\d+", MATCH_MODE_REGEX) is True
    assert _matches_summary("Meeting ABC with team", r"Meeting #\d+", MATCH_MODE_REGEX) is False

    # None summary
    assert _matches_summary(None, "test", MATCH_MODE_EXACT) is False

    # Invalid regex raises HomeAssistantError
    with pytest.raises(HomeAssistantError):
        _matches_summary("test", "[invalid regex", MATCH_MODE_REGEX)


def test_parse_time_boundary():
    """Test datetime and date boundary parsing."""
    default = datetime.datetime(2026, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)

    # Empty data falls back to default
    assert _parse_time_boundary({}, "start_dt", "start_d", False, default) == default

    # Datetime string
    res = _parse_time_boundary({"start_dt": "2026-10-15T14:30:00"}, "start_dt", "start_d", False, default)
    assert res.year == 2026 and res.month == 10 and res.day == 15 and res.hour == 14 and res.minute == 30

    # Date string - start of day (is_end=False)
    res_start = _parse_time_boundary({"start_d": "2026-10-15"}, "start_dt", "start_d", False, default)
    assert res_start.day == 15 and res_start.hour == 0 and res_start.minute == 0

    # Date string - end of day (is_end=True)
    res_end = _parse_time_boundary({"end_d": "2026-10-15"}, "end_dt", "end_d", True, default)
    assert res_end.day == 15 and res_end.hour == 23 and res_end.minute == 59

    # Invalid string raises HomeAssistantError
    with pytest.raises(HomeAssistantError):
        _parse_time_boundary({"start_dt": "not-a-datetime"}, "start_dt", "start_d", False, default)


def test_event_to_dict():
    """Test serialization of calendar event."""
    from homeassistant.components.calendar import CalendarEvent
    start = datetime.datetime(2026, 10, 15, 10, 0, 0, tzinfo=datetime.timezone.utc)
    end = datetime.datetime(2026, 10, 15, 11, 0, 0, tzinfo=datetime.timezone.utc)
    ev = CalendarEvent(
        summary="Test Meeting",
        start=start,
        end=end,
        uid="uid-12345",
        description="Meeting notes",
        location="Room A",
        recurrence_id="rec-01",
    )

    d = _event_to_dict(ev, "calendar.work")
    assert d["entity_id"] == "calendar.work"
    assert d["uid"] == "uid-12345"
    assert d["summary"] == "Test Meeting"
    assert d["description"] == "Meeting notes"
    assert d["location"] == "Room A"
    assert d["start"] == start.isoformat()
    assert d["end"] == end.isoformat()
    assert d["recurrence_id"] == "rec-01"


@pytest.mark.asyncio
async def test_service_delete_event_by_uid():
    """Test deleting an event directly by UID."""
    from homeassistant.core import HomeAssistant, ServiceCall
    hass = HomeAssistant()
    comp = MockCalendarComponent()
    cal = MockCalendarEntity("calendar.test")
    comp.entities["calendar.test"] = cal
    hass.data["calendar"] = comp

    registered_handlers = {}
    hass.services.async_register = lambda domain, svc, handler, **kw: registered_handlers.update({(domain, svc): handler})

    _async_register_services(hass)
    delete_event_handler = registered_handlers[(DOMAIN, SERVICE_DELETE_EVENT)]

    call = ServiceCall(
        DOMAIN,
        SERVICE_DELETE_EVENT,
        {"entity_id": "calendar.test", "uid": "abc-123", "recurrence_id": "r-1"},
    )
    result = await delete_event_handler(call)

    assert result["success"] is True
    assert result["deleted_count"] == 1
    assert result["events"][0]["uid"] == "abc-123"
    cal.async_delete_event.assert_called_once_with("abc-123", recurrence_id="r-1", recurrence_range=None)


@pytest.mark.asyncio
async def test_service_delete_event_by_summary():
    """Test searching and deleting an event by summary."""
    from homeassistant.core import HomeAssistant, ServiceCall
    from homeassistant.components.calendar import CalendarEvent
    hass = HomeAssistant()
    comp = MockCalendarComponent()
    cal = MockCalendarEntity("calendar.test")

    start = datetime.datetime(2026, 10, 1, 10, 0, 0, tzinfo=datetime.timezone.utc)
    end = datetime.datetime(2026, 10, 1, 11, 0, 0, tzinfo=datetime.timezone.utc)
    event1 = CalendarEvent("Doctor Appointment", start, end, uid="doc-uid-1")
    cal.events = [event1]

    comp.entities["calendar.test"] = cal
    hass.data["calendar"] = comp

    registered_handlers = {}
    hass.services.async_register = lambda domain, svc, handler, **kw: registered_handlers.update({(domain, svc): handler})

    _async_register_services(hass)
    delete_event_handler = registered_handlers[(DOMAIN, SERVICE_DELETE_EVENT)]

    call = ServiceCall(
        DOMAIN,
        SERVICE_DELETE_EVENT,
        {"entity_id": "calendar.test", "summary": "Doctor", "summary_match_mode": "contains"},
    )
    result = await delete_event_handler(call)

    assert result["success"] is True
    assert result["deleted_count"] == 1
    assert result["events"][0]["uid"] == "doc-uid-1"
    cal.async_delete_event.assert_called_once_with("doc-uid-1", recurrence_id=None, recurrence_range=None)


@pytest.mark.asyncio
async def test_service_delete_events_bulk_and_dry_run():
    """Test bulk deletion of events and dry_run preview."""
    from homeassistant.core import HomeAssistant, ServiceCall
    from homeassistant.components.calendar import CalendarEvent
    hass = HomeAssistant()
    comp = MockCalendarComponent()
    cal = MockCalendarEntity("calendar.test")

    now = datetime.datetime(2026, 9, 29, 12, 0, 0, tzinfo=datetime.timezone.utc)
    ev1 = CalendarEvent("Recycling Pickup", now, now + datetime.timedelta(hours=1), uid="rec-1")
    ev2 = CalendarEvent("Trash Pickup", now + datetime.timedelta(days=1), now + datetime.timedelta(days=1, hours=1), uid="trash-1")
    ev3 = CalendarEvent("Doctor", now + datetime.timedelta(days=2), now + datetime.timedelta(days=2, hours=1), uid="doc-1")
    cal.events = [ev1, ev2, ev3]

    comp.entities["calendar.test"] = cal
    hass.data["calendar"] = comp

    registered_handlers = {}
    hass.services.async_register = lambda domain, svc, handler, **kw: registered_handlers.update({(domain, svc): handler})

    _async_register_services(hass)
    delete_events_handler = registered_handlers[(DOMAIN, SERVICE_DELETE_EVENTS)]

    # 1. Test dry_run: Preview deleting "Pickup"
    call_dry = ServiceCall(
        DOMAIN,
        SERVICE_DELETE_EVENTS,
        {"entity_id": "calendar.test", "summary": "Pickup", "summary_match_mode": "contains", "dry_run": True},
    )
    result_dry = await delete_events_handler(call_dry)
    assert result_dry["dry_run"] is True
    assert result_dry["deleted_count"] == 2
    cal.async_delete_event.assert_not_called()

    # 2. Test actual deletion
    call_real = ServiceCall(
        DOMAIN,
        SERVICE_DELETE_EVENTS,
        {"entity_id": "calendar.test", "summary": "Pickup", "summary_match_mode": "contains", "dry_run": False},
    )
    result_real = await delete_events_handler(call_real)
    assert result_real["dry_run"] is False
    assert result_real["deleted_count"] == 2
    assert cal.async_delete_event.call_count == 2


@pytest.mark.asyncio
async def test_delete_events_safety_override():
    """Verify that deleting without filters requires delete_all: true."""
    from homeassistant.core import HomeAssistant, ServiceCall
    hass = HomeAssistant()
    comp = MockCalendarComponent()
    cal = MockCalendarEntity("calendar.test")
    comp.entities["calendar.test"] = cal
    hass.data["calendar"] = comp

    registered_handlers = {}
    hass.services.async_register = lambda domain, svc, handler, **kw: registered_handlers.update({(domain, svc): handler})

    _async_register_services(hass)
    delete_events_handler = registered_handlers[(DOMAIN, SERVICE_DELETE_EVENTS)]

    # Attempt delete with no filters and delete_all=False
    call = ServiceCall(DOMAIN, SERVICE_DELETE_EVENTS, {"entity_id": "calendar.test"})
    with pytest.raises(HomeAssistantError, match="delete_all: true"):
        await delete_events_handler(call)


@pytest.mark.asyncio
async def test_clear_calendar():
    """Test clear_calendar action with confirm check and past/future filters."""
    from homeassistant.core import HomeAssistant, ServiceCall
    from homeassistant.components.calendar import CalendarEvent
    hass = HomeAssistant()
    comp = MockCalendarComponent()
    cal = MockCalendarEntity("calendar.test")

    now = datetime.datetime(2026, 9, 29, 12, 0, 0, tzinfo=datetime.timezone.utc)
    past_ev = CalendarEvent("Past Event", now - datetime.timedelta(days=5), now - datetime.timedelta(days=5, hours=-1), uid="past-1")
    future_ev = CalendarEvent("Future Event", now + datetime.timedelta(days=5), now + datetime.timedelta(days=5, hours=1), uid="future-1")
    cal.events = [past_ev, future_ev]

    comp.entities["calendar.test"] = cal
    hass.data["calendar"] = comp

    registered_handlers = {}
    hass.services.async_register = lambda domain, svc, handler, **kw: registered_handlers.update({(domain, svc): handler})

    _async_register_services(hass)
    clear_handler = registered_handlers[(DOMAIN, SERVICE_CLEAR_CALENDAR)]

    # Confirm missing
    call_no_confirm = ServiceCall(DOMAIN, SERVICE_CLEAR_CALENDAR, {"entity_id": "calendar.test", "confirm": False})
    with pytest.raises(HomeAssistantError, match="confirm: true"):
        await clear_handler(call_no_confirm)

    # Clear only past events
    call_past = ServiceCall(
        DOMAIN,
        SERVICE_CLEAR_CALENDAR,
        {"entity_id": "calendar.test", "confirm": True, "only_past": True},
    )
    result = await clear_handler(call_past)
    assert result["deleted_count"] == 1
    assert result["events"][0]["uid"] == "past-1"
    cal.async_delete_event.assert_called_once_with("past-1", recurrence_id=None)


@pytest.mark.asyncio
async def test_config_flow():
    """Test config flow creation and options flow."""
    from homeassistant.config_entries import ConfigEntry
    flow = CalendarHelperConfigFlow()

    # Step user initial form
    result = await flow.async_step_user()
    assert result["type"] == "form"

    # Step user submit
    result_create = await flow.async_step_user({"register_calendar_services": True})
    assert result_create["type"] == "create_entry"
    assert result_create["data"]["register_calendar_services"] is True

    # Options flow
    entry = ConfigEntry("test_id", data={"register_calendar_services": True})
    options_flow = CalendarHelperConfigFlow.async_get_options_flow(entry)
    init_form = await options_flow.async_step_init()
    assert init_form["type"] == "form"

    init_save = await options_flow.async_step_init({"register_calendar_services": False})
    assert init_save["type"] == "create_entry"
    assert init_save["data"]["register_calendar_services"] is False
