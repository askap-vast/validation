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
        parser.add_argument("--ignore-mocs", action="store_true")
        parser.add_argument("--ignore-stokesv", action="store_true")
        parser.add_argument("--move-weights", action="store_true")
        
    def generate_paths(self,
                       image_path,
                       components_path,
                       islands_path,
                       base_path,
                       stokes,
                       links,
                       ignore_mocs=False,
                       move_weights=False):
        stokes = stokes.upper()
        all_files_exist = True
        image_path_str = str(image_path)
        
        # Image
        image_target = base_path / f"STOKES{stokes}_IMAGES" / image_path.name
        all_files_exist = all_files_exist and self._check_path_exists(image_path)
        
        # RMS map
        rms_path = (
                Path(image_path_str.replace(f"STOKES{stokes}_IMAGES", f"STOKES{stokes}_RMSMAPS")).parent
                / f"noiseMap.{image_path.name}"
        )
        rms_target = base_path / f"STOKES{stokes}_RMSMAPS" / rms_path.name
        all_files_exist = all_files_exist and self._check_path_exists(rms_path)  
        
        # Background map
        background_path = (
                Path(image_path_str.replace(f"STOKES{stokes}_IMAGES", f"STOKES{stokes}_RMSMAPS")).parent
                / f"meanMap.{image_path.name}"
        )
        background_target = base_path / f"STOKES{stokes}_RMSMAPS" / background_path.name
        all_files_exist = all_files_exist and self._check_path_exists(
            background_path
        )
        
        # Selavy components catalogue
        components_path = Path(components_path)
        components_target = base_path / f"STOKES{stokes}_SELAVY" / components_path.name
        all_files_exist = all_files_exist and self._check_path_exists(
            components_path
        )

        # Selavy islands catalogue
        islands_path = Path(islands_path)
        islands_target = base_path / f"STOKES{stokes}_SELAVY" / islands_path.name
        all_files_exist = all_files_exist and self._check_path_exists(islands_path)
        
        if stokes == "V":
            islands_path_n = islands_path.parent / islands_path.name.replace('selavy-image', 'selavy-nimage')
            islands_target_n = islands_target.parent / islands_target.name.replace('selavy', 'nselavy')
            all_files_exist = all_files_exist and self._check_path_exists(islands_path_n)
            
            components_path_n = components_path.parent / components_path.name.replace('selavy-image', 'selavy-nimage')
            components_target_n = components_target.parent / components_target.name.replace('selavy', 'nselavy')
            all_files_exist = all_files_exist and self._check_path_exists(components_path_n)
        
        # Weights map
        if move_weights:
            weight_path = Path(
                image_path_str.replace(f"STOKES{stokes}_IMAGES", f"STOKES{stokes}_WEIGHTS")
            ).parent / (
                image_path.name.replace("image", "weights")
                .replace(".restored", "")
                .replace(".conv", "")
            )
            weight_target = base_path / f"STOKES{stokes}_WEIGHTS" / weight_path.name
            all_files_exist = all_files_exist and self._check_path_exists(weight_path)
        
        # Stokes I MOC
        if stokes == "I" and not ignore_mocs:
            moc_path = (
                Path(image_path_str.replace("STOKESI_IMAGES", "STOKESI_MOCS")).parent
                / image_path.with_suffix(".moc.fits").name
            )
            moc_target = base_path / "STOKESI_MOCS" / moc_path.name
            all_files_exist = all_files_exist and self._check_path_exists(moc_path)
        
        
        if all_files_exist:
            links.append((image_path, image_target))
            links.append((rms_path, rms_target))
            links.append((background_path, background_target))
            links.append((components_path, components_target))
            links.append((islands_path, islands_target))
            
            if move_weights:
                links.append((weight_path, weight_target))
            if stokes == "I" and not ignore_mocs:
                links.append((moc_path, moc_target))
            if stokes == "V":
                links.append((islands_path_n, islands_target_n))
                links.append((components_path_n, components_target_n))
        else:
            raise CommandError(
                f"One or more data files for doesn't exist. Aborting release."
            )
        
    def _correct_stokes_path(self, path, stokes):
        path_str = str(path)
        path_str = path_str.replace("STOKESI",
                                    f"STOKES{stokes.upper()}"
                                    )
        path_str = path_str.replace(".i.",
                                    f".{stokes.lower()}."
                                    )
        return Path(path_str)
        
    def handle(self, *args, **kwargs):
        # get the observations ready for release
        obs_ready = Observation.objects.exclude(release_epoch="").filter(
            observation_epoch__in=kwargs["obs_epochs"],
            data_quality__in=Observation.ValidationState.accepted_states(),
        )
        release_epochs = set(obs_ready.values_list("release_epoch", flat=True))

        stokes_vals = ["I", "V"]
        if kwargs["ignore_stokesv"]:
            stokes_vals = ["I"]
        # create necessary release directories
        for release_epoch, data_dir in product(release_epochs, DATA_DIRS):
            epoch_data_dir: Path = (
                settings.RELEASE_DATA_DIR / release_epoch / "TILES" / data_dir
            )
            epoch_data_dir.mkdir(parents=True, exist_ok=True)

        # prepare links to the data in the release directories
        links: list[tuple[Path, Path]] = []

        for obs in obs_ready:
            stokes_I_image_path = obs.image_path
            stokes_I_comp_path = obs.components_path
            stokes_I_isl_path = obs.islands_path
            
            base_path = settings.RELEASE_DATA_DIR / obs.release_epoch / "TILES"
            
            for stokes in stokes_vals:
                image_path = self._correct_stokes_path(stokes_I_image_path, stokes)
                components_path = self._correct_stokes_path(stokes_I_comp_path, stokes)
                islands_path = self._correct_stokes_path(stokes_I_isl_path, stokes)
                
                self.generate_paths(image_path,
                                    components_path,
                                    islands_path,
                                    base_path,
                                    stokes,
                                    links,
                                    ignore_mocs=kwargs["ignore_mocs"],
                                    move_weights=kwargs["move_weights"]
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
