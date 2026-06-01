import sqlite3
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from books.category_utils import normalize_category_name
from books.models import Book, Category


class Command(BaseCommand):
    help = "Import books from a SQLite db.sqlite3 file into the current database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--sqlite-path",
            default=str(settings.BASE_DIR / "db.sqlite3"),
            help="Path to the source SQLite database. Default: BASE_DIR/db.sqlite3",
        )
        parser.add_argument(
            "--update-existing",
            action="store_true",
            help="Update existing books matched by title + author instead of only skipping duplicates.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show counts without writing to the current database.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        sqlite_path = Path(options["sqlite_path"])
        update_existing = options["update_existing"]
        dry_run = options["dry_run"]

        if not sqlite_path.exists():
            raise CommandError(f"SQLite file not found: {sqlite_path}")

        source_books, source_categories = self._read_source(sqlite_path)
        if not source_books:
            self.stdout.write(self.style.WARNING("No books found in source SQLite database."))
            return

        existing_keys = {
            self._dedupe_key(book.title, book.author): book
            for book in Book.objects.only("id", "title", "author")
        }
        seen_source_keys = set()
        created = 0
        updated = 0
        skipped_existing = 0
        skipped_source_duplicate = 0

        for row in source_books:
            key = self._dedupe_key(row["title"], row["author"])
            if key in seen_source_keys:
                skipped_source_duplicate += 1
                continue
            seen_source_keys.add(key)

            category_name = self._category_name(row, source_categories)
            category, _ = Category.objects.get_or_create(name=category_name)
            defaults = {
                "description": row["description"] or "",
                "price": Decimal(str(row["price"] or 0)),
                "category": category,
                "published_year": row["published_year"],
                "num_pages": row["num_pages"],
                "cover_image": row["cover_image"] or "",
                "stock": row["stock"] or 0,
                "is_digital": bool(row["is_digital"]),
                "content_text": row["content_text"] or "",
                "created_at": self._parse_created_at(row["created_at"]),
            }

            existing = existing_keys.get(key)
            if existing:
                if not update_existing:
                    skipped_existing += 1
                    continue
                for field, value in defaults.items():
                    setattr(existing, field, value)
                if not dry_run:
                    existing.save()
                updated += 1
                continue

            if not dry_run:
                book = Book.objects.create(
                    title=row["title"],
                    author=row["author"],
                    **defaults,
                )
                existing_keys[key] = book
            created += 1

        if dry_run:
            transaction.set_rollback(True)

        self.stdout.write(
            self.style.SUCCESS(
                "SQLite import finished"
                + (" (dry run)" if dry_run else "")
                + f": source={len(source_books)}, created={created}, updated={updated}, "
                f"skipped_existing={skipped_existing}, skipped_source_duplicate={skipped_source_duplicate}."
            )
        )

    def _read_source(self, sqlite_path):
        conn = sqlite3.connect(sqlite_path)
        conn.row_factory = sqlite3.Row
        try:
            categories = {
                row["id"]: row["name"]
                for row in conn.execute("SELECT id, name FROM books_category")
            }
            books = list(
                conn.execute(
                    """
                    SELECT
                        title,
                        author,
                        description,
                        price,
                        category_id,
                        published_year,
                        num_pages,
                        cover_image,
                        stock,
                        is_digital,
                        content_text,
                        created_at
                    FROM books_book
                    ORDER BY id
                    """
                )
            )
        finally:
            conn.close()
        return books, categories

    def _category_name(self, row, source_categories):
        raw_name = source_categories.get(row["category_id"]) or "Khác"
        return normalize_category_name(raw_name)

    def _dedupe_key(self, title, author):
        return (str(title or "").strip().casefold(), str(author or "").strip().casefold())

    def _parse_created_at(self, value):
        parsed = parse_datetime(str(value or ""))
        if not parsed:
            return timezone.now()
        if timezone.is_naive(parsed):
            return timezone.make_aware(parsed, timezone.get_current_timezone())
        return parsed
