from itertools import product
from pathlib import Path
from django.core.management.base import BaseCommand, ArgumentParser, CommandError
from django.conf import settings
from validation.models import Observation


DATA_DIRS = (
    "STOKESI_IMAGES",
    "STOKESI_RMSMAPS",
    "STOKESI_SELAVY",
    "STOKESI_MOCS",
    "STOKESI_WEIGHTS",
    "STOKESV_IMAGES",
    "STOKESV_RMSMAPS",
    "STOKESV_SELAVY",
    "STOKESV_WEIGHTS",
)


class Command(BaseCommand):
    help = (
        "Create hard links in the release directories for passing validated"
        " observations. Only observations that have been assigned a release epoch and"
        " have been validated with an acceptable data quality flag (i.e. GOOD or"
        " UNCERTAIN) are processed."
    )

    def _check_path_exists(self, path: Path) -> bool:
        if not path.exists():
            self.stderr.write(self.style.ERROR(f"{path} does not exist."))
        return path.exists()

    def add_arguments(self, parser: ArgumentParser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--overwrite", action="store_true")
        parser.add_argument("obs_epochs", nargs="+", type=int)

    def handle(self, *args, **kwargs):
        # get the observations ready for release
        obs_ready = Observation.objects.exclude(release_epoch="").filter(
            observation_epoch__in=kwargs["obs_epochs"],
            data_quality__in=Observation.ValidationState.accepted_states(),
        )
        release_epochs = set(obs_ready.values_list("release_epoch", flat=True))

        # create necessary release directories
        for release_epoch, data_dir in product(release_epochs, DATA_DIRS):
            epoch_data_dir: Path = (
                settings.RELEASE_DATA_DIR / release_epoch / "TILES" / data_dir
            )
            epoch_data_dir.mkdir(parents=True, exist_ok=True)

        # prepare links to the data in the release directories
        links: list[tuple[Path, Path]] = []
        for obs in obs_ready:
            base_path = settings.RELEASE_DATA_DIR / obs.release_epoch / "TILES"
            all_files_exist = True

            # image
            image_path = Path(obs.image_path)
            image_target = base_path / "STOKESI_IMAGES" / image_path.name
            all_files_exist = all_files_exist and self._check_path_exists(image_path)

            # rms image
            rms_path = (
                Path(obs.image_path.replace("STOKESI_IMAGES", "STOKESI_RMSMAPS")).parent
                / f"noiseMap.{image_path.name}"
            )
            rms_target = base_path / "STOKESI_RMSMAPS" / rms_path.name
            all_files_exist = all_files_exist and self._check_path_exists(rms_path)

            # background image
            background_path = (
                Path(obs.image_path.replace("STOKESI_IMAGES", "STOKESI_RMSMAPS")).parent
                / f"meanMap.{image_path.name}"
            )
            background_target = base_path / "STOKESI_RMSMAPS" / background_path.name
            all_files_exist = all_files_exist and self._check_path_exists(
                background_path
            )

            # selavy components catalog
            components_path = Path(obs.components_path)
            components_target = base_path / "STOKESI_SELAVY" / components_path.name
            all_files_exist = all_files_exist and self._check_path_exists(
                components_path
            )

            # selavy islands catalog
            islands_path = Path(obs.islands_path)
            islands_target = base_path / "STOKESI_SELAVY" / islands_path.name
            all_files_exist = all_files_exist and self._check_path_exists(islands_path)

            # MOC
            moc_path = (
                Path(obs.image_path.replace("STOKESI_IMAGES", "STOKESI_MOCS")).parent
                / image_path.with_suffix(".moc.fits").name
            )
            moc_target = base_path / "STOKESI_MOCS" / moc_path.name
            all_files_exist = all_files_exist and self._check_path_exists(moc_path)

            # weights image
            weight_path = Path(
                obs.image_path.replace("STOKESI_IMAGES", "STOKESI_WEIGHTS")
            ).parent / (
                image_path.name.replace("image", "weights")
                .replace(".restored", "")
                .replace(".conv", "")
            )
            weight_target = base_path / "STOKESI_WEIGHTS" / weight_path.name
            all_files_exist = all_files_exist and self._check_path_exists(weight_path)

            # store the release links if all the assumed files exist, otherwise raise
            # an exception and abort the release.
            if all_files_exist:
                links.append((image_path, image_target))
                links.append((rms_path, rms_target))
                links.append((background_path, background_target))
                links.append((components_path, components_target))
                links.append((islands_path, islands_target))
                links.append((moc_path, moc_target))
                links.append((weight_path, weight_target))
            else:
                raise CommandError(
                    f"One or more data files for {obs} doesn't exist. Aborting release."
                )

        # create the links or print what would be linked if --dry-run was passed
        for source_path, target_path in links:
            if kwargs["dry_run"]:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Would create link {source_path} -> {target_path}."
                    )
                )
            else:
                if target_path.exists() and kwargs["overwrite"]:
                    target_path.unlink()

                if not target_path.exists():
                    source_path.link_to(target_path)
                    if kwargs["verbosity"] > 0:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Created link {source_path} -> {target_path}."
                            )
                        )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f"{target_path} already exists. Not overwriting."
                        )
                    )

        message_prefix = "Would release" if kwargs["dry_run"] else "Released"
        self.stdout.write(
            self.style.SUCCESS(f"{message_prefix} {len(obs_ready)} observations.")
        )
