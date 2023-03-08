from itertools import chain
from pathlib import Path
from astropy.table import Table
from django.core.management.base import BaseCommand, ArgumentParser
from django.conf import settings
from validation.models import Observation, Crossmatch, ReferenceCatalog


class Command(BaseCommand):
    help = (
        "Looks for new crossmatch catalogs in the crossmatches directory and adds any"
        " new ones to their relevant VAST observation."
    )

    def add_arguments(self, parser: ArgumentParser):
        parser.add_argument("obs_epochs", nargs="*", type=int)

    def handle(self, *args, **kwargs):
        data_path: Path = settings.CROSSMATCH_DIR
        # ingest selected epochs, or everything if not given
        if len(kwargs["obs_epochs"]) > 0:
            catalog_paths = chain.from_iterable(
                [
                    data_path.glob(f"epoch_{obs_epoch}/*.csv")
                    for obs_epoch in kwargs["obs_epochs"]
                ]
            )
        else:
            catalog_paths = data_path.glob("**/*.csv")
        seen_catalogs = [
            Path(path).name
            for path in Crossmatch.objects.all().values_list("file_path", flat=True)
        ]
        for catalog_path in catalog_paths:
            # check if the catalog has been ingested already
            if catalog_path.name in seen_catalogs:
                self.stdout.write(
                    self.style.WARNING(
                        f"A crossmatch catalog with the name {catalog_path.name} has"
                        " already been ingested. Ignoring."
                    )
                )
                continue  # next catalog
            # catalog is new
            else:
                # check the catalog has data
                t = Table.read(str(catalog_path))
                if len(t) == 0:
                    continue   # next catalog
                # check the naming convention
                field, sbid, ref_catalog_name, *_ = catalog_path.name.split(".")
                sbid = int(sbid[2:])

            # get the observation
            try:
                obs = Observation.objects.get(sbid=sbid, field__name=field)
            except Observation.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(
                        f"Could not find a VAST observation for {field} SB{sbid}."
                        f" Ignoring catalog {catalog_path.name}."
                    )
                )
                continue  # next catalog

            # get the reference catalog
            try:
                ref_catalog = ReferenceCatalog.objects.get(name=ref_catalog_name)
            except ReferenceCatalog.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(
                        f"Could not find a reference catalog named {ref_catalog_name}."
                        f" Ignoring catalog {catalog_path.name}."
                    )
                )
                continue  # next catalog

            # create the crossmatch record
            cm = Crossmatch(
                observation=obs,
                reference_catalog=ref_catalog,
                file_path=catalog_path.resolve(),
            )
            cm.save()

            self.stdout.write(
                self.style.SUCCESS(
                    f"Crossmatch catalog {catalog_path.name} was associated with {obs}."
                )
            )
