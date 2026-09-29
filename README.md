# Calendar Helper for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://github.com/hacs/default)
[![GitHub Release](https://img.shields.io/github/v/release/modestpharaoh/hass-calendar-helper?style=for-the-badge)](https://github.com/modestpharaoh/hass-calendar-helper/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.1+-blue.svg?style=for-the-badge)](https://www.home-assistant.io/)

**Calendar Helper** is a Home Assistant custom integration (HACS compatible) that adds actions/services to **delete single or multiple calendar events** from Local Calendars (and any other calendar supporting event deletion) directly in automations, scripts, and Developer Tools.

---

## Why Calendar Helper?

Home Assistant provides native actions to create events (`calendar.create_event`) and fetch events (`calendar.get_events`), but **does not provide a built-in action to delete calendar events** in automations or scripts.

This integration bridges that gap by exposing clean, powerful actions:
- **`calendar_helper.delete_event`**: Delete a specific event by its `uid` or by searching for its `summary` (and optional time window).
- **`calendar_helper.delete_events`**: Bulk delete multiple events matching flexible search criteria (summary, description, location, or list of UIDs).
- **`calendar_helper.clear_calendar`**: Bulk clear all events, only past events, or only future events with confirmation protection.
- **Convenient Aliases**: Optionally registers `calendar.delete_event`, `calendar.delete_events`, and `calendar.clear_calendar` directly under the `calendar` domain so you can use standard service names!
- **`dry_run` Mode**: Test search criteria before deleting anything to see exactly what *would* be deleted.
- **Response Data**: Returns detailed lists of deleted events and counts using `response_variable`.

---

## Features

- 🎯 **Delete by UID or Title**: Delete an event by exact UID or automatically search by summary/title.
- 🔍 **Multiple Match Modes**: Search summaries using `exact` (case-insensitive), `exact_case_sensitive`, `contains`, `startswith`, `endswith`, or `regex`.
- 📅 **Date & Time Boundaries**: Specify start and end timestamps or dates (`start_date_time`, `end_date_time`, `start_date`, `end_date`), or use `all_time: true`.
- 🛡️ **Safety Guardrails**: Bulk actions require search filters, a safety override (`delete_all: true`), or confirmation (`confirm: true`) to prevent accidental calendar wipes.
- 🔁 **Recurring Event Support**: Supports RFC5545 `recurrence_id` and `recurrence_range` (`THIS_AND_FUTURE`).
- 📊 **Action Responses**: Fully supports Home Assistant `response_variable` output.

---

## Installation

### Method 1: HACS (Recommended)

1. Ensure [HACS](https://hacs.xyz/) is installed in your Home Assistant instance.
2. In Home Assistant, navigate to **HACS** > **Integrations**.
3. Click the three dots icon in the top right corner and select **Custom repositories**.
4. In the Repository field, enter:
   ```text
   https://github.com/modestpharaoh/hass-calendar-helper
   ```
5. Select category: **Integration**.
6. Click **Add**, locate **Calendar Helper**, and click **Download**.
7. Restart Home Assistant.

### Method 2: Manual Installation

1. Download the latest release from the [Releases](https://github.com/modestpharaoh/hass-calendar-helper/releases) page.
2. Copy the `custom_components/calendar_helper` directory into your Home Assistant `<config_dir>/custom_components/` directory.
3. Restart Home Assistant.

---

## Configuration

### Via User Interface (UI)
1. Go to **Settings** > **Devices & Services** > **Add Integration**.
2. Search for **Calendar Helper** and click to install.
3. (Optional) Check the box to enable registering aliases under `calendar.*` (e.g. `calendar.delete_event`).

### Via YAML (`configuration.yaml`)
Alternatively, add the following to your `configuration.yaml`:

```yaml
calendar_helper:
```

---

## Available Actions

### 1. `calendar_helper.delete_event`

Deletes a single event from the specified calendar.

#### Parameters:
| Parameter | Type | Required | Description |
|---|---|---|---|
| `target.entity_id` | entity | **Yes** | The calendar entity (e.g. `calendar.local_calendar`). |
| `uid` | string | *Conditional* | The unique ID of the event to delete. (Required if `summary` is not provided). |
| `summary` | string | *Conditional* | Summary/title of the event to search for and delete. |
| `summary_match_mode` | string | No | Mode: `exact` (default), `exact_case_sensitive`, `contains`, `startswith`, `endswith`, `regex`. |
| `recurrence_id` | string | No | Recurrence ID for targeting an instance of a recurring event. |
| `recurrence_range` | string | No | `THIS_AND_FUTURE` or `NONE`. |
| `start_date_time` | datetime | No | Start of search range (default: 30 days ago). |
| `end_date_time` | datetime | No | End of search range (default: 365 days ahead). |
| `start_date` | date | No | Search range start date (for all-day events). |
| `end_date` | date | No | Search range end date (for all-day events). |

#### Examples:

**Delete by UID:**
```yaml
action: calendar_helper.delete_event
target:
  entity_id: calendar.my_calendar
data:
  uid: "1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d"
```

**Delete by Summary / Title:**
```yaml
action: calendar_helper.delete_event
target:
  entity_id: calendar.my_calendar
data:
  summary: "Dentist Appointment"
  summary_match_mode: "contains"
```

---

### 2. `calendar_helper.delete_events`

Deletes multiple events matching filter criteria.

#### Parameters:
| Parameter | Type | Required | Description |
|---|---|---|---|
| `target.entity_id` | entity | **Yes** | Target calendar entity (or list of entities). |
| `summary` | string | No | Match events with this summary. |
| `summary_match_mode` | string | No | `exact` (default), `exact_case_sensitive`, `contains`, `startswith`, `endswith`, `regex`. |
| `description` | string | No | Filter events containing this text in description. |
| `location` | string | No | Filter events containing this location. |
| `uids` | list | No | Explicit list of UIDs to delete. |
| `start_date_time` / `end_date_time` | datetime | No | Datetime search boundaries. |
| `start_date` / `end_date` | date | No | Date search boundaries. |
| `all_time` | boolean | No | Search all time (1970–2099). Default `false`. |
| `limit` | integer | No | Maximum number of events to delete. |
| `delete_all` | boolean | No | Safety override. Must be `true` if deleting without any search filters. |
| `dry_run` | boolean | No | If `true`, returns what would be deleted without deleting. |

#### Examples:

**Delete all recurring garbage pickup reminders in the next month:**
```yaml
action: calendar_helper.delete_events
target:
  entity_id: calendar.chores
data:
  summary: "Trash Pickup"
  summary_match_mode: "contains"
  start_date_time: "{{ now().isoformat() }}"
  end_date_time: "{{ (now() + timedelta(days=30)).isoformat() }}"
```

**Dry run test before deleting:**
```yaml
action: calendar_helper.delete_events
target:
  entity_id: calendar.work
data:
  summary: "Cancelled"
  summary_match_mode: "contains"
  dry_run: true
response_variable: preview
```

---

### 3. `calendar_helper.clear_calendar`

Clears events in bulk (all events, only past events, or only future events).

#### Parameters:
| Parameter | Type | Required | Description |
|---|---|---|---|
| `target.entity_id` | entity | **Yes** | Target calendar entity. |
| `confirm` | boolean | **Yes** | Confirmation flag (must be `true`). |
| `only_past` | boolean | No | Clear only events that ended in the past. Default `false`. |
| `only_future` | boolean | No | Clear only events starting in the future. Default `false`. |
| `dry_run` | boolean | No | Preview events to clear without removing them. Default `false`. |

#### Example:

**Prune all past events older than today:**
```yaml
action: calendar_helper.clear_calendar
target:
  entity_id: calendar.temporary_tasks
data:
  confirm: true
  only_past: true
```

---

## Practical Automation Examples

### Automation 1: Remove "Trash Day" event when bin sensor triggers
```yaml
alias: "Chores: Clear trash calendar event on bin emptied"
trigger:
  - platform: state
    entity_id: binary_sensor.trash_bin_sensor
    to: "off"
action:
  - action: calendar_helper.delete_event
    target:
      entity_id: calendar.household
    data:
      summary: "Take out bins"
      summary_match_mode: "contains"
```

### Automation 2: Weekly cleanup of old past events
```yaml
alias: "Calendar: Prune old events every Sunday night"
trigger:
  - platform: time
    at: "23:59:00"
condition:
  - condition: time
    weekday:
      - sun
action:
  - action: calendar_helper.clear_calendar
    target:
      entity_id: calendar.work_schedule
    data:
      confirm: true
      only_past: true
```

### Automation 3: Capture deleted events and send mobile notification
```yaml
alias: "Notify on cancelled shifts removed"
trigger:
  - platform: webhook
    webhook_id: shift_cancelled_webhook
action:
  - action: calendar_helper.delete_events
    target:
      entity_id: calendar.work_schedule
    data:
      summary: "Cancelled"
      summary_match_mode: "contains"
    response_variable: deleted_result
  - action: notify.mobile_app_phone
    data:
      title: "Calendar Updated"
      message: >
        Deleted {{ deleted_result.deleted_count }} cancelled event(s) from your schedule.
```

---

## Troubleshooting & FAQ

#### Q: Does this work with Google Calendar or CalDAV?
**A:** This works with any calendar integration that implements the Home Assistant `DELETE_EVENT` entity feature flag and `async_delete_event`. This includes the built-in Home Assistant **Local Calendar** (`local_calendar`). External services like Google Calendar or CalDAV will work if they support deletion through Home Assistant.

#### Q: How do I know what event UID to pass?
**A:** You can either:
1. Simply pass `summary: "Event Name"` and let Calendar Helper locate the event automatically!
2. Call `calendar.get_events` with `response_variable` to inspect the `uid` of any event.

---

## Contributing & License

Pull requests, feature requests, and bug reports are welcome! Please open an issue on GitHub.

Distributed under the [MIT License](LICENSE).
