from django.contrib.auth import get_user_model
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

User = get_user_model()


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self) -> str:
        return self.name


class Book(models.Model):
    title = models.CharField(max_length=255)
    author = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name="books")
    published_year = models.PositiveIntegerField(blank=True, null=True)
    num_pages = models.PositiveIntegerField(blank=True, null=True)
    cover_image = models.URLField(blank=True)
    stock = models.PositiveIntegerField(default=100, help_text="Số lượng tồn kho")
    
    # New fields for E-reader
    is_digital = models.BooleanField(default=False, help_text="Có hỗ trợ đọc trực tuyến không")
    content_text = models.TextField(blank=True, help_text="Nội dung sách (Text)")
    content_html = models.TextField(blank=True, help_text="Nội dung sách dạng HTML đã lọc, có thể chứa ảnh minh họa")
    
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self) -> str:
        return self.title

    @property
    def in_stock(self):
        return self.stock > 0


class ReadingProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reading_progress")
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="read_by_users")
    last_page = models.PositiveIntegerField(default=1)
    last_read_at = models.DateTimeField(auto_now=True)
    is_finished = models.BooleanField(default=False)

    class Meta:
        unique_together = ("user", "book")

    def __str__(self) -> str:
        return f"{self.user.username} reading {self.book.title}"


class Wishlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="wishlist_items")
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="wishlist_users")
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "book")
        ordering = ["-added_at"]

    def __str__(self) -> str:
        return f"{self.user} - {self.book}"


class Coupon(models.Model):
    DISCOUNT_TYPE_CHOICES = [
        ("percent", "Phần trăm (%)"),
        ("fixed", "Số tiền cố định (₫)"),
    ]
    code = models.CharField(max_length=50, unique=True)
    discount_type = models.CharField(max_length=10, choices=DISCOUNT_TYPE_CHOICES, default="percent")
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Giá trị đơn hàng tối thiểu")
    max_uses = models.PositiveIntegerField(default=100, help_text="Số lần sử dụng tối đa")
    used_count = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)
    valid_from = models.DateTimeField(default=timezone.now)
    valid_to = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        if self.discount_type == "percent":
            return f"{self.code} (-{self.discount_value}%)"
        return f"{self.code} (-{self.discount_value:,.0f}₫)"

    @property
    def is_valid(self):
        now = timezone.now()
        return self.active and self.used_count < self.max_uses and self.valid_from <= now <= self.valid_to

    def apply_discount(self, total):
        if self.discount_type == "percent":
            discount = total * self.discount_value / 100
        else:
            discount = self.discount_value
        return max(total - discount, 0)


class Order(models.Model):
    STATUS_CHOICES = [
        ("pending", "Chờ xác nhận"),
        ("confirmed", "Đã xác nhận"),
        ("packing", "Đang đóng gói"),
        ("shipping", "Đang giao hàng"),
        ("delivered", "Đã giao"),
        ("cancelled", "Đã hủy"),
    ]
    PAYMENT_STATUS_CHOICES = [
        ("pending", "Chờ thanh toán"),
        ("paid", "Đã thanh toán"),
        ("failed", "Thanh toán thất bại"),
        ("refunded", "Đã hoàn tiền"),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="orders")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    payment_method = models.CharField(max_length=20, default="cod", choices=[("cod", "COD"), ("vnpay", "VNPay"), ("momo", "Momo")])
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default="pending")
    paid_at = models.DateTimeField(null=True, blank=True)
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    payment_reference = models.CharField(max_length=100, blank=True, null=True)
    idempotency_key = models.CharField(max_length=100, blank=True, null=True, unique=True)
    coupon = models.ForeignKey(Coupon, on_delete=models.SET_NULL, null=True, blank=True, related_name="orders")
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    note = models.TextField(blank=True, help_text="Ghi chú đơn hàng")
    shipping_address = models.TextField(blank=True, help_text="Địa chỉ giao hàng")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Order #{self.pk} by {self.user}"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["transaction_id"],
                condition=models.Q(transaction_id__isnull=False) & ~models.Q(transaction_id=""),
                name="uniq_order_transaction_id_not_blank",
            )
        ]

    @property
    def subtotal(self):
        return sum(item.price * item.quantity for item in self.items.all())

    @property
    def total(self):
        return max(self.subtotal - self.discount_amount, 0)

    @property
    def status_display_vi(self):
        return dict(self.STATUS_CHOICES).get(self.status, self.status)

    @property
    def status_progress(self):
        """Return progress percentage for the status timeline."""
        progress_map = {
            "pending": 10,
            "confirmed": 30,
            "packing": 50,
            "shipping": 75,
            "delivered": 100,
            "cancelled": 0,
        }
        return progress_map.get(self.status, 0)


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="order_items")
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    is_digital_purchase = models.BooleanField(default=False, help_text="Đánh dấu nếu đây là đơn mua bản E-book")

    def __str__(self) -> str:
        return f"{self.book} x {self.quantity}"

    @property
    def subtotal(self):
        return self.price * self.quantity


class Rating(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ratings")
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="ratings")
    score = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "book")

    def __str__(self) -> str:
        return f"{self.book} rated {self.score} by {self.user}"


class AdminAuditLog(models.Model):
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="admin_audit_logs")
    action = models.CharField(max_length=80)
    target_type = models.CharField(max_length=80)
    target_id = models.CharField(max_length=64, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.action} by {self.actor or 'system'}"
