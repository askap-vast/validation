from itertools import cycle
import random
from typing import TYPE_CHECKING
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count
from validation.models import Observation

if TYPE_CHECKING:
    from django.core.management.base import CommandParser

User = get_user_model()


class Command(BaseCommand):
    help = "Randomly assign pending observations to validators."

    def add_arguments(self, parser: "CommandParser"):
        parser.add_argument(
            "-n",
            "--num-obs",
            type=int,
            help=(
                "The maximum number of pending observations to assign to each user."
                " Default is to attempt to evenly distribute among users."
            ),
        )
        parser.add_argument(
            "-d",
            "--dry-run",
            action="store_true",
            help=(
                "Don't assign any validators, only print which observations would be"
                " assigned to whom."
            ),
        )
        parser.add_argument(
            "-a",
            "--all-users",
            action="store_true",
            help=(
                "Assign observations to all registered users. Cannot be used if users"
                " are explicitly given."
            ),
        )
        parser.add_argument(
            "users",
            nargs="*",
            help=(
                "Assign the pending observations to the given GitHub usernames. Cannot"
                " be used with --all-users."
            ),
        )

    def handle(self, *args, **options):
        if options["all_users"] == (len(options["users"]) > 0):
            raise CommandError("One of either --all-users or users may be supplied.")
        verbose = options["verbosity"] > 1
        # exclude accounts that weren't registered via social-auth (i.e. GitHub)
        eligible_validators = User.objects.annotate(
            n_social=Count("social_auth")
        ).filter(n_social__gt=0)
        if options["all_users"]:
            users = eligible_validators
        else:
            users = eligible_validators.filter(username__in=options["users"])
            # raise an error if any username isn't found
            if users.count() != len(options["users"]):
                invalid_usernames = set(options["users"]) - set(
                    users.values_list("username", flat=True)
                )
                raise CommandError(
                    f"Usernames not found: {', '.join(invalid_usernames)}."
                )

        obs_pending = Observation.objects.filter(
            data_quality=Observation.ValidationState.NOT_VALIDATED,
            assigned_validator=None,
        )
        n_obs_pending = obs_pending.count()
        users_list: list[User] = (
            random.sample(list(users), n_obs_pending)
            if n_obs_pending < users.count()
            else list(users)
        )

        # limit the number of observation assignments if -n was supplied
        it_limit = (
            len(obs_pending)
            if options["num_obs"] is None
            else options["num_obs"] * len(users_list)
        )

        # keep track of the number of assigned observations
        assigned_counts: dict[str, int] = {user.username: 0 for user in users_list}

        # assign the observations
        for i, (obs, user) in enumerate(zip(obs_pending, cycle(users_list))):
            if i >= it_limit:
                break  # -n limit reached, stop assigning observations
            if verbose:
                self.stdout.write(f"Assigning {obs} to {user.username}.")
            if not options["dry_run"]:
                obs.assigned_validator = user
            assigned_counts[user.username] += 1

        # write updates to database
        if not options["dry_run"]:
            Observation.objects.bulk_update(obs_pending, ["assigned_validator"])
            msg_prefix = "Assigned"
        else:
            msg_prefix = "Would assign"

        # print summary
        self.stdout.write(
            self.style.SUCCESS(
                f"{msg_prefix} {sum([n for n in assigned_counts.values()])} pending"
                f" observations to {len(users)} users."
            )
        )
        if verbose:
            for username, n_assigned in assigned_counts.items():
                self.stdout.write(
                    self.style.SUCCESS(
                        f"{username}: {n_assigned} new observation assignments."
                    )
                )
