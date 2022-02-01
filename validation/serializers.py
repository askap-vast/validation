from rest_framework import serializers
from validation.models import Field, Observation


class FieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = Field
        fields = ["name", "frequency_band"]


class ObservationSerializer(serializers.ModelSerializer):
    field_name = serializers.CharField(source="field.name")
    frequency_band = serializers.IntegerField(source="field.frequency_band")

    class Meta:
        model = Observation
        fields = [
            "id",
            "field_name",
            "frequency_band",
            "sbid",
            "data_quality",
            "start_datetime",
            "duration",
            "observation_epoch",
            "release_epoch",
            "imaged_datetime",
            "ingested_datetime",
            "validated_datetime",
            "psf_major_arcsec",
            "psf_minor_arcsec",
            "psf_pa_deg",
            "num_components",
            "hour_angle",
            "elevation",
        ]
