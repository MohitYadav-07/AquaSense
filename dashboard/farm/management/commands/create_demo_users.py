import secrets

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from farm.models import Field


class Command(BaseCommand):
    help = "Create an admin and a demo farmer with random passwords (printed once) and assign unowned fields to the farmer."

    def handle(self, *args, **opts):
        User = get_user_model()
        made = []
        for name, staff in (("admin", True), ("farmer", False)):
            if User.objects.filter(username=name).exists():
                continue
            pw = secrets.token_urlsafe(9)
            User.objects.create_user(name, password=pw, is_staff=staff, is_superuser=staff)
            made.append((name, pw))
        farmer = User.objects.filter(username="farmer").first()
        if farmer:
            Field.objects.filter(owner_id__isnull=True).update(owner_id=farmer.id)
        if made:
            self.stdout.write("Created users (save these now, they are not shown again):")
            for n, p in made:
                self.stdout.write("  %s / %s" % (n, p))
        else:
            self.stdout.write("Demo users already exist.")
