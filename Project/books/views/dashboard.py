from .helpers import *

@staff_member_required
def dashboard(request):
    now = timezone.now()

    # Overall stats
    total_revenue = OrderItem.objects.aggregate(
        total=Sum(F("price") * F("quantity"))
    )["total"] or 0
    total_orders = Order.objects.count()
    total_users = User.objects.count()
    total_books = Book.objects.count()

    # Revenue by month (last 12 months)
    months_data = []
    for i in range(11, -1, -1):
        month_start = (now.replace(day=1) - timedelta(days=i * 30)).replace(day=1, hour=0, minute=0, second=0)
        if i > 0:
            month_end = (month_start + timedelta(days=32)).replace(day=1)
        else:
            month_end = now
        revenue = OrderItem.objects.filter(
            order__created_at__gte=month_start,
            order__created_at__lt=month_end,
        ).aggregate(total=Sum(F("price") * F("quantity")))["total"] or 0
        months_data.append({
            "label": month_start.strftime("%m/%Y"),
            "revenue": float(revenue),
        })

    # Top selling books
    top_books = (
        Book.objects.annotate(total_sold=Count("order_items"))
        .filter(total_sold__gt=0)
        .order_by("-total_sold")[:10]
    )

    # Category distribution
    cat_dist = (
        Category.objects.annotate(book_count=Count("books"))
        .filter(book_count__gt=0)
        .order_by("-book_count")[:8]
    )

    # Order status distribution
    status_dist = (
        Order.objects.values("status")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    # Recent orders
    recent_orders = Order.objects.select_related("user").prefetch_related("items").order_by("-created_at")[:10]

    # Rating distribution
    rating_dist = (
        Rating.objects.values("score")
        .annotate(count=Count("id"))
        .order_by("score")
    )

    # Low stock books
    low_stock = Book.objects.filter(stock__lte=10).order_by("stock")[:10]

    context = {
        "total_revenue": total_revenue,
        "total_orders": total_orders,
        "total_users": total_users,
        "total_books": total_books,
        "months_data_json": json.dumps(months_data),
        "top_books": top_books,
        "cat_dist": cat_dist,
        "status_dist": status_dist,
        "recent_orders": recent_orders,
        "rating_dist": rating_dist,
        "low_stock": low_stock,
        "order_statuses": Order.STATUS_CHOICES,
    }
    return render(request, "books/dashboard.html", context)


def _require_perm(request: HttpRequest, perm: str, redirect_name: str) -> bool:
    if request.user.has_perm(perm):
        return True
    messages.error(request, "Ban khong co quyen thuc hien thao tac nay.")
    return False


def _assign_role(user, role: str) -> None:
    if role not in ROLE_CHOICES:
        raise ValueError("Invalid role")
    managed_groups = Group.objects.filter(name__in=INTERNAL_ROLES)
    user.groups.remove(*managed_groups)
    if role == "Customer":
        user.is_staff = False
        user.is_superuser = False
        user.save(update_fields=["is_staff", "is_superuser"])
        return

    group = Group.objects.get(name=role)
    user.groups.add(group)
    user.is_staff = True
    user.is_superuser = role == "Admin"
    user.save(update_fields=["is_staff", "is_superuser"])


def _log_admin_action(
    request: HttpRequest,
    action: str,
    target_type: str,
    target_id: str,
    metadata: dict | None = None,
) -> None:
    AdminAuditLog.objects.create(
        actor=request.user if request.user.is_authenticated else None,
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        metadata=metadata or {},
    )


@staff_member_required
def dashboard_users(request: HttpRequest) -> HttpResponse:
    if not _require_perm(request, "auth.view_user", "dashboard"):
        return redirect("dashboard")
    query = request.GET.get("q", "").strip()
    users_qs = User.objects.all()
    if query:
        users_qs = users_qs.filter(
            Q(username__icontains=query)
            | Q(email__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
        )
    user_rows = []
    for item in users_qs.order_by("-date_joined")[:200]:
        item.primary_role = primary_role(item)
        user_rows.append(item)
    return render(
        request,
        "books/dashboard_users.html",
        {"users": user_rows, "query": query, "role_choices": ROLE_CHOICES},
    )


@staff_member_required
def dashboard_user_detail(request: HttpRequest, pk: int) -> HttpResponse:
    if not _require_perm(request, "auth.view_user", "dashboard"):
        return redirect("dashboard")
    target = get_object_or_404(User, pk=pk)
    return render(
        request,
        "books/dashboard_user_detail.html",
        {
            "profile_user": target,
            "primary_role": primary_role(target),
            "orders": target.orders.prefetch_related("items__book").order_by("-created_at")[:10],
            "wishlist_items": target.wishlist_items.select_related("book").order_by("-added_at")[:10],
            "ratings": target.ratings.select_related("book").order_by("-created_at")[:10],
            "reading_progress": target.reading_progress.select_related("book").order_by("-last_read_at")[:10],
        },
    )


@staff_member_required
@require_POST
def dashboard_user_set_role(request: HttpRequest, pk: int) -> HttpResponse:
    if not _require_perm(request, "auth.change_user", "dashboard_users"):
        return redirect("dashboard_users")
    target = get_object_or_404(User, pk=pk)
    role = request.POST.get("role", "").strip()
    if target.pk == request.user.pk or target.is_superuser:
        messages.error(request, "Khong the thay doi role cua tai khoan nay.")
        return redirect("dashboard_users")
    try:
        _assign_role(target, role)
    except (Group.DoesNotExist, ValueError):
        messages.error(request, "Role khong hop le.")
        return redirect("dashboard_users")
    _log_admin_action(request, "set_role", "user", target.pk, {"role": role})
    messages.success(request, f"Da cap nhat role {role} cho {target.username}.")
    return redirect("dashboard_users")


@staff_member_required
@require_POST
def dashboard_user_toggle_staff(request: HttpRequest, pk: int) -> HttpResponse:
    if not _require_perm(request, "auth.change_user", "dashboard_users"):
        return redirect("dashboard_users")
    target = get_object_or_404(User, pk=pk)
    if target.pk == request.user.pk or target.is_superuser:
        messages.error(request, "Khong the thay doi quyen tai khoan nay.")
        return redirect("dashboard_users")
    next_role = "Customer" if target.is_staff else "Staff"
    _assign_role(target, next_role)
    _log_admin_action(request, "toggle_staff", "user", target.pk, {"role": next_role})
    messages.success(request, f"Da cap nhat quyen staff cho {target.username}.")
    return redirect("dashboard_users")


@staff_member_required
@require_POST
def dashboard_user_toggle_active(request: HttpRequest, pk: int) -> HttpResponse:
    if not _require_perm(request, "auth.change_user", "dashboard_users"):
        return redirect("dashboard_users")
    target = get_object_or_404(User, pk=pk)
    if target.pk == request.user.pk or target.is_superuser:
        messages.error(request, "Khong the khoa/mo tai khoan nay.")
        return redirect("dashboard_users")
    target.is_active = not target.is_active
    target.save(update_fields=["is_active"])
    _log_admin_action(request, "toggle_active", "user", target.pk, {"is_active": target.is_active})
    messages.success(request, f"Da cap nhat trang thai tai khoan {target.username}.")
    return redirect("dashboard_users")


@staff_member_required
def dashboard_books(request: HttpRequest) -> HttpResponse:
    if not _require_perm(request, "books.view_book", "dashboard"):
        return redirect("dashboard")
    query = request.GET.get("q", "").strip()
    category_id = request.GET.get("category")
    qs = Book.objects.select_related("category")
    if query:
        qs = qs.filter(Q(title__icontains=query) | Q(author__icontains=query))
    if category_id:
        qs = qs.filter(category_id=category_id)
    page = Paginator(qs.order_by("-created_at"), 20).get_page(request.GET.get("page", 1))
    return render(
        request,
        "books/dashboard_books.html",
        {
            "books": page.object_list,
            "page": page,
            "categories": Category.objects.order_by("name"),
            "query": query,
            "category_id": category_id,
        },
    )


@staff_member_required
def dashboard_book_create(request: HttpRequest) -> HttpResponse:
    if not _require_perm(request, "books.add_book", "dashboard_books"):
        return redirect("dashboard_books")
    form = BookAdminForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        book = form.save()
        _log_admin_action(request, "book_create", "book", book.pk, {"title": book.title})
        messages.success(request, "Da tao sach moi.")
        return redirect("dashboard_books")
    return render(request, "books/dashboard_book_form.html", {"form": form, "mode": "create"})


@staff_member_required
def dashboard_book_edit(request: HttpRequest, pk: int) -> HttpResponse:
    if not _require_perm(request, "books.change_book", "dashboard_books"):
        return redirect("dashboard_books")
    book = get_object_or_404(Book, pk=pk)
    form = BookAdminForm(request.POST or None, instance=book)
    if request.method == "POST" and form.is_valid():
        book = form.save()
        _log_admin_action(request, "book_edit", "book", book.pk, {"title": book.title})
        messages.success(request, "Da cap nhat sach.")
        return redirect("dashboard_books")
    return render(request, "books/dashboard_book_form.html", {"form": form, "mode": "edit", "book": book})


@staff_member_required
@require_POST
def dashboard_book_delete(request: HttpRequest, pk: int) -> HttpResponse:
    if not _require_perm(request, "books.delete_book", "dashboard_books"):
        return redirect("dashboard_books")
    book = Book.objects.filter(pk=pk).first()
    Book.objects.filter(pk=pk).delete()
    _log_admin_action(request, "book_delete", "book", pk, {"title": book.title if book else ""})
    messages.success(request, "Da xoa sach.")
    return redirect("dashboard_books")


@staff_member_required
def dashboard_coupons(request: HttpRequest) -> HttpResponse:
    if not _require_perm(request, "books.view_coupon", "dashboard"):
        return redirect("dashboard")
    query = request.GET.get("q", "").strip()
    qs = Coupon.objects.all()
    if query:
        qs = qs.filter(code__icontains=query)
    page = Paginator(qs.order_by("-created_at"), 20).get_page(request.GET.get("page", 1))
    return render(request, "books/dashboard_coupons.html", {"coupons": page.object_list, "page": page, "query": query})


@staff_member_required
def dashboard_coupon_create(request: HttpRequest) -> HttpResponse:
    if not _require_perm(request, "books.add_coupon", "dashboard_coupons"):
        return redirect("dashboard_coupons")
    form = CouponAdminForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        coupon = form.save()
        _log_admin_action(request, "coupon_create", "coupon", coupon.pk, {"code": coupon.code})
        messages.success(request, "Da tao ma giam gia.")
        return redirect("dashboard_coupons")
    return render(request, "books/dashboard_coupon_form.html", {"form": form, "mode": "create"})


@staff_member_required
def dashboard_coupon_edit(request: HttpRequest, pk: int) -> HttpResponse:
    if not _require_perm(request, "books.change_coupon", "dashboard_coupons"):
        return redirect("dashboard_coupons")
    coupon = get_object_or_404(Coupon, pk=pk)
    form = CouponAdminForm(request.POST or None, instance=coupon)
    if request.method == "POST" and form.is_valid():
        coupon = form.save()
        _log_admin_action(request, "coupon_edit", "coupon", coupon.pk, {"code": coupon.code})
        messages.success(request, "Da cap nhat ma giam gia.")
        return redirect("dashboard_coupons")
    return render(request, "books/dashboard_coupon_form.html", {"form": form, "mode": "edit", "coupon": coupon})


@staff_member_required
@require_POST
def dashboard_coupon_delete(request: HttpRequest, pk: int) -> HttpResponse:
    if not _require_perm(request, "books.delete_coupon", "dashboard_coupons"):
        return redirect("dashboard_coupons")
    coupon = Coupon.objects.filter(pk=pk).first()
    Coupon.objects.filter(pk=pk).delete()
    _log_admin_action(request, "coupon_delete", "coupon", pk, {"code": coupon.code if coupon else ""})
    messages.success(request, "Da xoa ma giam gia.")
    return redirect("dashboard_coupons")


@staff_member_required
def dashboard_orders(request: HttpRequest) -> HttpResponse:
    if not _require_perm(request, "books.view_order", "dashboard"):
        return redirect("dashboard")
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status")
    qs = Order.objects.select_related("user")
    if query:
        qs = qs.filter(Q(pk__icontains=query) | Q(user__username__icontains=query))
    if status:
        qs = qs.filter(status=status)
    page = Paginator(qs.order_by("-created_at"), 20).get_page(request.GET.get("page", 1))
    return render(
        request,
        "books/dashboard_orders.html",
        {"orders": page.object_list, "page": page, "query": query, "status": status, "order_statuses": Order.STATUS_CHOICES},
    )


# ═══════════════════════════════════════════════════════════════════
# Export CSV
# ═══════════════════════════════════════════════════════════════════


@staff_member_required
def export_orders_csv(request):
    if not _require_perm(request, "books.view_order", "dashboard"):
        return redirect("dashboard")
    response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
    response["Content-Disposition"] = 'attachment; filename="orders.csv"'
    response.write("\ufeff")  # BOM for Excel
    writer = csv.writer(response)
    writer.writerow(["Ma don", "Khach hang", "Trang thai", "Tong tien", "Giam gia", "Thanh toan", "Ngay dat", "Dia chi"])
    for order in Order.objects.select_related("user").order_by("-created_at"):
        writer.writerow([
            order.pk,
            order.user.username,
            order.status_display_vi,
            float(order.subtotal),
            float(order.discount_amount),
            float(order.total),
            order.created_at.strftime("%Y-%m-%d %H:%M"),
            order.shipping_address or "",
        ])
    _log_admin_action(
        request,
        "export_orders_csv",
        "order",
        "all",
        {"count": Order.objects.count()},
    )
    return response


@staff_member_required
def export_books_csv(request):
    if not _require_perm(request, "books.view_book", "dashboard"):
        return redirect("dashboard")
    response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
    response["Content-Disposition"] = 'attachment; filename="books.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(["ID", "Ten sach", "Tac gia", "The loai", "Gia", "Ton kho", "Nam XB", "Mo ta"])
    for book in Book.objects.select_related("category").order_by("title"):
        writer.writerow([
            book.pk,
            book.title,
            book.author,
            book.category.name if book.category else "",
            float(book.price),
            book.stock,
            book.published_year or "",
            (book.description or "")[:200],
        ])
    _log_admin_action(
        request,
        "export_books_csv",
        "book",
        "all",
        {"count": Book.objects.count()},
    )
    return response


@staff_member_required
@require_POST
def api_update_order_status(request, pk: int):
    if not request.user.has_perm("books.change_order"):
        return JsonResponse({"status": "error", "message": "Khong du quyen."}, status=403)
    order = get_object_or_404(Order, pk=pk)
    new_status = request.POST.get("status")
    if new_status in dict(Order.STATUS_CHOICES):
        old_status = order.status
        order.status = new_status
        order.save(update_fields=["status"])
        try:
            from ..tasks import send_order_status_update_email_task
            send_order_status_update_email_task(order.pk, old_status)
        except Exception:
            pass
        _log_admin_action(
            request,
            "order_status_update",
            "order",
            order.pk,
            {"status": order.status},
        )
        return JsonResponse({"status": "ok", "message": f"Đã cập nhật đơn hàng #{order.pk} sang {order.status_display_vi}."})
    return JsonResponse({"status": "error", "message": "Trạng thái không hợp lệ."}, status=400)


@staff_member_required
def dashboard_audit_logs(request: HttpRequest) -> HttpResponse:
    if not _require_perm(request, "books.view_adminauditlog", "dashboard"):
        return redirect("dashboard")
    qs = AdminAuditLog.objects.select_related("actor")
    page = Paginator(qs, 30).get_page(request.GET.get("page", 1))
    return render(request, "books/dashboard_audit.html", {"logs": page.object_list, "page": page})


# ═══════════════════════════════════════════════════════════════════
# Cancel Order
# ═══════════════════════════════════════════════════════════════════


