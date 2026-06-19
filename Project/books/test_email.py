from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core import mail
from django.conf import settings
from books.models import Book, Category, Coupon, Order, OrderItem
from books.email_service import (
    send_welcome_email,
    send_order_confirmation_email,
    send_order_status_update_email,
    send_low_stock_alert_email
)

User = get_user_model()


class EmailIntegrationTestCase(TestCase):
    def setUp(self):
        # Clear outbox before each test
        mail.outbox = []
        
        # Create a category and book
        self.category = Category.objects.create(name="Fiction")
        self.book = Book.objects.create(
            title="Test Book",
            author="Author Name",
            price=200000,
            stock=15,
            category=self.category
        )
        
        # Create staff user for admin alerts
        self.staff_user = User.objects.create_user(
            username="adminstaff",
            email="staff@bookie.com",
            password="adminpassword",
            is_staff=True
        )
        
        # Create normal user
        self.user = User.objects.create_user(
            username="testuser",
            email="testuser@example.com",
            password="password123"
        )
        self.client = Client()

    def test_send_welcome_email_direct(self):
        """Test sending welcome email directly via email service."""
        send_welcome_email(self.user)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Chào mừng bạn đến với Bookie!", mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].to, [self.user.email])
        self.assertIn(self.user.username, mail.outbox[0].body)

    def test_send_order_confirmation_email_direct(self):
        """Test sending order confirmation email with attachment."""
        order = Order.objects.create(
            user=self.user,
            shipping_address="123 Street",
            payment_method="cod"
        )
        OrderItem.objects.create(
            order=order,
            book=self.book,
            quantity=1,
            price=200000
        )
        send_order_confirmation_email(order)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(f"Xác nhận đơn hàng #{order.pk}", mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].to, [self.user.email])
        # Check PDF attachment
        self.assertEqual(len(mail.outbox[0].attachments), 1)
        filename, content, mime = mail.outbox[0].attachments[0]
        self.assertEqual(filename, f"hoa-don-{order.pk}.pdf")
        self.assertEqual(mime, "application/pdf")

    def test_send_order_status_update_email_direct(self):
        """Test sending order status update email directly."""
        order = Order.objects.create(
            user=self.user,
            shipping_address="123 Street",
            status="confirmed",
            payment_method="cod"
        )
        send_order_status_update_email(order, "pending")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(f"Đơn hàng #{order.pk}", mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].to, [self.user.email])

    def test_send_low_stock_alert_email_direct(self):
        """Test sending low stock alert directly."""
        send_low_stock_alert_email([self.book])
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Cảnh báo tồn kho thấp", mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].to, [self.staff_user.email])

    def test_welcome_email_on_registration_view(self):
        """Test that register view triggers welcome email."""
        response = self.client.post(reverse("register"), {
            "username": "newuser",
            "email": "newuser@example.com",
            "password1": "Password123!",
            "password2": "Password123!"
        })
        self.assertEqual(response.status_code, 302)  # Redirects to home
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["newuser@example.com"])
        self.assertIn("Chào mừng", mail.outbox[0].subject)

    def test_checkout_cod_sends_email_and_alerts_low_stock(self):
        """Test checkout view triggers confirmation email and low stock alert if stock falls below threshold."""
        # Set stock to 11, purchase 2 books, remaining is 9 (< 10 threshold)
        self.book.stock = 11
        self.book.save()
        
        # Put book in cart
        session = self.client.session
        session["cart"] = {f"{self.book.pk}_physical": 2}
        session.save()
        
        self.client.login(username="testuser", password="password123")
        response = self.client.post(reverse("checkout"), {
            "shipping_address": "456 Avenue",
            "payment_method": "cod",
            "note": "Deliver in afternoon"
        })
        self.assertEqual(response.status_code, 302)
        
        # We expect 2 emails:
        # 1. Low stock alert for the book (stock went to 9)
        # 2. Order confirmation email for COD order
        self.assertEqual(len(mail.outbox), 2)
        
        subjects = [email.subject for email in mail.outbox]
        has_low_stock = any("Cảnh báo tồn kho thấp" in s for s in subjects)
        has_order_confirm = any("Xác nhận đơn hàng" in s for s in subjects)
        
        self.assertTrue(has_low_stock)
        self.assertTrue(has_order_confirm)

    def test_payment_confirm_sends_email_for_online_payment(self):
        """Test that confirming an online payment triggers order confirmation email."""
        order = Order.objects.create(
            user=self.user,
            shipping_address="123 Street",
            status="pending",
            payment_method="vnpay"
        )
        OrderItem.objects.create(
            order=order,
            book=self.book,
            quantity=1,
            price=200000
        )
        
        self.client.login(username="testuser", password="password123")
        response = self.client.post(reverse("payment_confirm", args=[order.pk]))
        self.assertEqual(response.status_code, 302)
        
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(f"Xác nhận đơn hàng #{order.pk}", mail.outbox[0].subject)

    def test_cancel_order_sends_status_update_email(self):
        """Test that cancelling an order triggers status update email."""
        order = Order.objects.create(
            user=self.user,
            shipping_address="123 Street",
            status="confirmed",
            payment_method="cod"
        )
        OrderItem.objects.create(
            order=order,
            book=self.book,
            quantity=1,
            price=200000
        )
        
        self.client.login(username="testuser", password="password123")
        response = self.client.post(reverse("cancel_order", args=[order.pk]))
        self.assertEqual(response.status_code, 302)
        
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Đã hủy", mail.outbox[0].body)

    def test_password_reset_email(self):
        """Test password reset flow triggers password reset email."""
        response = self.client.post(reverse("password_reset"), {
            "email": "testuser@example.com"
        })
        self.assertEqual(response.status_code, 302)
        
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["testuser@example.com"])
        self.assertIn("Đặt lại mật khẩu", mail.outbox[0].subject)
