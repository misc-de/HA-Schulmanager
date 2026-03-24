```yaml
type: markdown
title: Homework
content: |
  {% set items = state_attr('sensor.YOUR_SCHULMANAGER_HOMEWORK_ENTITY', 'items') %}

  {% if items %}
  {% for item in items %}
  {% for entry in item.entries %}
  {% set parts = entry.split(':', 1) %}
  {{ parts[0] | replace('#', '\\#') | trim }}: {{ parts[1].strip() | replace('#', '\\#') if parts|length > 1 else '' }}

  {% endfor %}
  {% endfor %}
  {% else %}
  No homework available.
  {% endif %}
```
