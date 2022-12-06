from typing import TYPE_CHECKING
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from validation.models import Observation

if TYPE_CHECKING:
    from django.core.management.base import CommandParser

User = get_user_model()


class Command(BaseCommand):
    help = (
        "Export the data quality flags for observations in CSV format. Ignores"
        " observations that are not yet validated."
    )

    def add_arguments(self, parser: "CommandParser"):
        parser.add_argument("obs_epochs", nargs="*", type=int)

    def handle(self, *args, **kwargs):
        observations = Observation.objects.exclude(
            data_quality=Observation.ValidationState.NOT_VALIDATED
        )
        if kwargs["obs_epochs"]:
            observations = observations.filter(
                observation_epoch__in=kwargs["obs_epochs"]
            )
            self.stderr.write(
                self.style.NOTICE(
                    f"Exporting {len(observations)} observations from observation"
                    f" epochs {kwargs['obs_epochs']}."
                )
            )
        else:
            self.stderr.write(
                self.style.NOTICE(
                    f"Exporting {len(observations)} observations without selecting"
                    " observation epochs."
                )
            )
        self.stdout.write("SBID,quality")
        for obs in observations:
            self.stdout.write(f"{obs.sbid},{obs.get_data_quality_display().upper()}")
