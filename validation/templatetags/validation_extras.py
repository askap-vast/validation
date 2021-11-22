from datetime import timedelta
from django import template
from django.http import QueryDict

register = template.Library()


@register.filter
def duration_mins(td: timedelta) -> str:
    mins = int(td.total_seconds() // 60)
    secs = td.total_seconds() - (mins * 60)
    return f"{mins:02d}:{secs:02.0f}"


@register.simple_tag(takes_context=True)
def replace_param(context, **kwargs) -> str:
    """Template tag that returns GET params as a URL encoded string, optionally
    replacing any given parameters with the values provided in kwargs. Blank parameters
    (i.e. params with empty values) are dropped.
    """
    querydict: QueryDict = context["request"].GET.copy()
    # replace the request params
    for k, v in kwargs.items():
        querydict[k] = v
    # remove empty params (not required but cleans up the URL)
    for k in [k for k, v in querydict.items() if v == ""]:
        del querydict[k]
    return querydict.urlencode()
