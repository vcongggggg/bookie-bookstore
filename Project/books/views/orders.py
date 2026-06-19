from .helpers import *
import os
from django.urls import reverse
from ..vnpay import VNPay
from .helpers import _cart_items, _rate_limit_response, _set_cart

@login_required
def checkout(request):
    items = _cart_items(request)
    if not items:
        messages.warning(request, "Giỏ hàng trống.")
        return redirect("cart")

    subtotal = sum(x["subtotal"] for x in items)
    
    if request.method == "POST":
        limited = _rate_limit_response(
            request,
            "checkout",
            settings.CHECKOUT_RATE_LIMIT_REQUESTS,
            settings.CHECKOUT_RATE_LIMIT_WINDOW,
            "Bạn thử đặt hàng quá nhanh. Vui lòng chờ một lúc rồi thử lại.",
        )
        if limited:
            return limited

        form = CheckoutForm(request.POST)
        if form.is_valid():
            coupon_code = form.cleaned_data.get("coupon_code", "").strip()

            with transaction.atomic():
                locked_books = {
                    book.pk: book
                    for book in Book.objects.select_for_update().filter(
                        pk__in=[row["book"].pk for row in items]
                    )
                }
                locked_items = []
                for row in items:
                    book = locked_books.get(row["book"].pk)
                    if not book or row["quantity"] > book.stock:
                        messages.error(
                            request,
                            f"'{row['book'].title}' không đủ hàng cho số lượng bạn chọn.",
                        )
                        return redirect("cart")
                    locked_items.append({**row, "book": book, "subtotal": book.price * row["quantity"]})

                locked_subtotal = sum(row["subtotal"] for row in locked_items)
                discount_amount = 0
                applied_coupon = None

                if coupon_code:
                    try:
                        coupon = Coupon.objects.select_for_update().get(code__iexact=coupon_code)
                        if coupon.is_valid and locked_subtotal >= coupon.min_order_amount:
                            applied_coupon = coupon
                            final_total = coupon.apply_discount(locked_subtotal)
                            discount_amount = locked_subtotal - final_total
                        else:
                            messages.warning(request, "Mã giảm giá không hợp lệ hoặc không đủ điều kiện.")
                    except Coupon.DoesNotExist:
                        messages.warning(request, "Mã giảm giá không tồn tại.")

                order = Order.objects.create(
                    user=request.user,
                    shipping_address=form.cleaned_data["shipping_address"],
                    note=form.cleaned_data.get("note", ""),
                    coupon=applied_coupon,
                    discount_amount=discount_amount,
                    payment_method=form.cleaned_data["payment_method"],
                )
                for row in locked_items:
                    OrderItem.objects.create(
                        order=order,
                        book=row["book"],
                        quantity=row["quantity"],
                        price=row["book"].price,
                        is_digital_purchase=False,
                    )
                    Book.objects.filter(pk=row["book"].pk).update(stock=F("stock") - row["quantity"])

                if applied_coupon:
                    Coupon.objects.filter(pk=applied_coupon.pk).update(used_count=F("used_count") + 1)

            _set_cart(request, {})
            
            # Check for low stock books and send alert
            try:
                from books.email_service import send_low_stock_alert_email
                low_stock_books = []
                for row in locked_items:
                    fresh_book = Book.objects.get(pk=row["book"].pk)
                    if fresh_book.stock < getattr(settings, "LOW_STOCK_THRESHOLD", 10):
                        low_stock_books.append(fresh_book)
                if low_stock_books:
                    send_low_stock_alert_email(low_stock_books)
            except Exception:
                pass  # Do not block order completion if email alert fails

            if order.payment_method != "cod":
                return redirect("payment_gateway", pk=order.pk)

            # For COD, send order confirmation email immediately
            try:
                from books.email_service import send_order_confirmation_email
                send_order_confirmation_email(order)
            except Exception:
                pass

            messages.success(request, f"Đặt hàng thành công! Mã đơn: #{order.pk}")
            return redirect("order_detail", pk=order.pk)
    else:
        form = CheckoutForm()

    context = {
        "form": form,
        "cart_items": items,
        "cart_total": subtotal,
    }
    return render(request, "books/checkout.html", context)



@login_required
def payment_gateway(request, pk: int):
    """View to handle payment gateway redirect (VNPay or mock)."""
    order = get_object_or_404(Order, pk=pk, user=request.user)
    if order.status != "pending":
        return redirect("order_detail", pk=order.pk)
    
    if order.payment_method == "vnpay":
        vnp = VNPay(
            tmn_code=os.getenv('VNP_TMN_CODE'),
            hash_key=os.getenv('VNP_HASH_KEY'),
            return_url=request.build_absolute_uri(reverse('vnpay_return')),
            api_url=os.getenv('VNP_URL')
        )
        # Tính tổng tiền (sau chiết khấu)
        total = order.total
        payment_url = vnp.get_payment_url(
            order_id=order.pk,
            amount=total,
            order_desc=f"Thanh toan don hang #{order.pk} tai Smart Bookstore",
            ipaddr=request.META.get('REMOTE_ADDR')
        )
        return redirect(payment_url)
    
    return render(request, "books/payment.html", {"order": order})

def vnpay_return(request):
    """Callback view for VNPay payment result."""
    vnp = VNPay(
        tmn_code=os.getenv('VNP_TMN_CODE'),
        hash_key=os.getenv('VNP_HASH_KEY'),
        return_url='', # Không cần cho bước validate
        api_url=''
    )
    
    if vnp.validate_response(request.GET):
        order_id = request.GET.get('vnp_TxnRef')
        response_code = request.GET.get('vnp_ResponseCode')
        order = get_object_or_404(Order, pk=order_id)
        
        if response_code == "00":
            if order.status == "pending":
                order.status = "confirmed"
                order.save(update_fields=["status"])
                try:
                    from books.email_service import send_order_confirmation_email
                    send_order_confirmation_email(order)
                except Exception:
                    pass
                messages.success(request, f"Thanh toán VNPay thành công cho đơn hàng #{order.pk}!")
            else:
                messages.info(request, f"Đơn hàng #{order.pk} đã được xử lý trước đó.")
        else:
            messages.error(request, f"Thanh toán VNPay thất bại. Mã lỗi: {response_code}")
            
        return redirect("order_detail", pk=order.pk)
    
    messages.error(request, "Dữ liệu thanh toán không hợp lệ (Checksum failed).")
    return redirect("order_list")


@login_required
def payment_confirm(request, pk: int):
    """View to handle payment confirmation (mock callback)."""
    order = get_object_or_404(Order, pk=pk, user=request.user)
    if order.status == "pending":
        order.status = "confirmed"
        order.save(update_fields=["status"])
        try:
            from books.email_service import send_order_confirmation_email
            send_order_confirmation_email(order)
        except Exception:
            pass
        messages.success(request, f"Thanh toán thành công cho đơn hàng #{order.pk}!")
    
    return redirect("order_detail", pk=order.pk)


@login_required
def order_list(request):
    orders = request.user.orders.prefetch_related("items__book").order_by("-created_at")
    return render(request, "books/order_list.html", {"orders": orders})


@login_required
def order_detail(request, pk: int):
    order = get_object_or_404(Order, pk=pk, user=request.user)
    return render(request, "books/order_detail.html", {"order": order})


@login_required
def order_invoice_pdf(request, pk: int):
    order = get_object_or_404(
        Order.objects.select_related("user", "coupon").prefetch_related("items__book"),
        pk=pk,
        user=request.user,
    )
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, title=f"Invoice #{order.pk}")
    styles = getSampleStyleSheet()
    story = [
        Paragraph("BOOKIE INVOICE", styles["Title"]),
        Paragraph(f"Invoice for order #{order.pk}", styles["Heading2"]),
        Spacer(1, 12),
        Paragraph(f"Customer: {order.user.username}", styles["Normal"]),
        Paragraph(f"Order date: {order.created_at.strftime('%Y-%m-%d %H:%M')}", styles["Normal"]),
        Paragraph(f"Status: {order.status_display_vi}", styles["Normal"]),
        Paragraph(f"Shipping address: {order.shipping_address or 'N/A'}", styles["Normal"]),
        Spacer(1, 16),
    ]

    rows = [["Book", "Qty", "Unit price", "Subtotal"]]
    for item in order.items.all():
        rows.append([
            item.book.title,
            str(item.quantity),
            f"{item.price:,.0f} VND",
            f"{item.subtotal:,.0f} VND",
        ])
    rows.extend([
        ["", "", "Subtotal", f"{order.subtotal:,.0f} VND"],
        ["", "", "Discount", f"-{order.discount_amount:,.0f} VND"],
        ["", "", "Total", f"{order.total:,.0f} VND"],
    ])

    table = Table(rows, colWidths=[230, 50, 100, 100])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f3f4f6")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
    ]))
    story.append(table)
    story.append(Spacer(1, 16))
    story.append(Paragraph("Thank you for shopping at Bookie.", styles["Normal"]))
    doc.build(story)

    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="bookie-order-{order.pk}.pdf"'
    return response


# ═══════════════════════════════════════════════════════════════════
# Wishlist
# ═══════════════════════════════════════════════════════════════════



@login_required
@require_POST
def cancel_order(request, pk: int):
    with transaction.atomic():
        order = get_object_or_404(
            Order.objects.select_for_update().select_related("coupon"),
            pk=pk,
            user=request.user,
        )
        if order.status in ("pending", "confirmed"):
            old_status = order.status
            order.status = "cancelled"
            order.save(update_fields=["status"])
            for item in order.items.select_related("book"):
                Book.objects.filter(pk=item.book_id).update(stock=F("stock") + item.quantity)
            if order.coupon_id:
                Coupon.objects.filter(pk=order.coupon_id, used_count__gt=0).update(
                    used_count=F("used_count") - 1
                )
            try:
                from books.email_service import send_order_status_update_email
                send_order_status_update_email(order, old_status)
            except Exception:
                pass
            messages.success(request, f"Da huy don hang #{order.pk}.")
        else:
            messages.error(request, "Khong the huy don hang o trang thai nay.")
    return redirect("order_detail", pk=order.pk)


# ═══════════════════════════════════════════════════════════════════
# REST API
# ═══════════════════════════════════════════════════════════════════


