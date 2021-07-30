from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class Observation(models.Model):
    """A VAST observation of a single field. Most observations have their own unique
    SBID, but not all do e.g. the earliest observations.
    """

    class ValidationState(models.TextChoices):
        NOT_VALIDATED = "N"
        REJECTED = "R"
        GOOD = "G"
        UNCERTAIN = "U"

    class FrequencyBand(models.IntegerChoices):
        LOW = 1  # <= 888 MHz
        MID = 2

    sbid = models.PositiveIntegerField()
    calibration_sbid = models.PositiveIntegerField(null=True, default=None)
    field = models.CharField(max_length=15)
    image_path = models.FilePathField(
        path=str(settings.VALIDATION_DIR.resolve()),
        match=r".*\.fits$",
        recursive=True,
        max_length=200,
    )
    components_path = models.FilePathField(
        path=str(settings.VALIDATION_DIR.resolve()),
        match=r".*\.(xml|txt)$",
        recursive=True,
        max_length=200,
    )
    islands_path = models.FilePathField(
        path=str(settings.VALIDATION_DIR.resolve()),
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
        User, on_delete=models.SET_NULL, null=True, default=None
    )
    start_datetime = models.DateTimeField()
    duration = models.DurationField()
    epoch = models.CharField(max_length=9, blank=True, default="")
    imaged_datetime = models.DateTimeField()
    ingested_datetime = models.DateTimeField(auto_now_add=True)
    validated_datetime = models.DateTimeField(auto_now=True)
    frequency_band = models.PositiveSmallIntegerField(choices=FrequencyBand.choices)
    psf_major_arcsec = models.FloatField()
    psf_minor_arcsec = models.FloatField()
    psf_pa_deg = models.FloatField()
    num_components = models.PositiveIntegerField()
    rms_median = models.FloatField(null=True, default=None)
    hour_angle = models.FloatField()
    elevation = models.FloatField()

    def __str__(self):
        return f"{self.field} SB{self.sbid}"


class Crossmatch(models.Model):
    """A VAST Observation catalog crossmatched with an external reference catalog, e.g.
    RACS. Each Crossmatch object points to a CSV file of crossmatches.
    """

    observation = models.ForeignKey(Observation, on_delete=models.CASCADE)
    reference_catalog = models.CharField(max_length=25)
    file_path = models.FilePathField(
        path=settings.VALIDATION_DIR, match=r".*\.csv$", max_length=200
    )
    # TODO add crossmatch metadata e.g. radius, SNR cutoffs. Anything required to reproduce.
