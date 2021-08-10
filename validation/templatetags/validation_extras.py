from datetime import timedelta
from django import template

register = template.Library()


@register.filter
def duration_mins(td: timedelta):
    mins = int(td.total_seconds() // 60)
    secs = td.total_seconds() - (mins * 60)
    return f"{mins:02d}:{secs:02.0f}"
