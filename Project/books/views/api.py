from .helpers import *
from .helpers import _books_queryset, _cart_items
from .profile import _get_book_sentiment_summary

def api_books(request):
    """REST API: list books with pagination, search, filter."""
    page_num = request.GET.get("page", 1)
    per_page = min(int(request.GET.get("per_page", 20)), 50)
    search = request.GET.get("q", "").strip()
    category = request.GET.get("category")
    sort = request.GET.get("sort", "title")

    qs = _books_queryset(search=search or None, category_id=category, sort=sort)
    paginator = Paginator(qs, per_page)
    page = paginator.get_page(page_num)

    books_data = [
        {
            "id": b.pk,
            "title": b.title,
            "author": b.author,
            "price": float(b.price),
            "category": b.category.name if b.category else None,
            "published_year": b.published_year,
            "stock": b.stock,
            "in_stock": b.in_stock,
            "cover_image": b.cover_image or None,
            "description": (b.description or "")[:300],
            "url": f"/books/{b.pk}/",
        }
        for b in page.object_list
    ]
    return JsonResponse({
        "count": paginator.count,
        "num_pages": paginator.num_pages,
        "current_page": page.number,
        "results": books_data,
    })


def api_book_detail(request, pk: int):
    """REST API: single book detail."""
    book = get_object_or_404(Book, pk=pk)
    avg_rating = book.ratings.aggregate(avg=Avg("score"), cnt=Count("id"))
    sentiment = _get_book_sentiment_summary(book)
    return JsonResponse({
        "id": book.pk,
        "title": book.title,
        "author": book.author,
        "price": float(book.price),
        "description": book.description or "",
        "category": book.category.name if book.category else None,
        "published_year": book.published_year,
        "num_pages": book.num_pages,
        "stock": book.stock,
        "in_stock": book.in_stock,
        "cover_image": book.cover_image or None,
        "avg_rating": round(avg_rating["avg"], 1) if avg_rating["avg"] else None,
        "rating_count": avg_rating["cnt"],
        "sentiment": sentiment,
    })


def api_stats(request):
    """REST API: public stats."""
    total_books = Book.objects.count()
    total_categories = Category.objects.count()
    total_ratings = Rating.objects.count()
    avg_rating = Rating.objects.aggregate(avg=Avg("score"))["avg"]
    return JsonResponse({
        "total_books": total_books,
        "total_categories": total_categories,
        "total_ratings": total_ratings,
        "avg_rating": round(avg_rating, 2) if avg_rating else None,
    })


# ═══════════════════════════════════════════════════════════════════
# Enhanced API Layer: Cart, Orders, and Profile
# ═══════════════════════════════════════════════════════════════════
import json
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt

def api_cart(request):
    """REST API: get cart (GET) or update cart items (POST)."""
    cart = request.session.get("cart", {})
    if request.method == "POST":
        try:
            data = json.loads(request.body) if request.body else {}
            action = data.get("action")
            book_id = str(data.get("book_id", ""))
            
            if action == "add":
                qty = int(data.get("quantity", 1))
                book = get_object_or_404(Book, pk=book_id)
                cart[book_id] = cart.get(book_id, 0) + qty
            elif action == "update":
                qty = int(data.get("quantity", 1))
                book = get_object_or_404(Book, pk=book_id)
                if qty <= 0:
                    cart.pop(book_id, None)
                else:
                    cart[book_id] = min(qty, book.stock)
            elif action == "remove":
                cart.pop(book_id, None)
            
            request.session["cart"] = cart
            request.session.modified = True
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=400)
            
    items = _cart_items(request)
    cart_data = [
        {
            "book_id": item["book"].pk,
            "title": item["book"].title,
            "price": float(item["book"].price),
            "quantity": item["quantity"],
            "subtotal": float(item["subtotal"]),
            "cover_image": item["book"].cover_image or None
        }
        for item in items
    ]
    return JsonResponse({
        "cart_items": cart_data,
        "cart_total": float(sum(item["subtotal"] for item in items))
    })


@login_required
def api_orders(request):
    """REST API: list all orders of the authenticated user."""
    orders = request.user.orders.all().order_by("-created_at")
    orders_data = [
        {
            "id": o.pk,
            "status": o.status,
            "status_vi": o.status_display_vi,
            "payment_method": o.payment_method,
            "payment_status": o.payment_status,
            "total": float(o.total),
            "created_at": o.created_at.isoformat()
        }
        for o in orders
    ]
    return JsonResponse({"orders": orders_data})


@login_required
def api_order_detail(request, pk: int):
    """REST API: order details with owner-only access validation."""
    order = get_object_or_404(Order, pk=pk)
    if order.user != request.user and not request.user.is_staff:
        return JsonResponse({"status": "error", "message": "Bạn không có quyền xem đơn hàng này."}, status=403)
    
    items_data = [
        {
            "book_id": item.book.pk,
            "title": item.book.title,
            "quantity": item.quantity,
            "price": float(item.price),
            "subtotal": float(item.subtotal)
        }
        for item in order.items.select_related("book")
    ]
    
    return JsonResponse({
        "id": order.pk,
        "status": order.status,
        "status_vi": order.status_display_vi,
        "payment_method": order.payment_method,
        "payment_status": order.payment_status,
        "paid_at": order.paid_at.isoformat() if order.paid_at else None,
        "transaction_id": order.transaction_id,
        "discount_amount": float(order.discount_amount),
        "subtotal": float(order.subtotal),
        "total": float(order.total),
        "shipping_address": order.shipping_address,
        "note": order.note,
        "created_at": order.created_at.isoformat(),
        "items": items_data
    })


@login_required
def api_profile(request):
    """REST API: current user profile details with primary RBAC role."""
    from ..rbac import primary_role
    user = request.user
    return JsonResponse({
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "date_joined": user.date_joined.isoformat(),
        "is_staff": user.is_staff,
        "primary_role": primary_role(user)
    })
