```yaml
type: markdown
title: Schulmanager Schedule Today
content: |
  {% set today = state_attr('sensor.YOUR_SCHULMANAGER_SCHEDULE_TODAY_ENTITY', 'today') %}
  {% set day = state_attr('sensor.YOUR_SCHULMANAGER_SCHEDULE_TODAY_ENTITY', 'today_name') %}

  {% if today %}
  | Period | {{ day }} |
  | --- | --- |
  {% for lesson in today -%}
  | {{ loop.index }} | {{ lesson }} |
  {% endfor %}
  {% else %}
  No schedule available.
  {% endif %}
```
