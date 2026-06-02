import json
import io
from datetime import timedelta
from unittest.mock import patch

import requests
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, Client
from django.test.utils import override_settings
from django.urls import reverse
from django.utils import timezone
from books.models import Book, Category, Coupon, Order, OrderItem, ReadingProgress, Wishlist
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from books.category_utils import normalize_category_name
from books.chatbot import BookieChatbot
from books.ollama_client import OllamaError
from books.views import _split_reader_pages

User = get_user_model()


class FakeChatbot:
    def get_response(self, user_message, history, last_books):
        return {"text": "ok", "type": "text"}

    def get_catalog_response(self, user_message):
        return None

    def prepare_stream_context(self, user_message):
        return []

    def build_prompt(self, user_message, history, found_books):
        return "prompt"

    @property
    def _client(self):
        class Client:
            def stream_generate(self, prompt):
                yield "ok"

        return Client()


class FakeBrokenStreamChatbot(FakeChatbot):
    @property
    def _client(self):
        class Client:
            def stream_generate(self, prompt):
                if False:
                    yield ""
                raise OllamaError("Ollama timeout")

        return Client()


class FakeLLMClient:
    def generate(self, prompt):
        raise AssertionError("Catalog searches must not call the LLM")


class BasicFlowTest(TestCase):
    def setUp(self):
        cache.clear()
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

    def test_book_detail_includes_book_structured_data(self):
        response = self.client.get(reverse("book_detail", args=[self.book.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'application/ld+json')
        self.assertContains(response, '"@type": "Book"')
        self.assertContains(response, self.book.title)
        self.assertContains(response, '"priceCurrency": "VND"')

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
        progress = ReadingProgress.objects.get(user=self.user, book=self.book)
        self.assertEqual(progress.last_page, 2)
        self.assertTrue(progress.is_finished)

    def test_reader_splits_long_plain_text_into_multiple_pages(self):
        long_text = " ".join(["Django reader content"] * 260)

        pages = _split_reader_pages(long_text, max_chars=600)

        self.assertGreater(len(pages), 1)
        self.assertTrue(all(len(page) <= 650 for page in pages))

    def test_reader_context_uses_split_pages_for_long_ebook(self):
        self.book.is_digital = True
        self.book.content_text = " ".join(["Crime and Punishment"] * 260)
        self.book.price = 0
        self.book.save(update_fields=["is_digital", "content_text", "price"])
        self.client.force_login(self.user)

        response = self.client.get(reverse("read_book", args=[self.book.id]))

        self.assertEqual(response.status_code, 200)
        self.assertGreater(response.context["total_pages"], 1)
        self.assertContains(response, "body.reader-mode")
        self.assertContains(response, "reader-panel")

    def test_digital_book_detail_shows_read_button(self):
        self.book.is_digital = True
        self.book.content_text = "Trang 1"
        self.book.price = 0
        self.book.save(update_fields=["is_digital", "content_text", "price"])

        response = self.client.get(reverse("book_detail", args=[self.book.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("read_book", args=[self.book.id]))
        self.assertContains(response, "Đọc online")
        self.assertNotContains(response, "Mua E-book")

    def test_ebook_list_only_shows_digital_books(self):
        ebook = Book.objects.create(
            title="Python Online Reader",
            author="Bookie",
            price=0,
            category=self.category,
            is_digital=True,
            content_text="Trang 1",
        )

        response = self.client.get(reverse("ebook_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, ebook.title)
        self.assertContains(response, reverse("read_book", args=[ebook.pk]))
        self.assertNotContains(response, self.book.title)

    def test_ebook_list_does_not_show_prices_or_purchase_actions(self):
        ebook = Book.objects.create(
            title="Paid Price Physical Book With Online Reader",
            author="Bookie",
            price=120000,
            category=self.category,
            is_digital=True,
            content_text="Trang 1",
        )

        response = self.client.get(reverse("ebook_list"))

        self.assertContains(response, ebook.title)
        self.assertContains(response, "Đọc online")
        self.assertNotContains(response, "120000")
        self.assertNotContains(response, "Mua E-book")
        self.assertNotContains(response, "Đọc thử")

    def test_navbar_links_to_ebook_list(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("ebook_list"))
        self.assertContains(response, "Đọc sách online")

    def test_reader_redirects_for_non_digital_book(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("read_book", args=[self.book.id]))
        self.assertRedirects(response, reverse("book_detail", args=[self.book.id]))

    def test_online_reader_is_free_even_when_physical_book_has_price(self):
        self.book.is_digital = True
        self.book.content_text = "\n\n".join([f"Trang {i} " + ("noi dung " * 180) for i in range(1, 13)])
        self.book.price = 100
        self.book.save(update_fields=["is_digital", "content_text", "price"])

        response = self.client.get(reverse("read_book", args=[self.book.id]))
        self.assertEqual(response.status_code, 200)
        self.assertGreater(response.context["total_pages"], 5)
        self.assertFalse(response.context["can_save_progress"])
        self.assertNotContains(response, "Mua E-book")
        self.assertNotContains(response, "Đọc thử")

    def test_digital_format_cannot_be_added_to_cart(self):
        self.book.is_digital = True
        self.book.content_text = "Trang 1"
        self.book.stock = 10
        self.book.save(update_fields=["is_digital", "content_text", "stock"])
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("add_to_cart", args=[self.book.id]),
            data={"format": "digital", "quantity": "5"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertNotIn(f"{self.book.id}_digital", self.client.session.get("cart", {}))
        self.assertEqual(OrderItem.objects.count(), 0)
        self.book.refresh_from_db()
        self.assertEqual(self.book.stock, 10)

    def test_ajax_add_to_cart_returns_count_and_caps_at_stock(self):
        response = self.client.post(
            reverse("add_to_cart", args=[self.book.id]),
            data={"quantity": "50"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["cart_count"], self.book.stock)
        self.assertEqual(self.client.session["cart"][f"{self.book.id}_physical"], self.book.stock)

    def test_ajax_remove_from_cart_updates_count(self):
        self.client.post(
            reverse("add_to_cart", args=[self.book.id]),
            data={"quantity": "2"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        response = self.client.get(
            reverse("remove_from_cart", args=[f"{self.book.id}_physical"]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["cart_count"], 0)
        self.assertNotIn(f"{self.book.id}_physical", self.client.session.get("cart", {}))

    def test_ajax_wishlist_add_and_remove_updates_count(self):
        self.client.force_login(self.user)

        add_response = self.client.post(
            reverse("wishlist_add", args=[self.book.id]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(add_response.status_code, 200)
        self.assertEqual(add_response.json()["action"], "added")
        self.assertEqual(add_response.json()["wishlist_count"], 1)
        self.assertTrue(Wishlist.objects.filter(user=self.user, book=self.book).exists())

        remove_response = self.client.post(
            reverse("wishlist_remove", args=[self.book.id]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(remove_response.status_code, 200)
        self.assertEqual(remove_response.json()["action"], "removed")
        self.assertEqual(remove_response.json()["wishlist_count"], 0)
        self.assertFalse(Wishlist.objects.filter(user=self.user, book=self.book).exists())

    def test_physical_checkout_decreases_stock_and_uses_requested_quantity(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("add_to_cart", args=[self.book.id]),
            data={"quantity": "3"},
        )
        self.assertEqual(response.status_code, 302)

        response = self.client.post(
            reverse("checkout"),
            data={
                "shipping_address": "123 Test Street",
                "note": "",
                "coupon_code": "",
                "payment_method": "cod",
            },
        )
        self.assertEqual(response.status_code, 302)
        item = OrderItem.objects.get(book=self.book)
        self.assertEqual(item.quantity, 3)
        self.assertFalse(item.is_digital_purchase)
        self.book.refresh_from_db()
        self.assertEqual(self.book.stock, 7)

    def test_valid_coupon_reduces_order_total_and_increments_usage(self):
        coupon = Coupon.objects.create(
            code="SAVE10",
            discount_type="percent",
            discount_value=10,
            min_order_amount=0,
            max_uses=5,
            valid_to=timezone.now() + timedelta(days=7),
        )
        self.client.force_login(self.user)
        self.client.post(reverse("add_to_cart", args=[self.book.id]), data={"quantity": "2"})

        response = self.client.post(
            reverse("checkout"),
            data={
                "shipping_address": "123 Test Street",
                "note": "",
                "coupon_code": "SAVE10",
                "payment_method": "cod",
            },
        )
        self.assertEqual(response.status_code, 302)
        order = Order.objects.get(user=self.user)
        self.assertEqual(order.coupon, coupon)
        self.assertEqual(float(order.discount_amount), 20.0)
        self.assertEqual(float(order.total), 180.0)
        coupon.refresh_from_db()
        self.assertEqual(coupon.used_count, 1)

    def test_invalid_coupon_does_not_block_checkout_or_discount_order(self):
        self.client.force_login(self.user)
        self.client.post(reverse("add_to_cart", args=[self.book.id]), data={"quantity": "1"})

        response = self.client.post(
            reverse("checkout"),
            data={
                "shipping_address": "123 Test Street",
                "note": "",
                "coupon_code": "NOPE",
                "payment_method": "cod",
            },
        )
        self.assertEqual(response.status_code, 302)
        order = Order.objects.get(user=self.user)
        self.assertIsNone(order.coupon)
        self.assertEqual(float(order.discount_amount), 0.0)
        self.assertEqual(float(order.total), 100.0)

    def test_dashboard_urls_reverse(self):
        names = [
            ("dashboard_users", []),
            ("dashboard_user_detail", [self.user.id]),
            ("dashboard_user_set_role", [self.user.id]),
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

    def test_reading_dna_supplies_chart_and_insight_context(self):
        order = Order.objects.create(user=self.user)
        OrderItem.objects.create(order=order, book=self.book, quantity=2, price=self.book.price)
        self.client.force_login(self.user)

        response = self.client.get(reverse("reading_dna"))
        self.assertEqual(response.status_code, 200)
        dna = response.context["dna"]
        self.assertIn("chart_categories", dna)
        self.assertIn("chart_trend", dna)
        self.assertTrue(dna["ai_insight"])
        self.assertTrue(dna["chart_categories"]["labels"].startswith("["))
        self.assertTrue(dna["chart_trend"]["values"].startswith("["))
        self.assertContains(response, "radarChart")

    def test_order_detail_links_invoice_pdf(self):
        order = Order.objects.create(user=self.user, shipping_address="123 Test Street")
        OrderItem.objects.create(order=order, book=self.book, quantity=2, price=self.book.price)
        self.client.force_login(self.user)

        response = self.client.get(reverse("order_detail", args=[order.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("order_invoice_pdf", args=[order.pk]))

    def test_reading_history_view(self):
        self.book.is_digital = True
        self.book.content_text = ("a" * 1000) + "\n\n" + ("b" * 1000)
        self.book.save(update_fields=["is_digital", "content_text"])

        ReadingProgress.objects.create(user=self.user, book=self.book, last_page=1)

        self.client.force_login(self.user)
        response = self.client.get(reverse("reading_history"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Lịch sử đọc sách")
        self.assertContains(response, self.book.title)
        self.assertContains(response, "Trang 1/2")
        self.assertContains(response, "50%")

    def test_order_invoice_pdf_download_requires_owner(self):
        order = Order.objects.create(user=self.user, shipping_address="123 Test Street")
        OrderItem.objects.create(order=order, book=self.book, quantity=2, price=self.book.price)
        other_user = User.objects.create_user(username="other", password="password123")

        self.client.force_login(other_user)
        response = self.client.get(reverse("order_invoice_pdf", args=[order.pk]))
        self.assertEqual(response.status_code, 404)

        self.client.force_login(self.user)
        response = self.client.get(reverse("order_invoice_pdf", args=[order.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("bookie-order-", response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_robots_txt_points_to_sitemap(self):
        response = self.client.get(reverse("robots_txt"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("text/plain"))
        self.assertContains(response, "Disallow: /dashboard/")
        self.assertContains(response, "Sitemap: http://testserver/sitemap.xml")

    def test_sitemap_lists_public_book_and_category_pages(self):
        response = self.client.get(reverse("sitemap"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"/books/{self.book.pk}/")
        self.assertContains(response, f"/categories/{self.category.pk}/")

    def test_chatbot_api_requires_csrf_token_when_middleware_enforces_it(self):
        csrf_client = Client(enforce_csrf_checks=True)
        response = csrf_client.post(
            reverse("api_chatbot"),
            data=json.dumps({"message": "hello"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)

    @override_settings(CHATBOT_RATE_LIMIT_REQUESTS=1, CHATBOT_RATE_LIMIT_WINDOW=60)
    def test_chatbot_api_rate_limits_repeated_requests(self):
        with patch("books.views._build_chatbot", return_value=FakeChatbot()) as build_bot:
            response = self.client.post(
                reverse("api_chatbot"),
                data=json.dumps({"message": "hello"}),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200)

            response = self.client.post(
                reverse("api_chatbot"),
                data=json.dumps({"message": "hello again"}),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 429)
            self.assertIn("retry_after", response.json())
            self.assertEqual(build_bot.call_count, 1)

    @override_settings(CHATBOT_RATE_LIMIT_REQUESTS=1, CHATBOT_RATE_LIMIT_WINDOW=60)
    def test_chatbot_stream_uses_same_rate_limit(self):
        with patch("books.views._build_chatbot", return_value=FakeChatbot()):
            response = self.client.post(
                reverse("api_chatbot"),
                data=json.dumps({"message": "hello"}),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200)

        response = self.client.post(
            reverse("api_chatbot_stream"),
            data=json.dumps({"message": "stream please"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 429)

    def test_chatbot_stream_returns_fallback_when_ollama_fails(self):
        with patch("books.views._build_chatbot", return_value=FakeBrokenStreamChatbot()):
            response = self.client.post(
                reverse("api_chatbot_stream"),
                data=json.dumps({"message": "hello"}),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        body = b"".join(response.streaming_content).decode("utf-8")
        self.assertIn("Bookie", body)
        self.assertIn('"type": "final"', body)

    def test_chatbot_catalog_search_returns_database_books_before_llm(self):
        programming = Category.objects.create(name="Lập trình")
        python_book = Book.objects.create(
            title="Python Web",
            author="Bookie",
            price=150000,
            category=programming,
            description="Sách thực hành Python và Django.",
        )
        bot = BookieChatbot(user=self.user, client=FakeLLMClient(), max_turns=3)

        response = bot.get_response("sách hay về python", [], None)

        self.assertEqual(response["type"], "books")
        self.assertEqual(response["books"][0]["id"], python_book.id)
        self.assertIn("150,000", response["books"][0]["price"])

    def test_chatbot_catalog_search_does_not_invent_missing_books(self):
        Book.objects.create(
            title="A Long Journey",
            author="Bookie",
            price=120000,
            category=self.category,
            description="A long classic adventure.",
        )
        bot = BookieChatbot(user=self.user, client=FakeLLMClient(), max_turns=3)

        response = bot.get_response("có sách nào hay về khủng long ko", [], None)

        self.assertEqual(response["type"], "text")
        self.assertIn("chưa tìm thấy", response["text"])
        self.assertNotIn("Khủng Long Trên Mặt Trăng", response["text"])

    def test_chatbot_stream_uses_catalog_response_for_book_search(self):
        programming = Category.objects.create(name="Lập trình")
        Book.objects.create(
            title="Python Web",
            author="Bookie",
            price=150000,
            category=programming,
            description="Sách thực hành Python và Django.",
        )
        bot = BookieChatbot(user=self.user, client=FakeLLMClient(), max_turns=3)

        with patch("books.views._build_chatbot", return_value=bot):
            response = self.client.post(
                reverse("api_chatbot_stream"),
                data=json.dumps({"message": "sách hay về python"}),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        body = b"".join(response.streaming_content).decode("utf-8")
        self.assertIn("Python Web", body)
        self.assertIn('"type": "books"', body)

    def test_profile_change_password_updates_login_credentials(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("profile_change_password"),
            data={
                "old_password": "password123",
                "new_password1": "new-password-456",
                "new_password2": "new-password-456",
            },
        )
        self.assertRedirects(response, reverse("profile"))
        self.client.logout()
        self.assertTrue(self.client.login(username="testuser", password="new-password-456"))


class CategoryNormalizationTest(TestCase):
    def test_normalize_category_name_uses_vietnamese_display_names(self):
        cases = {
            "fiction": "Văn học",
            "Programming": "Lập trình",
            "science": "Khoa học",
            "romance": "Lãng mạn",
            "mystery": "Trinh thám",
            "Kinh điển": "Kinh điển",
            "  custom_topic  ": "Custom Topic",
        }

        for raw_name, expected_name in cases.items():
            with self.subTest(raw_name=raw_name):
                self.assertEqual(normalize_category_name(raw_name), expected_name)

    def test_normalize_categories_command_renames_and_merges_existing_data(self):
        old_fiction = Category.objects.create(name="fiction")
        existing_vietnamese = Category.objects.create(name="Văn học")
        programming = Category.objects.create(name="programming")
        fiction_book = Book.objects.create(
            title="Old Fiction",
            author="Author",
            price=100,
            category=old_fiction,
        )
        existing_book = Book.objects.create(
            title="Existing Fiction",
            author="Author",
            price=100,
            category=existing_vietnamese,
        )
        programming_book = Book.objects.create(
            title="Code Book",
            author="Author",
            price=100,
            category=programming,
        )

        call_command("normalize_categories")

        self.assertFalse(Category.objects.filter(name="fiction").exists())
        self.assertFalse(Category.objects.filter(name="programming").exists())
        self.assertTrue(Category.objects.filter(name="Lập trình").exists())
        fiction_book.refresh_from_db()
        existing_book.refresh_from_db()
        programming_book.refresh_from_db()
        self.assertEqual(fiction_book.category.name, "Văn học")
        self.assertEqual(existing_book.category.name, "Văn học")
        self.assertEqual(programming_book.category.name, "Lập trình")


class SeedReaderContentCommandTest(TestCase):
    @patch("books.management.commands.seed_reader_content.requests.get")
    def test_seed_reader_content_handles_gutendex_timeout(self, mock_get):
        mock_get.side_effect = requests.Timeout("read timeout")
        output = io.StringIO()

        call_command(
            "seed_reader_content",
            timeout=5,
            retries=1,
            stdout=output,
        )

        self.assertIn("Gutendex dang cham hoac loi mang", output.getvalue())
        self.assertEqual(Book.objects.count(), 0)
        self.assertTrue(Category.objects.filter(name="Kinh điển").exists())


class RBACTest(TestCase):
    def setUp(self):
        call_command("seed_rbac")
        self.client = Client()
        self.customer = User.objects.create_user(username="customer", password="password123")
        self.manager = User.objects.create_user(username="manager", password="password123", is_staff=True)
        self.manager.groups.add(Group.objects.get(name="Manager"))
        self.support = User.objects.create_user(username="support", password="password123", is_staff=True)
        self.support.groups.add(Group.objects.get(name="Support"))
        self.admin = User.objects.create_superuser(username="admin_role", password="password123")

    def test_seed_rbac_uses_five_roles_without_accountant(self):
        self.assertTrue(Group.objects.filter(name="Staff").exists())
        self.assertTrue(Group.objects.filter(name="Manager").exists())
        self.assertTrue(Group.objects.filter(name="Support").exists())
        self.assertTrue(Group.objects.filter(name="Admin").exists())
        self.assertFalse(Group.objects.filter(name="Accountant").exists())

    def test_customer_cannot_access_dashboard(self):
        self.client.force_login(self.customer)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_manager_can_manage_books_but_not_users(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse("dashboard_books"))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse("dashboard_users"))
        self.assertEqual(response.status_code, 302)

    def test_staff_can_view_core_dashboard_data_without_management_actions(self):
        staff = User.objects.create_user(username="staff", password="password123", is_staff=True)
        staff.groups.add(Group.objects.get(name="Staff"))
        self.client.force_login(staff)

        self.assertEqual(self.client.get(reverse("dashboard_books")).status_code, 200)
        self.assertEqual(self.client.get(reverse("dashboard_orders")).status_code, 200)
        self.assertEqual(self.client.get(reverse("dashboard_coupons")).status_code, 200)
        self.assertEqual(self.client.get(reverse("dashboard_users")).status_code, 200)
        self.assertEqual(self.client.get(reverse("dashboard_book_create")).status_code, 302)
        self.assertEqual(self.client.get(reverse("dashboard_coupon_create")).status_code, 302)

    def test_admin_can_view_user_profile_detail(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("dashboard_user_detail", args=[self.customer.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.customer.username)

    def test_support_can_view_orders_and_change_status(self):
        order = Order.objects.create(user=self.customer, shipping_address="123 Test Street")
        self.client.force_login(self.support)

        response = self.client.get(reverse("dashboard_orders"))
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            reverse("api_update_order_status", args=[order.pk]),
            data={"status": "confirmed"},
        )
        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, "confirmed")

    def test_admin_can_assign_customer_role(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("dashboard_user_set_role", args=[self.manager.pk]),
            data={"role": "Customer"},
        )
        self.assertEqual(response.status_code, 302)
        self.manager.refresh_from_db()
        self.assertFalse(self.manager.is_staff)
        self.assertFalse(self.manager.groups.filter(name__in=["Staff", "Manager", "Support", "Admin"]).exists())

    def test_admin_can_assign_manager_role(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("dashboard_user_set_role", args=[self.customer.pk]),
            data={"role": "Manager"},
        )
        self.assertEqual(response.status_code, 302)
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.is_staff)
        self.assertTrue(self.customer.groups.filter(name="Manager").exists())
