from django.core.management.base import BaseCommand
from django.db import transaction

from books.category_utils import normalize_category_name
from books.models import Category


def console_safe(value):
    return str(value).encode("ascii", errors="backslashreplace").decode("ascii")


class Command(BaseCommand):
    help = "Normalize category display names and merge duplicate category records."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show planned changes without updating the database.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        planned_changes = []

        with transaction.atomic():
            for category in Category.objects.order_by("id"):
                normalized_name = normalize_category_name(category.name)
                if normalized_name == category.name:
                    continue

                target = Category.objects.filter(name=normalized_name).exclude(pk=category.pk).first()
                book_count = category.books.count()

                if target:
                    planned_changes.append(
                        f"Merge '{console_safe(category.name)}' -> '{console_safe(target.name)}' ({book_count} books)"
                    )
                    if not dry_run:
                        category.books.update(category=target)
                        category.delete()
                else:
                    planned_changes.append(
                        f"Rename '{console_safe(category.name)}' -> '{console_safe(normalized_name)}'"
                    )
                    if not dry_run:
                        category.name = normalized_name
                        category.save(update_fields=["name"])

            if dry_run:
                transaction.set_rollback(True)

        if not planned_changes:
            self.stdout.write(self.style.SUCCESS("Categories are already normalized."))
            return

        for change in planned_changes:
            self.stdout.write(change)

        suffix = " (dry run)" if dry_run else ""
        self.stdout.write(self.style.SUCCESS(f"Normalized {len(planned_changes)} categories{suffix}."))
