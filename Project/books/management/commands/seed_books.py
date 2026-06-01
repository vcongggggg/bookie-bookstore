"""
Lay du lieu sach mau tu Open Library API (API cong khai, mien phi) va luu vao database.
Chay: python manage.py seed_books
      python manage.py seed_books --limit 24 --subjects fiction,programming,science
"""
import json
import random
import time
import urllib.error
import urllib.request

from django.core.management.base import BaseCommand

from books.category_utils import normalize_category_name
from books.models import Book, Category


def fetch_url(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "SmartBookstore/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def get_cover_url(cover_id):
    if not cover_id:
        return ""
    return f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg"


def fetch_description(work_key):
    """Lay mo ta sach tu Open Library Works API.
    work_key: vi du '/works/OL66554W'
    """
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

        # Fallback: subjects
        subjects = data.get("subjects", [])
        if subjects:
            subject_list = [s for s in subjects[:6] if all(ord(c) < 128 or c.isalpha() for c in s)]
            if subject_list:
                return "Topics: " + ", ".join(subject_list) + "."
    except Exception:
        pass
    return ""


class Command(BaseCommand):
    help = "Them sach mau tu Open Library API vao database (bao gom mo ta chi tiet)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=24,
            help="So sach toi da moi the loai (mac dinh 24)",
        )
        parser.add_argument(
            "--subjects",
            type=str,
            default="fiction,programming,science,romance,mystery",
            help="Cac the loai cach nhau boi dau phay",
        )
        parser.add_argument(
            "--offset",
            type=int,
            default=0,
            help="Vi tri bat dau (de lay trang tiep theo, thu offset=30, 60...)",
        )
        parser.add_argument(
            "--no-desc",
            action="store_true",
            help="Bo qua viec lay mo ta (nhanh hon nhung khong co description)",
        )

    def handle(self, *args, **options):
        limit = options["limit"]
        offset = max(0, options["offset"])
        subjects = [s.strip() for s in options["subjects"].split(",") if s.strip()]
        skip_desc = options["no_desc"]
        created_books = 0

        for subject in subjects:
            url = f"https://openlibrary.org/subjects/{subject}.json?limit={limit}&offset={offset}"
            self.stdout.write(f"\n[FETCH] {subject}...")
            try:
                data = fetch_url(url)
            except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as e:
                self.stdout.write(self.style.WARNING(f"  SKIP {subject}: {e}"))
                continue

            name = normalize_category_name(data.get("name") or subject)
            category, _ = Category.objects.get_or_create(name=name)
            works = data.get("works") or []

            for i, w in enumerate(works):
                title = (w.get("title") or "").strip()
                if not title or len(title) > 255:
                    continue
                authors = w.get("authors") or []
                author = (authors[0].get("name") or "Unknown").strip() if authors else "Unknown"
                if len(author) > 255:
                    author = author[:252] + "..."
                cover_id = w.get("cover_id")
                cover_image = get_cover_url(cover_id) if cover_id else ""
                year = w.get("first_publish_year")
                if year and (year < 1000 or year > 2100):
                    year = None

                if Book.objects.filter(title=title, author=author).exists():
                    continue

                # Lay mo ta tu Works API
                description = ""
                work_key = w.get("key", "")
                if not skip_desc and work_key:
                    safe_title = title[:50].encode("ascii", errors="replace").decode("ascii")
                    self.stdout.write(f"  [{i+1}/{len(works)}] {safe_title}... ", ending="")
                    description = fetch_description(work_key)
                    if description:
                        self.stdout.write(self.style.SUCCESS(f"OK ({len(description)} chars)"))
                    else:
                        self.stdout.write(self.style.WARNING("no description"))
                    time.sleep(0.2)

                if not description:
                    description = f"Sach hay ve {name}. Tac gia: {author}."

                price = random.randint(50, 250) * 1000  # 50k - 250k VND
                Book.objects.create(
                    title=title,
                    author=author,
                    description=description,
                    price=price,
                    category=category,
                    published_year=year,
                    cover_image=cover_image or "",
                )
                created_books += 1

        self.stdout.write(self.style.SUCCESS(f"\n[DONE] Added {created_books} books with descriptions."))
