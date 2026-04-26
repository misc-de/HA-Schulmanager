# Dashboard examples

These examples are intended for Home Assistant dashboards.

Replace the placeholder entity IDs with your own entity IDs:

- `sensor.YOUR_SCHULMANAGER_SCHEDULE_WEEK_ENTITY`
- `sensor.YOUR_SCHULMANAGER_SCHEDULE_TODAY_ENTITY`
- `sensor.YOUR_SCHULMANAGER_MEAL_TODAY_ENTITY`
- `sensor.YOUR_SCHULMANAGER_HOMEWORK_ENTITY`

You can find the real entity IDs in Home Assistant under:
**Developer Tools → States**

## Examples

- `stundenplan-woche.md` – dedicated Schulmanager timetable Lovelace card
- `hausaufgaben.md` – dedicated Schulmanager homework Lovelace card
- `hausaufgaben-timeline.md` – homework grouped by date with a timeline layout
- `debug-status.md` – debug/status card
- `service-refresh.md` – manual refresh service example

## Timetable card

Add this dashboard resource once:

/schulmanager_static/schulmanager-timetable-card.js?v=0.3.25

Resource type: `JavaScript Module`

Card configuration:

type: custom:schulmanager-timetable-card
entity: sensor.YOUR_SCHULMANAGER_SCHEDULE_WEEK_ENTITY
title: Stundenplan

Homework card:

type: custom:schulmanager-homework-card
entity: sensor.YOUR_SCHULMANAGER_HOMEWORK_ENTITY
title: Hausaufgaben

In the visual editor the cards show entity pickers and prefer matching
Schulmanager sensors.
