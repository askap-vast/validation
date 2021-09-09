from pathlib import Path
from typing import Optional
from urllib.parse import urlencode, urlsplit, urlunsplit, SplitResult
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.urls import reverse

User = get_user_model()


class Field(models.Model):
    class FrequencyBand(models.IntegerChoices):
        LOW = 1  # <= 888 MHz
        MID = 2

    name = models.CharField(max_length=15)
    frequency_MHz = models.FloatField(help_text="Frequency in MHz")
    frequency_band = models.PositiveSmallIntegerField(choices=FrequencyBand.choices)
    ra = models.FloatField()
    dec = models.FloatField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["name", "frequency_band"], name="unique_field"
            ),
        ]

    def __str__(self):
        return f"{self.name} - {self.get_frequency_band_display()} band"


class Observation(models.Model):
    """A VAST observation of a single field. Most observations have their own unique
    SBID, but not all do e.g. the earliest observations.
    """

    class ValidationState(models.TextChoices):
        GOOD = "G"
        UNCERTAIN = "U"
        REJECTED = "R"
        NOT_VALIDATED = "N"

        @classmethod
        def get_color_class(cls, validation_state):
            color_class = "primary"
            if validation_state == cls.REJECTED:
                color_class = "danger"
            elif validation_state == cls.UNCERTAIN:
                color_class = "dark"
            elif validation_state == cls.GOOD:
                color_class = "success"
            elif validation_state == cls.NOT_VALIDATED:
                color_class = "warning"
            return color_class

    sbid = models.PositiveIntegerField()
    calibration_sbid = models.PositiveIntegerField(null=True, blank=True, default=None)
    field = models.ForeignKey(Field, on_delete=models.CASCADE)
    image_path = models.FilePathField(
        path=str(settings.IMAGE_DATA_DIR.resolve()),
        match=r".*\.fits$",
        recursive=True,
        max_length=200,
    )
    components_path = models.FilePathField(
        path=str(settings.CATALOG_DATA_DIR.resolve()),
        match=r".*\.(xml|txt)$",
        recursive=True,
        max_length=200,
    )
    islands_path = models.FilePathField(
        path=str(settings.CATALOG_DATA_DIR.resolve()),
        match=r".*\.(xml|txt)$",
        recursive=True,
        max_length=200,
    )
    data_quality = models.CharField(
        max_length=1,
        choices=ValidationState.choices,
        default=ValidationState.NOT_VALIDATED,
    )
    validator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None,
        related_name="validated_observations",
    )
    assigned_validator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None,
        related_name="assigned_observations",
    )
    start_datetime = models.DateTimeField()
    duration = models.DurationField()
    epoch = models.CharField(max_length=9, blank=True, default="")
    imaged_datetime = models.DateTimeField()
    ingested_datetime = models.DateTimeField(auto_now_add=True)
    validated_datetime = models.DateTimeField(auto_now=True)
    psf_major_arcsec = models.FloatField()
    psf_minor_arcsec = models.FloatField()
    psf_pa_deg = models.FloatField()
    num_components = models.PositiveIntegerField()
    rms_median = models.FloatField(null=True, blank=True, default=None)
    hour_angle = models.FloatField()
    elevation = models.FloatField()
    validation_comment = models.TextField(blank=True)

    class Meta:
        ordering = ["field__name", "-sbid"]

    def __str__(self):
        return f"{self.field} SB{self.sbid}"

    @property
    def data_quality_color_class(self):
        return Observation.ValidationState.get_color_class(self.data_quality)

    def get_absolute_url(self):
        return reverse("observation-detail", kwargs={"pk": self.pk})

    def get_carta_url(self) -> Optional[str]:
        url = None
        if settings.CARTA_URL is not None:
            image_path = Path(self.image_path)
            query = {
                "folder": str(image_path.parent),
                "file": image_path.name,
            }
            url_parts = urlsplit(settings.CARTA_URL)
            url_query = (
                urlencode(query)
                if url_parts.query == ""
                else f"{url_parts.query}&{urlencode(query)}"
            )
            url_path = "/" if url_parts.path == "" else url_parts.path
            url_parts = SplitResult(
                url_parts.scheme,
                url_parts.netloc,
                url_path,
                url_query,
                url_parts.fragment,
            )
            url = urlunsplit(url_parts)
        return url


class ReferenceCatalog(models.Model):
    """A reference catalog that can be crossmatched to a VAST Observation catalogs."""

    name = models.CharField(primary_key=True, max_length=25)
    frequency_MHz = models.FloatField(
        help_text="Frequency in MHz", null=True, blank=True
    )

    class Meta:
        ordering = [
            "name",
        ]

    def __str__(self):
        freq_str = (
            f" ({self.frequency_MHz:.0f} MHz)" if self.frequency_MHz is not None else ""
        )
        return f"{self.name}{freq_str}"


class Crossmatch(models.Model):
    """A VAST Observation catalog crossmatched with an external reference catalog, e.g.
    RACS. Each Crossmatch object points to a CSV file of crossmatches.
    """

    observation = models.ForeignKey(Observation, on_delete=models.CASCADE)
    reference_catalog = models.ForeignKey(ReferenceCatalog, on_delete=models.CASCADE)
    file_path = models.FilePathField(
        path=settings.CROSSMATCH_DIR, match=r".*\.csv$", max_length=200
    )
    # TODO add crossmatch metadata e.g. radius, SNR cutoffs. Anything required to reproduce.

    def __str__(self):
        return (
            f"Crossmatch {self.observation.field} -"
            f" SB{self.observation.sbid} {self.reference_catalog}"
        )
