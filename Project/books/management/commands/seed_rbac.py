from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

from books.rbac import GROUP_PERMS


class Command(BaseCommand):
    help = "Create default RBAC groups and assign permissions."

    def handle(self, *args, **options):
        Group.objects.filter(name="Accountant").delete()
        for group_name, perms in GROUP_PERMS.items():
            group, created = Group.objects.get_or_create(name=group_name)
            permissions = Permission.objects.filter(
                content_type__app_label__in={p.split(".")[0] for p in perms},
                codename__in=[p.split(".")[1] for p in perms],
            )
            group.permissions.set(permissions)
            status = "created" if created else "updated"
            self.stdout.write(self.style.SUCCESS(f"{status} group: {group_name}"))
