import requests
from django.core.management.base import BaseCommand

from books.category_utils import normalize_category_name
from books.models import Book, Category


class Command(BaseCommand):
    help = "Seeds digital books from Project Gutenberg"

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS("Dang bat dau keo sach tu Project Gutenberg..."))

        category, _ = Category.objects.get_or_create(name=normalize_category_name("Kinh điển"))
        api_url = "https://gutendex.com/books/?languages=en&topic=fiction"

        try:
            response = requests.get(api_url, timeout=20)
            data = response.json()
            books_data = data.get("results", [])[:10]

            for b_data in books_data:
                title = b_data.get("title")
                author = b_data["authors"][0]["name"] if b_data["authors"] else "Unknown"
                gutenberg_id = b_data.get("id")

                self.stdout.write(f"Dang xu ly: {title}...")

                if Book.objects.filter(title=title, author=author).exists():
                    self.stdout.write(self.style.WARNING(f"Sach '{title}' da ton tai. Bo qua."))
                    continue

                text_url = b_data["formats"].get("text/plain; charset=utf-8") or b_data["formats"].get("text/plain")

                if not text_url:
                    self.stdout.write(self.style.ERROR(f"Khong tim thay ban text cho {title}"))
                    continue

                try:
                    content_res = requests.get(text_url, timeout=15)
                    content_text = content_res.text
                    cover_url = b_data["formats"].get("image/jpeg")

                    Book.objects.create(
                        title=title,
                        author=author,
                        description=f"Một tác phẩm kinh điển từ Project Gutenberg (ID: {gutenberg_id}).",
                        price=0.00,
                        category=category,
                        is_digital=True,
                        content_text=content_text,
                        cover_image=cover_url or "",
                        stock=999,
                    )
                    self.stdout.write(self.style.SUCCESS(f"Da them thanh cong: {title}"))

                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Loi khi tai noi dung {title}: {str(e)}"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Loi khi goi API Gutendex: {str(e)}"))

        self.stdout.write(self.style.SUCCESS("--- Hoan tat qua trinh seed du lieu ---"))
