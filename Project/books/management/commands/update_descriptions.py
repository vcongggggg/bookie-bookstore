"""
Cap nhat mo ta sach tu Open Library API cho cac sach da co trong database.
Chay: python manage.py update_descriptions
      python manage.py update_descriptions --force  (ghi de ca sach da co mo ta)
"""
import json
import re
import time
import urllib.error
import urllib.request

from django.core.management.base import BaseCommand

from books.models import Book


def fetch_url(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "Bookie/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def search_work(title, author):
    """Tim sach tren Open Library bang tieu de va tac gia, tra ve (work_key, search_desc)."""
    # Try 1: search by title + author
    for q in [f"{title} {author}", title]:
        try:
            q_encoded = urllib.request.quote(q.strip())
            url = f"https://openlibrary.org/search.json?q={q_encoded}&limit=3&fields=key,title,author_name,first_sentence"
            data = fetch_url(url, timeout=10)
            docs = data.get("docs", [])
            for doc in docs:
                key = doc.get("key", "")
                # Extract first_sentence from search results as backup
                fs = doc.get("first_sentence", [])
                search_desc = fs[0] if isinstance(fs, list) and fs else ""
                if key:
                    return key, search_desc
        except Exception:
            pass
        time.sleep(0.2)
    return "", ""


def fetch_description_from_work(work_key):
    """Lay mo ta sach tu Open Library Works API."""
    try:
        url = f"https://openlibrary.org{work_key}.json"
        data = fetch_url(url, timeout=10)
        desc = data.get("description")
        if isinstance(desc, dict):
            desc = desc.get("value", "")
        if isinstance(desc, str) and desc.strip():
            return desc.strip()

        # Fallback: first_sentence
        first_sentence = data.get("first_sentence")
        if isinstance(first_sentence, dict):
            first_sentence = first_sentence.get("value", "")
        if isinstance(first_sentence, str) and first_sentence.strip():
            return first_sentence.strip()

        # Fallback: excerpts
        excerpts = data.get("excerpts", [])
        if excerpts:
            excerpt_text = excerpts[0].get("excerpt", "")
            if excerpt_text:
                return excerpt_text.strip()

        # Fallback: subjects
        subjects = data.get("subjects", [])
        if subjects:
            subject_list = [s for s in subjects[:8] if all(ord(c) < 128 or c.isalpha() for c in s)]
            if subject_list:
                return "Topics: " + ", ".join(subject_list[:6]) + "."
    except Exception:
        pass
    return ""


def is_placeholder_description(desc):
    """Kiem tra xem mo ta co phai la mo ta gia (placeholder) khong."""
    if not desc:
        return True
    placeholder_patterns = [
        r"^S.ch hay v. .+\. T.c gi.: .+\.$",
    ]
    for pattern in placeholder_patterns:
        if re.match(pattern, desc.strip()):
            return True
    return False


class Command(BaseCommand):
    help = "Cap nhat mo ta sach tu Open Library API cho sach da co trong database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Ghi de mo ta ca cho sach da co mo ta that",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Gioi han so sach can cap nhat (0 = tat ca)",
        )

    def handle(self, *args, **options):
        force = options["force"]
        limit = options["limit"]

        books = Book.objects.all().order_by("pk")
        if limit > 0:
            books = books[:limit]

        total = books.count()
        updated = 0
        skipped = 0
        failed = 0

        self.stdout.write(f"\n[START] Updating descriptions for {total} books...\n")

        for i, book in enumerate(books, 1):
            # Skip books that already have real descriptions
            safe_title = book.title[:50].encode('ascii', errors='replace').decode('ascii')
            if not force and not is_placeholder_description(book.description):
                self.stdout.write(f"  [{i}/{total}] {safe_title}... " + self.style.WARNING("SKIP (has desc)"))
                skipped += 1
                continue

            self.stdout.write(f"  [{i}/{total}] {safe_title}... ", ending="")

            # Step 1: Search for the work
            work_key, search_desc = search_work(book.title, book.author)
            if not work_key:
                self.stdout.write(self.style.WARNING("NOT FOUND on Open Library"))
                failed += 1
                time.sleep(0.3)
                continue

            # Step 2: Fetch description from Works API
            time.sleep(0.3)  # Rate limit
            description = fetch_description_from_work(work_key)

            # Fallback: use first_sentence from search results
            if not description and search_desc:
                description = search_desc

            if description:
                book.description = description
                book.save(update_fields=["description"])
                updated += 1
                desc_preview = description[:60].replace("\n", " ")
                safe_preview = desc_preview.encode("ascii", errors="replace").decode("ascii")
                self.stdout.write(self.style.SUCCESS(f'OK "{safe_preview}..."'))
            else:
                failed += 1
                self.stdout.write(self.style.WARNING("NO DESCRIPTION"))

            # Rate limit
            time.sleep(0.2)

        self.stdout.write(self.style.SUCCESS(
            f"\n[DONE] Updated: {updated} | Skipped: {skipped} | Failed: {failed}"
        ))
