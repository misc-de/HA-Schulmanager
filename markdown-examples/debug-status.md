```yaml
type: markdown
title: Schulmanager Debug
content: |
  Schedule week state:
  {{ states('sensor.YOUR_SCHULMANAGER_SCHEDULE_WEEK_ENTITY') }}

  week_rows:
  {{ state_attr('sensor.YOUR_SCHULMANAGER_SCHEDULE_WEEK_ENTITY', 'week_rows') }}

  data_stale:
  {{ state_attr('sensor.YOUR_SCHULMANAGER_SCHEDULE_WEEK_ENTITY', 'data_stale') }}

  last_successful_update:
  {{ state_attr('sensor.YOUR_SCHULMANAGER_SCHEDULE_WEEK_ENTITY', 'last_successful_update') }}

  last_attempted_update:
  {{ state_attr('sensor.YOUR_SCHULMANAGER_SCHEDULE_WEEK_ENTITY', 'last_attempted_update') }}
```
