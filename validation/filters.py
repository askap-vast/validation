from django.forms.widgets import (
    CheckboxSelectMultiple,
    DateTimeInput,
    NumberInput,
    TextInput,
)
import django_filters

from validation.models import Observation, Field


class ObservationFilter(django_filters.FilterSet):
    band = django_filters.MultipleChoiceFilter(
        field_name="field__frequency_band",
        label="Band",
        choices=Field.FrequencyBand.choices,
        widget=CheckboxSelectMultiple(),
    )
    field = django_filters.ModelChoiceFilter(
        to_field_name="name",
        queryset=Field.objects.all().order_by("name"),
    )
    sbid__after = django_filters.NumberFilter(
        field_name="sbid",
        lookup_expr="gte",
        widget=NumberInput(attrs={"class": "form-control"}),
    )
    sbid__before = django_filters.NumberFilter(
        field_name="sbid",
        lookup_expr="lte",
        widget=NumberInput(attrs={"class": "form-control"}),
    )
    data_quality = django_filters.MultipleChoiceFilter(
        choices=Observation.ValidationState.choices,
        widget=CheckboxSelectMultiple(),
    )
    start_datetime__after = django_filters.DateTimeFilter(
        field_name="start_datetime",
        lookup_expr="gte",
        widget=DateTimeInput(
            attrs={"placeholder": "yyyy-mm-dd HH:MM:SS", "class": "form-control"}
        ),
    )
    start_datetime__before = django_filters.DateTimeFilter(
        field_name="start_datetime",
        lookup_expr="lte",
        widget=DateTimeInput(
            attrs={"placeholder": "yyyy-mm-dd HH:MM:SS", "class": "form-control"}
        ),
    )
    observation_epoch = django_filters.NumberFilter(
        widget=NumberInput(attrs={"class": "form-control"})
    )
    release_epoch = django_filters.CharFilter(
        widget=TextInput(attrs={"class": "form-control"})
    )
    sort = django_filters.OrderingFilter(
        fields=("field", "sbid", "start_datetime", "data_quality"),
        field_labels={
            "sbid": "SBID",
        }
    )

    class Meta:
        model = Observation
        fields = [
            "band",
            "field",
            "sbid__after",
            "sbid__before",
            "start_datetime__after",
            "start_datetime__before",
            "observation_epoch",
            "release_epoch",
            "data_quality",
            "sort",
        ]
