import logging
from decimal import Decimal
from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .models import Book, Coupon, Order, OrderItem
from .tasks import (
    send_order_confirmation_email_task,
    send_order_status_update_email_task,
    send_low_stock_alert_email_task,
)

logger = logging.getLogger(__name__)

class ServiceError(Exception):
    pass

def validate_coupon_for_order(coupon_code: str, subtotal: Decimal) -> dict:
    """Validate a coupon against subtotal.
    Returns:
        dict: {"status": "ok", "coupon": Coupon, "discount": Decimal, "final_total": Decimal}
        or {"status": "error", "message": str}
    """
    if not coupon_code:
        return {"status": "ok", "coupon": None, "discount": Decimal("0"), "final_total": subtotal}

    try:
        coupon = Coupon.objects.get(code__iexact=coupon_code)
        if not coupon.is_valid:
            return {"status": "error", "message": "Mã giảm giá đã hết hạn hoặc hết lượt dùng."}

        if subtotal < coupon.min_order_amount:
            return {
                "status": "error",
                "message": f"Đơn hàng tối thiểu {coupon.min_order_amount:,.0f}₫ để dùng mã này."
            }

        final_total = coupon.apply_discount(subtotal)
        discount = subtotal - final_total
        return {
            "status": "ok",
            "coupon": coupon,
            "discount": discount,
            "final_total": final_total,
        }
    except Coupon.DoesNotExist:
        return {"status": "error", "message": "Mã giảm giá không tồn tại."}

def create_order_from_cart(user, shipping_address: str, note: str, coupon_code: str, payment_method: str, items: list[dict]) -> Order:
    """Create an order atomically, checking and locking stock, and applying a coupon if valid."""
    if not items:
        raise ServiceError("Giỏ hàng trống.")

    with transaction.atomic():
        # Lock books in DB to prevent race conditions during concurrent orders
        book_ids = [row["book"].pk for row in items]
        locked_books = {
            book.pk: book
            for book in Book.objects.select_for_update().filter(pk__in=book_ids)
        }

        # Check stock sufficiency and compute subtotal
        locked_items = []
        for row in items:
            book = locked_books.get(row["book"].pk)
            if not book or row["quantity"] > book.stock:
                raise ServiceError(f"'{row['book'].title}' không đủ hàng cho số lượng bạn chọn.")
            locked_items.append({
                **row,
                "book": book,
                "subtotal": book.price * row["quantity"]
            })

        locked_subtotal = sum(row["subtotal"] for row in locked_items)
        discount_amount = Decimal("0")
        applied_coupon = None

        if coupon_code:
            coupon_res = validate_coupon_for_order(coupon_code, locked_subtotal)
            if coupon_res["status"] == "ok":
                applied_coupon = coupon_res["coupon"]
                discount_amount = coupon_res["discount"]
            else:
                # We don't block order completion if coupon is invalid, just warning in view
                pass

        # Create Order
        order = Order.objects.create(
            user=user,
            shipping_address=shipping_address,
            note=note,
            coupon=applied_coupon,
            discount_amount=discount_amount,
            payment_method=payment_method,
        )

        # Create OrderItems and decrease stock
        for row in locked_items:
            OrderItem.objects.create(
                order=order,
                book=row["book"],
                quantity=row["quantity"],
                price=row["book"].price,
                is_digital_purchase=False,
            )
            Book.objects.filter(pk=row["book"].pk).update(stock=F("stock") - row["quantity"])

        # Increment coupon usage
        if applied_coupon:
            Coupon.objects.filter(pk=applied_coupon.pk).update(used_count=F("used_count") + 1)

    # Queue background emails via Huey after successful transaction commit
    if order.payment_method == "cod":
        send_order_confirmation_email_task(order.pk)
    
    # Check low stock threshold and queue warning emails
    low_stock_ids = []
    for row in locked_items:
        fresh_book = Book.objects.get(pk=row["book"].pk)
        if fresh_book.stock < 10:  # threshold is 10
            low_stock_ids.append(fresh_book.pk)
    if low_stock_ids:
        send_low_stock_alert_email_task(low_stock_ids)

    return order

def cancel_order_by_user(user, order_pk: int) -> Order:
    """Atomic cancellation of an order by the customer."""
    with transaction.atomic():
        order = get_object_or_404(
            Order.objects.select_for_update().select_related("coupon"),
            pk=order_pk,
            user=user,
        )
        if order.status not in ("pending", "confirmed"):
            raise ServiceError("Không thể hủy đơn hàng ở trạng thái này.")

        old_status = order.status
        order.status = "cancelled"
        order.save(update_fields=["status"])

        # Restore book stock
        for item in order.items.select_related("book"):
            Book.objects.filter(pk=item.book_id).update(stock=F("stock") + item.quantity)

        # Revert coupon usage
        if order.coupon_id:
            Coupon.objects.filter(pk=order.coupon_id, used_count__gt=0).update(
                used_count=F("used_count") - 1
            )

    # Queue background status email after transaction commits
    send_order_status_update_email_task(order.pk, old_status)
    return order
