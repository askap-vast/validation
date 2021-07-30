from pathlib import Path
from django.db.models.signals import post_delete
from django.dispatch import receiver
from validation.models import Observation


@receiver(post_delete, sender=Observation, dispatch_uid="delete_observation_files")
def delete_observation_files(sender, instance: Observation, **kwargs):
    """Delete the image and catalog files when an Observation is deleted.
    """
    image_path = Path(instance.image_path)
    components_path = Path(instance.components_path)
    islands_path = Path(instance.islands_path)
    image_path.unlink()
    components_path.unlink()
    islands_path.unlink()
