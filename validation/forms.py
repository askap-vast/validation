from django import forms
from validation.models import Observation


class ValidationForm(forms.ModelForm):
    class Meta:
        model = Observation
        fields = [
            "data_quality",
            "validation_comment",
        ]
        widgets = {
            "data_quality": forms.RadioSelect(attrs={"class": "form-check-input"}),
            "validation_comment": forms.Textarea(
                attrs={"class": "form-control", "rows": 3}
            ),
        }
