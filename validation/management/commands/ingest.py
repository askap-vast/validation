from datetime import timedelta
from pathlib import Path
import re
from typing import List
from astropy.coordinates import SkyCoord, EarthLocation
from astropy.io import fits
from astropy.table import Table
from astropy.time import Time
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils.timezone import make_aware, utc
from validation.models import Observation, Field

ASKAP_ANT01_LOCATION = EarthLocation.from_geodetic(116.631424, -26.697000, 360.99)


class Command(BaseCommand):
    help = (
        "Looks for new images and adds them to the databasea long with their catalogs."
        " The data products MUST be named according to the VAST naming convention, e.g."
        " contain the field name in the form of 'VAST_0012-06A' and the SBID in the"
        " form of 'SB12345'."
    )

    def handle(self, *args, **kwargs):
        image_root_path: Path = settings.IMAGE_DATA_DIR
        catalog_root_path: Path = settings.CATALOG_DATA_DIR
        image_paths = image_root_path.glob("**/*.fits")
        seen_images = [
            Path(path).name
            for path in Observation.objects.all().values_list("image_path", flat=True)
        ]
        glob_count = 0
        ingest_count = 0
        skip_count = 0
        for image_path in image_paths:
            glob_count += 1
            # check if the image has been ingested already
            if image_path.name in seen_images:
                skip_count += 1
                continue  # next image file
            # image is new, check the naming convention
            else:
                sbid_match = re.search(r"SB(\d+)", image_path.name)
                if sbid_match is None:
                    self.stdout.write(
                        self.style.ERROR(
                            "Could not find the SBID in the filename for"
                            f" {image_path.name}"
                        )
                    )
                    continue  # next image file
                else:
                    sbid = int(sbid_match.group(1))
                field_match = re.search(r"VAST_\d+[\+\-]\d+\w?", image_path.name)
                if field_match is None:
                    self.stdout.write(
                        self.style.ERROR(
                            "Could not find the field in the filename for"
                            f" {image_path.name}"
                        )
                    )
                    continue  # next image file
                else:
                    field = field_match.group(0)

            epoch = image_path.parent.name
            # check if the components file exists under the assumed name
            components_path = (
                catalog_root_path / epoch / f"selavy-{image_path.name}"
            ).with_suffix(".components.xml")
            if not components_path.exists():
                self.stdout.write(
                    self.style.ERROR(
                        "No components catalog found for image"
                        f" {image_path.name} assuming the name {components_path.name}."
                        " Skipping."
                    )
                )
                continue  # next image file

            # check if the islands file exists under the assumed name
            islands_path = (
                catalog_root_path / epoch / f"selavy-{image_path.name}"
            ).with_suffix(".islands.xml")
            if not islands_path.exists():
                self.stdout.write(
                    self.style.ERROR(
                        f"No islands catalog found for image {image_path.name} assuming"
                        f" the name {islands_path.name}. Skipping."
                    )
                )
                continue  # next image file

            # all files exist and are new and named correctly - ingest!
            # get some metadata from the FITS image header
            image_header = fits.getheader(image_path)
            missing_header_cards: List[str] = []
            for card in (
                "DATE-OBS",
                "DURATION",
                "DATE",
                "CRVAL3",
                "BMAJ",
                "BMIN",
                "BPA",
                "CRVAL1",
                "CRVAL2",
            ):
                if card not in image_header:
                    missing_header_cards.append(card)
            if len(missing_header_cards) > 0:
                self.stdout.write(
                    self.style.ERROR(
                        f"Required FITS header cards {missing_header_cards} are not"
                        f" present in image {image_path.name}. Skipping."
                    )
                )
                continue  # next image file
            frequency_MHz = image_header["CRVAL3"] / 1e6
            frequency_band = (
                Field.FrequencyBand.LOW
                if frequency_MHz <= 888
                else Field.FrequencyBand.MID
            )
            start_time = Time(image_header["DATE-OBS"], location=ASKAP_ANT01_LOCATION)
            lmst = start_time.sidereal_time(kind="mean")
            image_ref_coord = SkyCoord(
                ra=image_header["CRVAL1"],
                dec=image_header["CRVAL2"],
                unit="deg",
                location=ASKAP_ANT01_LOCATION,
                obstime=start_time,
            )
            hour_angle = lmst - image_ref_coord.ra

            field_obj, _ = Field.objects.get_or_create(
                name=field,
                frequency_band=frequency_band,
                defaults={
                    "ra": image_ref_coord.ra.deg,
                    "dec": image_ref_coord.dec.deg,
                    "frequency_MHz": frequency_MHz,
                },
            )

            obs = Observation(
                sbid=sbid,
                field=field_obj,
                image_path=image_path,
                components_path=components_path,
                islands_path=islands_path,
                start_datetime=make_aware(start_time.datetime, timezone=utc),
                duration=timedelta(seconds=float(image_header["DURATION"])),
                imaged_datetime=make_aware(
                    Time(image_header["DATE"]).datetime, timezone=utc
                ),
                psf_major_arcsec=image_header["BMAJ"] * 3600,
                psf_minor_arcsec=image_header["BMIN"] * 3600,
                psf_pa_deg=image_header["BPA"],
                num_components=len(Table.read(components_path)),
                hour_angle=hour_angle.hourangle,
                elevation=image_ref_coord.altaz.alt.deg,
            )
            obs.save()

            # TODO crossmatching here. Add Crossmatch record and write output CSV file
            # to settings.CROSSMATCH_DIR with name e.g.
            # VAST_0012-06A.SB11111.RACS.<Observation ID>.csv. Include the observation
            # ID in the rare case of duplicate fields in a SB.

            self.stdout.write(
                self.style.SUCCESS(
                    f"Data products for {field} SB{sbid} were ingested successfully:"
                    f" {image_path.name}, {components_path.name}, {islands_path.name}."
                )
            )
            ingest_count += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"{glob_count} observations were detected. {ingest_count} were"
                f" ingested, {skip_count} were skipped as they were already ingested."
            )
        )
