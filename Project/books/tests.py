import json

from django.test import TestCase, Client
from django.urls import reverse
from books.models import Book, Category, Order
from django.contrib.auth import get_user_model

User = get_user_model()

class BasicFlowTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.category = Category.objects.create(name="IT")
        self.book = Book.objects.create(
            title="Django Pro",
            author="Copilot",
            price=100.0,
            category=self.category,
            stock=10
        )
        self.user = User.objects.create_user(username="testuser", password="password123")

    def test_home_page(self):
        """Kiểm tra trang chủ có hoạt động không."""
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)

    def test_book_detail(self):
        """Kiểm tra xem trang chi tiết sách có hiển thị đúng không."""
        response = self.client.get(reverse('book_detail', args=[self.book.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Django Pro")

    def test_reader_and_progress_api_for_digital_book(self):
        self.book.is_digital = True
        self.book.content_text = "Trang 1\n\nTrang 2"
        self.book.price = 0
        self.book.save(update_fields=["is_digital", "content_text", "price"])
        self.client.force_login(self.user)

        response = self.client.get(reverse("read_book", args=[self.book.id]))
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            reverse("api_save_reading_progress", args=[self.book.id]),
            data=json.dumps({"page": 2, "finished": True}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")

    def test_dashboard_urls_reverse(self):
        names = [
            ("dashboard_users", []),
            ("dashboard_books", []),
            ("dashboard_book_create", []),
            ("dashboard_book_edit", [self.book.id]),
            ("dashboard_book_delete", [self.book.id]),
            ("dashboard_coupons", []),
            ("dashboard_coupon_create", []),
            ("dashboard_coupon_edit", [1]),
            ("dashboard_coupon_delete", [1]),
            ("dashboard_orders", []),
            ("dashboard_audit_logs", []),
        ]
        for name, args in names:
            with self.subTest(name=name):
                self.assertTrue(reverse(name, args=args).startswith("/"))
