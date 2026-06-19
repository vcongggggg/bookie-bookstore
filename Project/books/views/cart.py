from .helpers import *
from .helpers import _get_cart, _set_cart, _cart_items, _rate_limit_response

def cart_view(request):
    items = _cart_items(request)
    total = sum(x["subtotal"] for x in items)
    context = {"cart_items": items, "cart_total": total}
    return render(request, "books/cart.html", context)


@require_POST
def add_to_cart(request, book_id: int):
    book = get_object_or_404(Book, pk=book_id)

    book_format = request.POST.get("format", "physical")
    if book_format == "digital":
        message = "Đọc online đang miễn phí. Giỏ hàng chỉ dùng để mua sách giấy."
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"status": "error", "message": message})
        messages.info(request, message)
        return redirect("book_detail", pk=book.pk)

    if book_format == "physical" and not book.in_stock:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"status": "error", "message": f"'{book.title}' đã hết hàng."})
        messages.error(request, f"'{book.title}' đã hết hàng.")
        return redirect("book_detail", pk=book.pk)

    cart = _get_cart(request)
    key = f"{book.pk}_{book_format}"
    qty = request.POST.get("quantity") or request.GET.get("quantity") or 1
    try:
        qty = max(1, int(qty))
    except (TypeError, ValueError):
        qty = 1
    new_qty = cart.get(key, 0) + qty
    if new_qty > book.stock:
        new_qty = book.stock

    cart[key] = new_qty
    _set_cart(request, cart)

    # AJAX response
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        cart_total = sum(cart.values())
        return JsonResponse({
            "status": "ok",
            "message": f"Đã thêm sách giấy '{book.title}' vào giỏ hàng.",
            "cart_count": cart_total,
        })

    messages.success(request, f"Đã thêm sách giấy '{book.title}' vào giỏ.")
    next_url = request.GET.get("next") or request.POST.get("next") or "book_detail"
    if next_url == "book_detail":
        return redirect("book_detail", pk=book.pk)
    return redirect("cart")


@require_POST
def update_cart(request):
    cart = _get_cart(request)
    remove_item = request.POST.get("remove_item")
    if remove_item in cart:
        del cart[remove_item]
        _set_cart(request, cart)
        messages.info(request, "Đã xóa sản phẩm khỏi giỏ.")
        return redirect("cart")

    for key in list(cart.keys()):
        qty = request.POST.get(f"qty_{key}")
        if qty is not None:
            try:
                n = int(qty)
                if n <= 0:
                    del cart[key]
                else:
                    cart[key] = n
            except (TypeError, ValueError):
                pass
    _set_cart(request, cart)
    messages.info(request, "Đã cập nhật giỏ hàng.")
    return redirect("cart")


@require_POST
def remove_from_cart(request, item_key: str):
    cart = _get_cart(request)
    if item_key in cart:
        del cart[item_key]
        _set_cart(request, cart)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"status": "ok", "cart_count": sum(cart.values())})
    messages.info(request, "Đã xóa sản phẩm khỏi giỏ.")
    return redirect("cart")



@login_required
@require_POST
def api_apply_coupon(request):
    """AJAX API to validate and calculate coupon discount."""
    limited = _rate_limit_response(
        request,
        "coupon",
        settings.COUPON_RATE_LIMIT_REQUESTS,
        settings.COUPON_RATE_LIMIT_WINDOW,
        "Bạn thử mã giảm giá quá nhanh. Vui lòng chờ một lúc rồi thử lại.",
    )
    if limited:
        return limited

    coupon_code = request.POST.get("code", "").strip()
    try:
        subtotal = Decimal(str(request.POST.get("subtotal", "0")))
    except (InvalidOperation, TypeError):
        return JsonResponse({"status": "error", "message": "Giá trị đơn hàng không hợp lệ."}, status=400)
    
    try:
        coupon = Coupon.objects.get(code__iexact=coupon_code)
        if not coupon.is_valid:
            return JsonResponse({"status": "error", "message": "Mã giảm giá đã hết hạn hoặc hết lượt dùng."})
        
        if subtotal < coupon.min_order_amount:
            return JsonResponse({
                "status": "error", 
                "message": f"Đơn hàng tối thiểu {coupon.min_order_amount:,.0f}₫ để dùng mã này."
            })
            
        final_total = coupon.apply_discount(subtotal)
        discount = subtotal - final_total
        
        return JsonResponse({
            "status": "ok",
            "message": f"Áp dụng thành công: {coupon}",
            "discount": float(discount),
            "final_total": float(final_total),
            "coupon_code": coupon.code
        })
    except Coupon.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Mã giảm giá không tồn tại."})



