from django import template

from absence.services.time_values import format_hhmm

register = template.Library()


@register.filter
def hhmm(value):
    return format_hhmm(value)
