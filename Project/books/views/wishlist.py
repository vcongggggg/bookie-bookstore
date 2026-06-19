from .helpers import *

def wishlist_add(request, book_id: int):
    if not request.user.is_authenticated:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({
                "status": "error",
                "message": "Vui lòng đăng nhập để sử dụng danh sách yêu thích.",
            }, status=401)
        return redirect_to_login(request.get_full_path())

    book = get_object_or_404(Book, pk=book_id)
    _, created = Wishlist.objects.get_or_create(user=request.user, book=book)
    wishlist_count = request.user.wishlist_items.count()
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({
            "status": "ok", 
            "action": "added", 
            "message": f"Đã thêm '{book.title}' vào yêu thích.",
            "wishlist_count": wishlist_count
        })
    messages.success(request, f"Đã thêm '{book.title}' vào danh sách yêu thích.")
    next_url = request.GET.get("next") or request.META.get("HTTP_REFERER") or "book_detail"
    if "book_detail" in str(next_url) or not next_url:
        return redirect("book_detail", pk=book.pk)
    return redirect(next_url)


def wishlist_remove(request, book_id: int):
    if not request.user.is_authenticated:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({
                "status": "error",
                "message": "Vui lòng đăng nhập để sử dụng danh sách yêu thích.",
            }, status=401)
        return redirect_to_login(request.get_full_path())

    book = get_object_or_404(Book, pk=book_id)
    Wishlist.objects.filter(user=request.user, book=book).delete()
    wishlist_count = request.user.wishlist_items.count()
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({
            "status": "ok", 
            "action": "removed", 
            "message": f"Đã bỏ '{book.title}' khỏi yêu thích.",
            "wishlist_count": wishlist_count
        })
    messages.info(request, "Đã bỏ khỏi danh sách yêu thích.")
    next_url = request.GET.get("next") or request.META.get("HTTP_REFERER")
    if next_url and "wishlist" in next_url:
        return redirect("wishlist")
    return redirect("book_detail", pk=book.pk)


@login_required
def wishlist_view(request):
    items = request.user.wishlist_items.select_related("book").order_by("-added_at")
    return render(request, "books/wishlist.html", {"wishlist_items": items})


# ═══════════════════════════════════════════════════════════════════
# Profile
# ═══════════════════════════════════════════════════════════════════


