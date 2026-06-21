from .helpers import *
import logging
import os
import uuid
from django.db import transaction
from django.http import HttpResponseBadRequest
from django.urls import reverse
from django.views.decorators.http import require_POST
from ..vnpay import VNPay
from ..services import ServiceError, mark_order_paid
from .helpers import _cart_items, _rate_limit_response, _set_cart

logger = logging.getLogger(__name__)

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
            ik = form.cleaned_data.get("idempotency_key", "").strip()

            if coupon_code:
                from ..services import validate_coupon_for_order
                res = validate_coupon_for_order(coupon_code, subtotal)
                if res["status"] == "error":
                    messages.warning(request, res["message"])

            try:
                from ..services import create_order_from_cart, ServiceError
                order = create_order_from_cart(
                    user=request.user,
                    shipping_address=form.cleaned_data["shipping_address"],
                    note=form.cleaned_data.get("note", ""),
                    coupon_code=coupon_code,
                    payment_method=form.cleaned_data["payment_method"],
                    items=items,
                    idempotency_key=ik or None,
                )
                
                _set_cart(request, {})

                if order.payment_method != "cod":
                    return redirect("payment_gateway", pk=order.pk)

                messages.success(request, f"Đặt hàng thành công! Mã đơn: #{order.pk}")
                return redirect("order_detail", pk=order.pk)
            except ServiceError as exc:
                messages.error(request, str(exc))
                return redirect("cart")
    else:
        ik = uuid.uuid4().hex
        form = CheckoutForm(initial={"idempotency_key": ik})

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
    """Return handler for VNPay payment results."""
    vnp = VNPay(
        tmn_code=os.getenv("VNP_TMN_CODE"),
        hash_key=os.getenv("VNP_HASH_KEY"),
        return_url="",
        api_url="",
    )

    if not vnp.validate_response(request.GET):
        logger.warning("VNPay return rejected: checksum failed")
        messages.error(request, "Dữ liệu thanh toán không hợp lệ (checksum failed).")
        return redirect("order_list")

    order_id = request.GET.get("vnp_TxnRef")
    response_code = request.GET.get("vnp_ResponseCode")
    vnp_amount = request.GET.get("vnp_Amount")
    vnp_transaction_no = request.GET.get("vnp_TransactionNo")

    if not order_id:
        logger.warning("VNPay return rejected: missing vnp_TxnRef")
        messages.error(request, "Thiếu mã đơn hàng trong dữ liệu thanh toán.")
        return redirect("order_list")

    with transaction.atomic():
        order = get_object_or_404(Order.objects.select_for_update(), pk=order_id)

        if order.payment_method != "vnpay":
            logger.warning("VNPay return rejected: order=%s has payment_method=%s", order.pk, order.payment_method)
            messages.error(request, "Phương thức thanh toán của đơn hàng không hợp lệ.")
            return redirect("order_detail", pk=order.pk)

        if not vnp_amount or not vnp_transaction_no:
            logger.warning("VNPay return rejected: missing amount or transaction id for order=%s", order.pk)
            order.payment_status = "failed"
            order.save(update_fields=["payment_status"])
            messages.error(request, "Thiếu dữ liệu giao dịch VNPay.")
            return redirect("order_detail", pk=order.pk)

        try:
            vnp_amount_decimal = Decimal(vnp_amount) / 100
        except (TypeError, ValueError, InvalidOperation):
            vnp_amount_decimal = Decimal("0")

        if abs(order.total - vnp_amount_decimal) > Decimal("1.00"):
            logger.warning("VNPay return rejected: amount mismatch for order=%s expected=%s received=%s", order.pk, order.total, vnp_amount_decimal)
            order.payment_status = "failed"
            order.save(update_fields=["payment_status"])
            messages.error(request, "Số tiền thanh toán không khớp với tổng tiền đơn hàng.")
            return redirect("order_detail", pk=order.pk)

        if order.payment_status == "paid":
            logger.info("VNPay return replay ignored: order=%s transaction_id=%s", order.pk, order.transaction_id)
            messages.info(request, f"Đơn hàng #{order.pk} đã được thanh toán và xử lý trước đó.")
            return redirect("order_detail", pk=order.pk)

        if response_code == "00":
            try:
                mark_order_paid(
                    order,
                    transaction_id=vnp_transaction_no,
                    payment_reference=request.GET.get("vnp_BankTranNo") or vnp_transaction_no,
                    source="vnpay_return",
                )
            except ServiceError as exc:
                messages.error(request, str(exc))
                return redirect("order_detail", pk=order.pk)
            messages.success(request, f"Thanh toán VNPay thành công cho đơn hàng #{order.pk}!")
        else:
            logger.info("VNPay payment failed: order=%s response_code=%s", order.pk, response_code)
            order.payment_status = "failed"
            order.save(update_fields=["payment_status"])
            messages.error(request, f"Thanh toán VNPay thất bại. Mã lỗi: {response_code}")

        return redirect("order_detail", pk=order.pk)


@login_required
@require_POST
def payment_confirm(request, pk: int):
    """View to handle payment confirmation (mock callback)."""
    with transaction.atomic():
        order = get_object_or_404(Order.objects.select_for_update(), pk=pk, user=request.user)

        if order.payment_method != "momo":
            logger.warning("Mock payment rejected: order=%s method=%s user=%s", order.pk, order.payment_method, request.user.pk)
            return HttpResponseBadRequest("Mock payment confirmation is only available for Momo orders.")

        if order.payment_status == "paid":
            logger.info("Mock payment replay ignored: order=%s", order.pk)
            messages.info(request, f"Đơn hàng #{order.pk} đã được thanh toán trước đó.")
            return redirect("order_detail", pk=order.pk)

        try:
            mark_order_paid(
                order,
                transaction_id=f"MOCK-MOMO-{order.pk}-{uuid.uuid4().hex[:6].upper()}",
                payment_reference="MOCK-MOMO",
                source="momo_mock",
            )
        except ServiceError as exc:
            messages.error(request, str(exc))
            return redirect("order_detail", pk=order.pk)

        messages.success(request, f"Thanh toán Momo mô phỏng thành công cho đơn hàng #{order.pk}!")
    
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
    try:
        from ..services import cancel_order_by_user, ServiceError
        order = cancel_order_by_user(user=request.user, order_pk=pk)
        messages.success(request, f"Da huy don hang #{order.pk}.")
    except ServiceError as exc:
        messages.error(request, str(exc))
    return redirect("order_detail", pk=pk)


# ═══════════════════════════════════════════════════════════════════
# REST API
# ═══════════════════════════════════════════════════════════════════


