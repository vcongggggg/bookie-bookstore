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
