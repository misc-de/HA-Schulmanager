```yaml
type: markdown
title: Schulmanager Schedule Week
content: |
  {% set rows = state_attr('sensor.YOUR_SCHULMANAGER_SCHEDULE_WEEK_ENTITY', 'week_rows') %}

  {% if rows %}
  | Period | Mon | Tue | Wed | Thu | Fri |
  | --- | --- | --- | --- | --- | --- |
  {% for row in rows -%}
  | {{ row.lesson }} | {{ row.Mo if row.Mo else '—' }} | {{ row.Di if row.Di else '—' }} | {{ row.Mi if row.Mi else '—' }} | {{ row.Do if row.Do else '—' }} | {{ row.Fr if row.Fr else '—' }} |
  {% endfor %}
  {% else %}
  No schedule available.
  {% endif %}
```
