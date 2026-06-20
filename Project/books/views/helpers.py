import csv
import html as html_lib
import json
import re
from decimal import Decimal, InvalidOperation
from io import BytesIO
from collections import Counter, defaultdict
from datetime import timedelta
from html.parser import HTMLParser
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model, login, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import Group
from django.contrib.auth.views import LoginView, redirect_to_login
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, Count, F, Q, Sum
from django.http import HttpRequest, HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..chatbot import BookieChatbot
from ..forms import (
    BookAdminForm,
    CheckoutForm,
    CouponAdminForm,
    ProfileEditForm,
    RatingForm,
    RegisterForm,
)
from ..models import AdminAuditLog, Book, Category, Coupon, Order, OrderItem, Rating, ReadingProgress, Wishlist
from ..ollama_client import OllamaClient, OllamaConfig, OllamaError
from ..rbac import INTERNAL_ROLES, ROLE_CHOICES, primary_role

User = get_user_model()


def _client_actor(request: HttpRequest) -> str:
    if request.user.is_authenticated:
        return f"user:{request.user.pk}"
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    ip_address = forwarded_for.split(",", 1)[0].strip() if forwarded_for else request.META.get("REMOTE_ADDR", "unknown")
    return f"ip:{ip_address or 'unknown'}"


def _rate_limit_response(
    request: HttpRequest,
    scope: str,
    limit: int,
    window: int,
    message: str,
):
    if limit <= 0 or window <= 0:
        return None

    key = f"rate_limit:{scope}:{_client_actor(request)}"
    if cache.add(key, 1, timeout=window):
        return None

    try:
        count = cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=window)
        return None

    if count > limit:
        return JsonResponse({"error": message, "retry_after": window}, status=429)
    return None


# ═══════════════════════════════════════════════════════════════════
# Cart helpers (session: { "cart": { "book_id": quantity } })
# ═══════════════════════════════════════════════════════════════════


def _get_cart(request):
    cart = request.session.get("cart")
    if not isinstance(cart, dict):
        cart = {}
    return cart


def _set_cart(request, cart):
    request.session["cart"] = cart
    request.session.modified = True


def _cart_items(request):
    cart = _get_cart(request)
    if not cart:
        return []
    book_ids = []
    for key in cart.keys():
        try:
            book_ids.append(int(str(key).split("_")[0]))
        except (TypeError, ValueError):
            continue

    books = Book.objects.filter(pk__in=set(book_ids))
    book_map = {str(book.pk): book for book in books}
    items = []
    for key, qty in cart.items():
        parts = str(key).split("_")
        book = book_map.get(parts[0])
        if not book:
            continue
        book_format = parts[1] if len(parts) > 1 else "physical"
        if book_format != "physical":
            continue
        items.append({
            "book": book,
            "quantity": qty,
            "subtotal": book.price * qty,
            "format": book_format,
            "key": str(key),
        })
    return items


# ═══════════════════════════════════════════════════════════════════
# Recently viewed (session: list of book ids, newest last)
# ═══════════════════════════════════════════════════════════════════


def _push_recently_viewed(request, book_id: int):
    ids = request.session.get("recently_viewed")
    if not isinstance(ids, list):
        ids = []
    book_id = int(book_id)
    if book_id in ids:
        ids.remove(book_id)
    ids.append(book_id)
    request.session["recently_viewed"] = ids[-20:]
    request.session.modified = True


def _recently_viewed_books(request, limit: int = 6):
    ids = request.session.get("recently_viewed")
    if not isinstance(ids, list) or not ids:
        return []
    ids = ids[-limit:][::-1]
    books = list(Book.objects.filter(pk__in=ids))
    return _order_books_by_ids(books, ids)


def _order_books_by_ids(queryset, ids):
    by_id = {b.pk: b for b in queryset}
    return [by_id[i] for i in ids if i in by_id]


# ═══════════════════════════════════════════════════════════════════
# AI Recommendation helpers
# ═══════════════════════════════════════════════════════════════════


def _get_popular_books(limit: int = 15):
    """Sách bán chạy nhất dựa trên số lượng đơn hàng."""
    cache_key = f"popular_books_{limit}"
    books = cache.get(cache_key)
    if books is None:
        books = list(
            Book.objects.annotate(total_sold=Count("order_items"))
            .order_by("-total_sold", "title")[:limit]
        )
        cache.set(cache_key, books, 3600)
    return books


def _get_top_rated_books(limit: int = 15):
    """Sách được đánh giá cao nhất."""
    cache_key = f"top_rated_books_{limit}"
    books = cache.get(cache_key)
    if books is None:
        books = list(
            Book.objects.annotate(avg_rating=Avg("ratings__score"), rating_count=Count("ratings"))
            .filter(rating_count__gt=0)
            .order_by("-avg_rating", "-rating_count", "title")[:limit]
        )
        cache.set(cache_key, books, 3600)
    return books


def _get_recommended_for_user(user, limit: int = 8):
    """Content-based + collaborative recommendation."""
    user_orders = OrderItem.objects.filter(order__user=user)
    user_ratings = Rating.objects.filter(user=user, score__gte=4)

    # --- Content-based: categories user liked ---
    category_ids = set(
        Category.objects.filter(books__order_items__in=user_orders)
        .values_list("id", flat=True)
    ) | set(
        Category.objects.filter(books__ratings__in=user_ratings)
        .values_list("id", flat=True)
    )

    # --- Collaborative: books bought by users who bought same books ---
    user_book_ids = set(user_orders.values_list("book_id", flat=True))
    if user_book_ids:
        similar_users = (
            OrderItem.objects.filter(book_id__in=user_book_ids)
            .exclude(order__user=user)
            .values_list("order__user", flat=True)
            .distinct()[:50]
        )
        collaborative_book_ids = set(
            OrderItem.objects.filter(order__user__in=similar_users)
            .exclude(book_id__in=user_book_ids)
            .values_list("book_id", flat=True)
            .distinct()[:limit]
        )
    else:
        collaborative_book_ids = set()

    if not category_ids and not collaborative_book_ids:
        return _get_popular_books(limit=limit)

    # Combine: content-based categories + collaborative book IDs
    qs = Book.objects.filter(
        Q(category_id__in=category_ids) | Q(pk__in=collaborative_book_ids)
    )
    if user_book_ids:
        qs = qs.exclude(pk__in=user_book_ids)

    return (
        qs.annotate(total_sold=Count("order_items"), avg_rating=Avg("ratings__score"))
        .order_by("-avg_rating", "-total_sold", "title")
        .distinct()[:limit]
    )


def _get_content_similar_books(book, limit: int = 8):
    """TF-IDF-like content similarity based on description keywords."""
    if not book.description:
        return (
            Book.objects.filter(category=book.category)
            .exclude(pk=book.pk)
            .annotate(total_sold=Count("order_items"))
            .order_by("-total_sold", "title")[:limit]
        )

    # Simple keyword extraction
    words = re.findall(r'\b[a-zA-Zàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]{3,}\b',
                       book.description.lower())
    word_freq = Counter(words)
    top_keywords = [w for w, _ in word_freq.most_common(10)]

    if not top_keywords:
        return (
            Book.objects.filter(category=book.category)
            .exclude(pk=book.pk)
            .annotate(total_sold=Count("order_items"))
            .order_by("-total_sold", "title")[:limit]
        )

    # Find books with matching keywords in description
    q_filter = Q()
    for kw in top_keywords[:5]:
        q_filter |= Q(description__icontains=kw)

    similar = (
        Book.objects.filter(q_filter)
        .exclude(pk=book.pk)
        .annotate(total_sold=Count("order_items"))
        .order_by("-total_sold", "title")
        .distinct()[:limit]
    )

    if similar.count() < 4:
        # Fallback to category-based
        fallback = (
            Book.objects.filter(category=book.category)
            .exclude(pk=book.pk)
            .exclude(pk__in=similar.values_list("pk", flat=True))
            .annotate(total_sold=Count("order_items"))
            .order_by("-total_sold", "title")[: limit - similar.count()]
        )
        return list(similar) + list(fallback)

    return similar


def _also_bought_books(book, limit: int = 6):
    """Collaborative: users who bought this book also bought..."""
    buyers = list(
        OrderItem.objects.filter(book=book)
        .values_list("order__user", flat=True)
        .distinct()[:100]
    )
    if not buyers:
        return []
    return (
        Book.objects.filter(order_items__order__user__in=buyers)
        .exclude(pk=book.pk)
        .annotate(buy_count=Count("order_items"))
        .order_by("-buy_count", "title")
        .distinct()[:limit]
    )


def _books_queryset(search=None, category_id=None, sort="title"):
    qs = Book.objects.all()
    if search and search.strip():
        q = Q(title__icontains=search.strip()) | Q(author__icontains=search.strip())
        qs = qs.filter(q)
    if category_id:
        qs = qs.filter(category_id=category_id)
    if sort == "price_asc":
        qs = qs.order_by("price", "title")
    elif sort == "price_desc":
        qs = qs.order_by("-price", "title")
    elif sort == "newest":
        qs = qs.order_by("-created_at", "title")
    elif sort == "popular":
        qs = qs.annotate(total_sold=Count("order_items")).order_by("-total_sold", "title")
    elif sort == "top_rated":
        qs = (
            qs.annotate(avg_rating=Avg("ratings__score"), rating_count=Count("ratings"))
            .filter(rating_count__gt=0)
            .order_by("-avg_rating", "-rating_count", "title")
        )
    else:
        qs = qs.order_by("title")
    return qs


# ═══════════════════════════════════════════════════════════════════
# Views
# ═══════════════════════════════════════════════════════════════════


