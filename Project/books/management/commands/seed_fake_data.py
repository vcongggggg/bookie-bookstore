from decimal import Decimal
from random import Random

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from books.category_utils import normalize_category_name
from books.models import (
    AdminAuditLog,
    Book,
    Category,
    Coupon,
    Order,
    OrderItem,
    Rating,
    ReadingProgress,
    Wishlist,
)


FAKE_USERS = [
    ("demo", "demo123", "demo@example.com", False, False),
    ("admin", "admin123", "admin@example.com", True, True),
    ("alice", "alice123", "alice@example.com", False, False),
    ("bob", "bob123", "bob@example.com", False, False),
    ("staff", "staff123", "staff@example.com", True, False),
]

FAKE_BOOKS = [
    ("Python Web Django", "Bookie Academy", "Lập trình", "Sách thực hành Python, Django, API và triển khai web.", 185000, 2026, 320),
    ("Clean Code Tiếng Việt", "Bookie Engineering", "Lập trình", "Các nguyên tắc viết code dễ đọc, dễ test và dễ bảo trì.", 165000, 2025, 280),
    ("Dữ liệu và Thuật toán", "Bookie Academy", "Lập trình", "Nhập môn cấu trúc dữ liệu, thuật toán tìm kiếm và sắp xếp.", 175000, 2024, 360),
    ("Vũ trụ trong tầm tay", "Nguyễn Minh Khoa", "Khoa học", "Hành trình khám phá thiên văn, vật lý và những câu hỏi lớn.", 142000, 2023, 240),
    ("Khủng long và Trái Đất cổ đại", "Lan Phương", "Khoa học", "Sách phổ thông về khủng long, hóa thạch và lịch sử sự sống.", 99000, 2022, 180),
    ("Cơ thể người kỳ diệu", "Bookie Science", "Khoa học", "Kiến thức nhập môn về sinh học, sức khỏe và cơ thể người.", 125000, 2024, 210),
    ("Án mạng trong thư viện", "Minh An", "Trinh thám", "Một vụ án bí ẩn bắt đầu từ căn phòng đọc sách lúc nửa đêm.", 132000, 2021, 260),
    ("Dấu vết cuối cùng", "Hạ Vũ", "Trinh thám", "Thám tử trẻ lần theo chuỗi manh mối bị che giấu nhiều năm.", 118000, 2020, 230),
    ("Mùa hè ở hiệu sách", "Mai Chi", "Lãng mạn", "Câu chuyện dịu dàng về tình yêu, sách cũ và những lá thư chưa gửi.", 109000, 2023, 220),
    ("Ngày em đọc mưa", "An Nhiên", "Lãng mạn", "Một tiểu thuyết nhẹ nhàng cho những độc giả thích cảm xúc chậm rãi.", 97000, 2022, 190),
    ("Những ngày xanh", "Bookie Classics", "Văn học", "Tập truyện ngắn về tuổi trẻ, gia đình và những lựa chọn đầu đời.", 88000, 2021, 200),
    ("Ebook Demo: Python căn bản", "Bookie Academy", "Kinh điển", "Ebook mẫu dùng để kiểm thử chức năng đọc trực tuyến.", 0, 2026, 90),
    ("Ebook Demo: Nghệ thuật đọc sách", "Bookie Editorial", "Kinh điển", "Ebook mẫu về phương pháp đọc, ghi chú và ứng dụng kiến thức.", 0, 2026, 80),
]


EBOOK_CONTENT = {
    "Ebook Demo: Python căn bản": (
        "Python là ngôn ngữ lập trình dễ đọc và phù hợp cho người mới bắt đầu.\n\n"
        "Bài 1: Biến, kiểu dữ liệu và câu lệnh điều kiện.\n\n"
        "Bài 2: Vòng lặp, hàm và module.\n\n"
        "Bài 3: Xây dựng ứng dụng web với Django và quản lý dữ liệu bằng ORM."
    ),
    "Ebook Demo: Nghệ thuật đọc sách": (
        "Đọc sách hiệu quả bắt đầu từ việc chọn đúng mục tiêu.\n\n"
        "Phần 1: Đọc lướt để nắm cấu trúc.\n\n"
        "Phần 2: Ghi chú các ý quan trọng và đặt câu hỏi.\n\n"
        "Phần 3: Biến kiến thức thành hành động nhỏ mỗi ngày."
    ),
}


class Command(BaseCommand):
    help = "Seed realistic fake data for local/demo environments."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset-demo",
            action="store_true",
            help="Delete demo orders, ratings, wishlist, progress and audit logs before seeding.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        rng = Random(20260601)
        User = get_user_model()

        call_command("seed_rbac", verbosity=0)

        if options["reset_demo"]:
            usernames = [item[0] for item in FAKE_USERS]
            users = User.objects.filter(username__in=usernames)
            Order.objects.filter(user__in=users).delete()
            Rating.objects.filter(user__in=users).delete()
            Wishlist.objects.filter(user__in=users).delete()
            ReadingProgress.objects.filter(user__in=users).delete()
            AdminAuditLog.objects.all().delete()

        categories = {
            name: Category.objects.get_or_create(name=normalize_category_name(name))[0]
            for name in ["Lập trình", "Khoa học", "Trinh thám", "Lãng mạn", "Văn học", "Kinh điển"]
        }

        users = {}
        for username, password, email, is_staff, is_superuser in FAKE_USERS:
            user, _ = User.objects.get_or_create(
                username=username,
                defaults={"email": email, "is_staff": is_staff, "is_superuser": is_superuser, "is_active": True},
            )
            user.email = email
            user.is_staff = is_staff
            user.is_superuser = is_superuser
            user.is_active = True
            user.set_password(password)
            user.save()
            users[username] = user

        for title, author, category_name, description, price, year, pages in FAKE_BOOKS:
            is_digital = title in EBOOK_CONTENT
            Book.objects.update_or_create(
                title=title,
                author=author,
                defaults={
                    "description": description,
                    "price": Decimal(price),
                    "category": categories[normalize_category_name(category_name)],
                    "published_year": year,
                    "num_pages": pages,
                    "stock": 999 if is_digital else rng.randint(8, 80),
                    "is_digital": is_digital,
                    "content_text": EBOOK_CONTENT.get(title, ""),
                    "cover_image": "",
                },
            )

        coupons = [
            ("SAVE10", "percent", 10, 0, 100),
            ("FREESHIP", "fixed", 30000, 100000, 100),
            ("VIP20", "percent", 20, 250000, 50),
        ]
        for code, discount_type, discount_value, min_order, max_uses in coupons:
            Coupon.objects.update_or_create(
                code=code,
                defaults={
                    "discount_type": discount_type,
                    "discount_value": Decimal(discount_value),
                    "min_order_amount": Decimal(min_order),
                    "max_uses": max_uses,
                    "used_count": 0,
                    "active": True,
                    "valid_from": timezone.now() - timezone.timedelta(days=1),
                    "valid_to": timezone.now() + timezone.timedelta(days=45),
                },
            )

        books = list(Book.objects.select_related("category").order_by("id"))
        digital_books = [book for book in books if book.is_digital]
        physical_books = [book for book in books if not book.is_digital]
        order_specs = [
            ("demo", "delivered", "cod", physical_books[:3], "Đơn demo đã giao.", "12 Nguyễn Trãi, Quận 1, TP.HCM", "SAVE10"),
            ("demo", "shipping", "vnpay", physical_books[3:5] + digital_books[:1], "Đơn demo đang giao.", "12 Nguyễn Trãi, Quận 1, TP.HCM", None),
            ("alice", "confirmed", "momo", physical_books[5:8], "Giao giờ hành chính.", "88 Lê Lợi, Đà Nẵng", "FREESHIP"),
            ("bob", "pending", "cod", physical_books[8:10] + digital_books[:1], "Gọi trước khi giao.", "45 Hai Bà Trưng, Hà Nội", None),
            ("staff", "packing", "vnpay", physical_books[10:13], "Đơn nội bộ test dashboard.", "Kho Bookie", "VIP20"),
        ]

        for username, status, payment_method, selected_books, note, address, coupon_code in order_specs:
            if not selected_books:
                continue
            coupon = Coupon.objects.filter(code=coupon_code).first() if coupon_code else None
            order, _ = Order.objects.get_or_create(
                user=users[username],
                note=note,
                defaults={
                    "status": status,
                    "payment_method": payment_method,
                    "shipping_address": address,
                    "coupon": coupon,
                },
            )
            order.status = status
            order.payment_method = payment_method
            order.shipping_address = address
            order.coupon = coupon
            order.items.all().delete()
            for book in selected_books:
                OrderItem.objects.create(
                    order=order,
                    book=book,
                    quantity=1 if book.is_digital else rng.randint(1, 3),
                    price=book.price,
                    is_digital_purchase=book.is_digital,
                )
            order.discount_amount = Decimal(0)
            if coupon:
                order.discount_amount = order.subtotal - coupon.apply_discount(order.subtotal)
            order.save()

        review_comments = [
            "Nội dung dễ đọc, rất hợp để bắt đầu.",
            "Sách trình bày rõ, ví dụ thực tế.",
            "Bìa đẹp, giao diện đọc online ổn.",
            "Mình thích phần gợi ý và cách giải thích.",
            "Đáng mua trong tầm giá.",
        ]
        for user in [users["demo"], users["alice"], users["bob"]]:
            for index, book in enumerate(books[:8]):
                Rating.objects.update_or_create(
                    user=user,
                    book=book,
                    defaults={"score": 5 - (index % 2), "comment": review_comments[index % len(review_comments)]},
                )

        for username in ["demo", "alice", "bob"]:
            for book in books[2:7]:
                Wishlist.objects.get_or_create(user=users[username], book=book)

        for user in [users["demo"], users["alice"]]:
            for index, book in enumerate(digital_books[:3], start=1):
                ReadingProgress.objects.update_or_create(
                    user=user,
                    book=book,
                    defaults={"last_page": index * 2, "is_finished": index == 3},
                )

        audit_actions = [
            ("seed_fake_data", "system", ""),
            ("create_coupon", "Coupon", "SAVE10"),
            ("update_inventory", "Book", "bulk"),
            ("update_order_status", "Order", "demo"),
        ]
        for action, target_type, target_id in audit_actions:
            AdminAuditLog.objects.create(
                actor=users["admin"],
                action=action,
                target_type=target_type,
                target_id=target_id,
                metadata={"source": "seed_fake_data"},
            )

        self.stdout.write(self.style.SUCCESS("Fake data seeded successfully."))
        self.stdout.write(
            f"Users={User.objects.count()}, Categories={Category.objects.count()}, Books={Book.objects.count()}, "
            f"Orders={Order.objects.count()}, Ratings={Rating.objects.count()}, Wishlist={Wishlist.objects.count()}, "
            f"Progress={ReadingProgress.objects.count()}, Coupons={Coupon.objects.count()}, "
            f"AuditLogs={AdminAuditLog.objects.count()}"
        )
        self.stdout.write("Logins: demo/demo123, admin/admin123, alice/alice123, bob/bob123, staff/staff123")
