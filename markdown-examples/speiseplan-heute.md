```yaml
type: markdown
title: Schulmanager Meal Plan Today
content: |
  {% set meals = state_attr('sensor.YOUR_SCHULMANAGER_MEAL_TODAY_ENTITY', 'today') %}
  {% if not meals %}
    {% set meals = state_attr('sensor.YOUR_SCHULMANAGER_MEAL_TODAY_ENTITY', 'items') %}
  {% endif %}

  {% if meals %}
  | # | Meal |
  | --- | --- |
  {% for meal in meals -%}
  | {{ loop.index }} | {{ meal.menu if meal.menu is defined else meal }} |
  {% endfor %}
  {% else %}
  No meal plan available.
  {% endif %}
```
