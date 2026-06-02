import csv
import html as html_lib
import json
import re
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
from django.contrib.auth.views import redirect_to_login
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Avg, Count, F, Q, Sum
from django.http import HttpRequest, HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .chatbot import BookieChatbot
from .forms import (
    BookAdminForm,
    CheckoutForm,
    CouponAdminForm,
    ProfileEditForm,
    RatingForm,
    RegisterForm,
)
from .models import AdminAuditLog, Book, Category, Coupon, Order, OrderItem, Rating, ReadingProgress, Wishlist
from .ollama_client import OllamaClient, OllamaConfig, OllamaError
from .rbac import INTERNAL_ROLES, ROLE_CHOICES, primary_role

User = get_user_model()


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
    return (
        Book.objects.annotate(total_sold=Count("order_items"))
        .order_by("-total_sold", "title")[:limit]
    )


def _get_top_rated_books(limit: int = 15):
    """Sách được đánh giá cao nhất."""
    return (
        Book.objects.annotate(avg_rating=Avg("ratings__score"), rating_count=Count("ratings"))
        .filter(rating_count__gt=0)
        .order_by("-avg_rating", "-rating_count", "title")[:limit]
    )


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


def home(request):
    """Trang chủ: hiển thị các danh mục sách khác nhau dưới dạng Slider."""
    books = Book.objects.all().order_by("-created_at")[:12]
    featured_books = _get_popular_books(15)
    top_rated_books = _get_top_rated_books(15)
    recommended_books = None
    if request.user.is_authenticated:
        recommended_books = _get_explainable_recommendations(request.user, limit=12)
    recently_viewed = _recently_viewed_books(request)
    total_books = Book.objects.count()
    categories = Category.objects.annotate(book_count=Count("books")).order_by("name")
    
    # Get some featured reviews for section 6
    recent_reviews = Rating.objects.select_related("user", "book").order_by("-created_at")[:10]
    
    context = {
        "books": books,
        "featured_books": featured_books,
        "top_rated_books": top_rated_books,
        "recommended_books": recommended_books,
        "recently_viewed": recently_viewed,
        "total_books": total_books,
        "categories": categories,
        "recent_reviews": recent_reviews,
    }
    return render(request, "books/home.html", context)


def book_list(request):
    search = request.GET.get("q", "").strip()
    category_id = request.GET.get("category")
    try:
        current_category_id = int(category_id) if category_id else None
    except (TypeError, ValueError):
        current_category_id = None
    sort = request.GET.get("sort", "title")
    qs = _books_queryset(search=search or None, category_id=current_category_id, sort=sort)
    paginator = Paginator(qs, 12)
    page_num = request.GET.get("page", 1)
    page = paginator.get_page(page_num)
    categories = Category.objects.all().order_by("name")
    context = {
        "page": page,
        "books": page.object_list,
        "categories": categories,
        "search": search,
        "current_category_id": current_category_id,
        "current_sort": sort,
    }
    return render(request, "books/book_list.html", context)


def ebook_list(request):
    search = request.GET.get("q", "").strip()
    category_id = request.GET.get("category")
    try:
        current_category_id = int(category_id) if category_id else None
    except (TypeError, ValueError):
        current_category_id = None

    qs = Book.objects.filter(is_digital=True)
    if search:
        qs = qs.filter(Q(title__icontains=search) | Q(author__icontains=search))
    if current_category_id:
        qs = qs.filter(category_id=current_category_id)

    qs = qs.order_by("title")
    paginator = Paginator(qs, 12)
    page = paginator.get_page(request.GET.get("page", 1))
    categories = Category.objects.filter(books__is_digital=True).distinct().order_by("name")
    wishlist_book_ids = set()
    if request.user.is_authenticated:
        wishlist_book_ids = set(Wishlist.objects.filter(user=request.user).values_list("book_id", flat=True))

    context = {
        "page": page,
        "books": page.object_list,
        "categories": categories,
        "search": search,
        "current_category_id": current_category_id,
        "wishlist_book_ids": wishlist_book_ids,
    }
    return render(request, "books/ebook_list.html", context)


def category_list(request):
    categories = Category.objects.annotate(book_count=Count("books")).order_by("name")
    return render(request, "books/category_list.html", {"categories": categories})


def category_detail(request, pk: int):
    category = get_object_or_404(Category, pk=pk)
    sort = request.GET.get("sort", "title")
    qs = _books_queryset(category_id=pk, sort=sort)
    paginator = Paginator(qs, 12)
    page_num = request.GET.get("page", 1)
    page = paginator.get_page(page_num)
    context = {"category": category, "page": page, "books": page.object_list, "current_sort": sort}
    return render(request, "books/category_detail.html", context)


def book_detail(request, pk: int):
    book = get_object_or_404(Book, pk=pk)
    _push_recently_viewed(request, book.pk)

    # AI: content-based similar books
    similar_books = _get_content_similar_books(book)
    # AI: collaborative also-bought
    also_bought = _also_bought_books(book)

    same_author_books = (
        Book.objects.filter(author=book.author)
        .exclude(pk=book.pk)
        .order_by("title")[:6]
    )
    avg_rating = book.ratings.aggregate(avg=Avg("score"), cnt=Count("id"))
    rating_sort = request.GET.get("rating_sort", "newest")
    rating_filter = request.GET.get("rating_filter", "all")

    book_ratings_qs = book.ratings.select_related("user")
    if rating_filter.isdigit():
        score_value = int(rating_filter)
        if 1 <= score_value <= 5:
            book_ratings_qs = book_ratings_qs.filter(score=score_value)

    if rating_sort == "oldest":
        book_ratings_qs = book_ratings_qs.order_by("created_at")
    elif rating_sort == "highest":
        book_ratings_qs = book_ratings_qs.order_by("-score", "-created_at")
    elif rating_sort == "lowest":
        book_ratings_qs = book_ratings_qs.order_by("score", "-created_at")
    else:
        book_ratings_qs = book_ratings_qs.order_by("-created_at")

    book_ratings = list(book_ratings_qs[:10])
    rating_total = book.ratings.count()
    rating_filtered_total = book_ratings_qs.count()

    # AI: Sentiment analysis
    sentiment_summary = _get_book_sentiment_summary(book)
    # Add sentiment to each rating
    rated_with_sentiment = []
    for r in book_ratings:
        s, confidence = _analyze_sentiment(r.comment)
        rated_with_sentiment.append({
            "rating": r,
            "sentiment": s,
            "confidence": confidence,
        })

    user_rating = None
    rating_form = None
    is_in_wishlist = False
    if request.user.is_authenticated:
        user_rating = book.ratings.filter(user=request.user).first()
        rating_form = RatingForm(instance=user_rating)
        is_in_wishlist = Wishlist.objects.filter(user=request.user, book=book).exists()
    context = {
        "book": book,
        "similar_books": similar_books,
        "also_bought": also_bought,
        "same_author_books": same_author_books,
        "avg_rating": avg_rating,
        "book_ratings": rated_with_sentiment,
        "rating_sort": rating_sort,
        "rating_filter": rating_filter,
        "rating_total": rating_total,
        "rating_filtered_total": rating_filtered_total,
        "sentiment_summary": sentiment_summary,
        "user_rating": user_rating,
        "rating_form": rating_form,
        "is_in_wishlist": is_in_wishlist,
    }
    return render(request, "books/book_detail.html", context)


def register(request):
    if request.user.is_authenticated:
        return redirect("home")
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Đăng ký thành công! Chào mừng bạn đến Smart Bookstore.")
            return redirect("home")
    else:
        form = RegisterForm()
    return render(request, "registration/register.html", {"form": form})


@login_required
def rate_book(request, book_id: int):
    book = get_object_or_404(Book, pk=book_id)
    user_rating = book.ratings.filter(user=request.user).first()
    if request.method == "POST":
        form = RatingForm(request.POST, instance=user_rating)
        if form.is_valid():
            r = form.save(commit=False)
            r.user = request.user
            r.book = book
            r.save()
            messages.success(request, "Đã lưu đánh giá.")
            return redirect("book_detail", pk=book.pk)
    else:
        form = RatingForm(instance=user_rating)
    return render(request, "books/rate_book.html", {"book": book, "form": form})


# ═══════════════════════════════════════════════════════════════════
# Cart & Checkout
# ═══════════════════════════════════════════════════════════════════


def cart_view(request):
    items = _cart_items(request)
    total = sum(x["subtotal"] for x in items)
    context = {"cart_items": items, "cart_total": total}
    return render(request, "books/cart.html", context)


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


def update_cart(request):
    if request.method != "POST":
        return redirect("cart")
    cart = _get_cart(request)
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
def checkout(request):
    items = _cart_items(request)
    if not items:
        messages.warning(request, "Giỏ hàng trống.")
        return redirect("cart")

    subtotal = sum(x["subtotal"] for x in items)
    
    if request.method == "POST":
        form = CheckoutForm(request.POST)
        if form.is_valid():
            coupon_code = form.cleaned_data.get("coupon_code", "").strip()
            discount_amount = 0
            applied_coupon = None
            
            if coupon_code:
                try:
                    coupon = Coupon.objects.get(code__iexact=coupon_code)
                    if coupon.is_valid and subtotal >= coupon.min_order_amount:
                        applied_coupon = coupon
                        final_total = coupon.apply_discount(subtotal)
                        discount_amount = subtotal - final_total
                    else:
                        messages.warning(request, "Mã giảm giá không hợp lệ hoặc không đủ điều kiện.")
                        # Proceed without coupon if invalid during final submission? 
                        # Usually better to error out if they intended to use it.
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
            for row in items:
                OrderItem.objects.create(
                    order=order,
                    book=row["book"],
                    quantity=row["quantity"],
                    price=row["book"].price,
                    is_digital_purchase=False,
                )
                book = row["book"]
                book.stock = max(0, book.stock - row["quantity"])
                book.save(update_fields=["stock"])

            if applied_coupon:
                applied_coupon.used_count += 1
                applied_coupon.save(update_fields=["used_count"])

            _set_cart(request, {})
            
            if order.payment_method != "cod":
                return redirect("payment_gateway", pk=order.pk)

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
@require_POST
def api_apply_coupon(request):
    """AJAX API to validate and calculate coupon discount."""
    coupon_code = request.POST.get("code", "").strip()
    subtotal = float(request.POST.get("subtotal", 0))
    
    try:
        coupon = Coupon.objects.get(code__iexact=coupon_code)
        if not coupon.is_valid:
            return JsonResponse({"status": "error", "message": "Mã giảm giá đã hết hạn hoặc hết lượt dùng."})
        
        if subtotal < float(coupon.min_order_amount):
            return JsonResponse({
                "status": "error", 
                "message": f"Đơn hàng tối thiểu {coupon.min_order_amount:,.0f}₫ để dùng mã này."
            })
            
        final_total = float(coupon.apply_discount(subtotal))
        discount = subtotal - final_total
        
        return JsonResponse({
            "status": "ok",
            "message": f"Áp dụng thành công: {coupon}",
            "discount": discount,
            "final_total": final_total,
            "coupon_code": coupon.code
        })
    except Coupon.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Mã giảm giá không tồn tại."})


from django.urls import reverse
from .vnpay import VNPay

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
            order.status = "confirmed"
            order.save(update_fields=["status"])
            messages.success(request, f"Thanh toán VNPay thành công cho đơn hàng #{order.pk}!")
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


@login_required
def profile(request):
    order_count = request.user.orders.count()
    wishlist_count = request.user.wishlist_items.count()
    rating_count = request.user.ratings.count()
    
    dna = _get_user_reading_dna(request.user)
    milestones = dna.get("milestones", []) if dna else []
    
    context = {
        "profile_user": request.user,
        "order_count": order_count,
        "wishlist_count": wishlist_count,
        "rating_count": rating_count,
        "milestones": milestones[:3],  # Show top 3 on profile
    }
    return render(request, "books/profile.html", context)


@login_required
def profile_edit(request):
    if request.method == "POST":
        form = ProfileEditForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Đã cập nhật thông tin.")
            return redirect("profile")
    else:
        form = ProfileEditForm(instance=request.user)
    return render(request, "books/profile_edit.html", {"form": form})


@login_required
def profile_change_password(request):
    if request.method == "POST":
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Đã đổi mật khẩu thành công.")
            return redirect("profile")
    else:
        form = PasswordChangeForm(request.user)
    return render(request, "books/profile_change_password.html", {"form": form})


# ═══════════════════════════════════════════════════════════════════
# Live Search API
# ═══════════════════════════════════════════════════════════════════


def api_search(request):
    q = request.GET.get("q", "").strip()
    if len(q) < 2:
        return JsonResponse({"results": []})
    books = Book.objects.filter(
        Q(title__icontains=q) | Q(author__icontains=q)
    )[:8]
    results = [
        {
            "id": b.pk,
            "title": b.title,
            "author": b.author,
            "price": str(b.price),
            "cover": b.cover_image or "",
            "url": f"/books/{b.pk}/",
        }
        for b in books
    ]
    return JsonResponse({"results": results})


# ═══════════════════════════════════════════════════════════════════
# Static pages
# ═══════════════════════════════════════════════════════════════════


def about(request):
    return render(request, "books/about.html")


def contact(request):
    return render(request, "books/contact.html")


def robots_txt(request):
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /dashboard/",
        "Disallow: /cart/",
        "Disallow: /checkout/",
        "Disallow: /orders/",
        "Disallow: /profile/",
        f"Sitemap: {request.build_absolute_uri(reverse('sitemap'))}",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


# ═══════════════════════════════════════════════════════════════════
# AI: Sentiment Analysis
# ═══════════════════════════════════════════════════════════════════

# Vietnamese + English positive/negative word lists for simple sentiment
_POSITIVE_WORDS = {
    "hay", "tot", "tuyet", "voi", "dep", "nhanh", "uy tin", "chat luong",
    "great", "good", "excellent", "amazing", "wonderful", "love", "best",
    "fantastic", "perfect", "recommend", "enjoyed", "beautiful", "brilliant",
    "masterpiece", "outstanding", "superb", "awesome", "incredible", "favorite",
    "exciting", "engaging", "fascinating", "captivating", "delightful", "impressive",
    "satisfying", "remarkable", "touching", "inspiring", "classic", "must-read",
    "pleased", "happy", "entertaining", "fun", "intriguing", "profound",
    "thich", "rat hay", "rat tot", "xuat sac", "dinh", "pro",
    "helpful", "informative", "insightful", "compelling", "riveting",
}
_NEGATIVE_WORDS = {
    "te", "chan", "kem", "do", "toi", "xau",
    "bad", "terrible", "awful", "horrible", "boring", "waste", "poor",
    "disappointing", "worst", "hate", "slow", "confusing", "mediocre",
    "overrated", "predictable", "dull", "weak", "annoying", "frustrating",
    "uninspired", "flat", "tedious", "unreadable", "pointless", "shallow",
    "repetitive", "forgettable", "unimpressive", "bland", "meh",
    "tham", "nham", "that vong", "khong hay", "bof",
}


def _analyze_sentiment(text):
    """Simple rule-based sentiment analysis.
    Returns: ('positive', score), ('negative', score), or ('neutral', score)
    Score is confidence from 0.0 to 1.0.
    """
    if not text:
        return "neutral", 0.5

    text_lower = text.lower()
    # Remove Vietnamese diacritics for matching
    import unicodedata
    text_ascii = unicodedata.normalize("NFD", text_lower)
    text_ascii = "".join(c for c in text_ascii if unicodedata.category(c) != "Mn")

    words = set(re.findall(r'\b\w+\b', text_ascii))
    words_orig = set(re.findall(r'\b\w+\b', text_lower))
    all_words = words | words_orig

    pos_count = len(all_words & _POSITIVE_WORDS)
    neg_count = len(all_words & _NEGATIVE_WORDS)

    total = pos_count + neg_count
    if total == 0:
        return "neutral", 0.5

    if pos_count > neg_count:
        return "positive", min(0.5 + (pos_count - neg_count) / total * 0.5, 1.0)
    elif neg_count > pos_count:
        return "negative", min(0.5 + (neg_count - pos_count) / total * 0.5, 1.0)
    return "neutral", 0.5


def _get_book_sentiment_summary(book):
    """Get sentiment distribution for a book's ratings."""
    ratings = book.ratings.exclude(comment="").exclude(comment__isnull=True)
    if not ratings.exists():
        return None

    sentiments = {"positive": 0, "negative": 0, "neutral": 0}
    for r in ratings:
        sentiment, _ = _analyze_sentiment(r.comment)
        sentiments[sentiment] += 1

    total = sum(sentiments.values())
    return {
        "positive": sentiments["positive"],
        "negative": sentiments["negative"],
        "neutral": sentiments["neutral"],
        "total": total,
        "positive_pct": round(sentiments["positive"] / total * 100) if total else 0,
        "negative_pct": round(sentiments["negative"] / total * 100) if total else 0,
        "neutral_pct": round(sentiments["neutral"] / total * 100) if total else 0,
    }


# ═══════════════════════════════════════════════════════════════════
# AI: User Reading DNA / Taste Profile
# ═══════════════════════════════════════════════════════════════════


def _get_user_reading_dna(user):
    """Analyze user's reading preferences and build a 'Reading DNA' profile."""
    orders = OrderItem.objects.filter(order__user=user).select_related("book__category", "order")
    ratings = Rating.objects.filter(user=user).select_related("book__category")

    if not orders.exists() and not ratings.exists():
        return None

    dna = {}

    # Category preferences
    cat_counter = Counter()
    for item in orders:
        if item.book.category:
            cat_counter[item.book.category.name] += item.quantity
    for r in ratings:
        if r.book.category and r.score >= 4:
            cat_counter[r.book.category.name] += r.score - 2  # weight by score

    top_categories = cat_counter.most_common(6)
    chart_categories = cat_counter.most_common(5)
    dna["chart_categories"] = {
        "labels": json.dumps([name for name, _ in chart_categories] or ["Chua co du lieu"]),
        "values": json.dumps([count for _, count in chart_categories] or [0]),
    }

    if cat_counter:
        total_cat = sum(cat_counter.values())
        dna["categories"] = [
            {"name": name, "count": count, "pct": round(count / total_cat * 100)}
            for name, count in top_categories
        ]
    else:
        dna["categories"] = []

    now = timezone.localtime()
    trend_keys = []
    for offset in range(5, -1, -1):
        month = now.month - offset
        year = now.year
        while month <= 0:
            month += 12
            year -= 1
        trend_keys.append((year, month))
    trend_counts = {key: 0 for key in trend_keys}
    for item in orders:
        created_at = timezone.localtime(item.order.created_at)
        key = (created_at.year, created_at.month)
        if key in trend_counts:
            trend_counts[key] += item.quantity
    dna["chart_trend"] = {
        "labels": json.dumps([f"{month:02d}/{year}" for year, month in trend_keys]),
        "values": json.dumps([trend_counts[key] for key in trend_keys]),
    }

    # Favorite authors
    author_counter = Counter()
    for item in orders:
        author_counter[item.book.author] += item.quantity
    for r in ratings:
        if r.score >= 4:
            author_counter[r.book.author] += 1
    dna["favorite_authors"] = [
        {"name": name, "count": count}
        for name, count in author_counter.most_common(5)
    ]

    # Price range preference
    prices = [float(item.book.price) for item in orders]
    if prices:
        dna["price_range"] = {
            "min": min(prices),
            "max": max(prices),
            "avg": round(sum(prices) / len(prices)),
        }
    else:
        dna["price_range"] = None

    # Average rating given
    avg_score = ratings.aggregate(avg=Avg("score"))["avg"]
    dna["avg_rating_given"] = round(avg_score, 1) if avg_score else None

    # Total books, total spent
    dna["total_books_bought"] = sum(item.quantity for item in orders)
    dna["total_spent"] = sum(float(item.price) * item.quantity for item in orders)
    dna["total_ratings"] = ratings.count()

    # Reading mood (based on category distribution)
    if dna["categories"]:
        top_cat = dna["categories"][0]["name"].lower()
        mood_map = {
            "fiction": "Dreamer",
            "mystery": "Detective",
            "romance": "Romantic",
            "science": "Explorer",
            "programming": "Builder",
            "history": "Historian",
            "fantasy": "Adventurer",
            "thriller": "Thrill-Seeker",
        }
        dna["reading_mood"] = "Bookworm"
        for key, mood in mood_map.items():
            if key in top_cat:
                dna["reading_mood"] = mood
                break
    else:
        dna["reading_mood"] = "Newcomer"

    top_cat_label = dna["categories"][0]["name"] if dna["categories"] else "nhieu the loai moi"
    dna["ai_insight"] = (
        f"Ban dang co phong cach {dna['reading_mood']} voi xu huong noi bat ve {top_cat_label}. "
        "Hay tiep tuc danh gia va mua sach de Bookie goi y ngay cang dung gu hon."
    )
    dna["milestones"] = _get_user_milestones(user, dna)
    return dna


def _get_user_milestones(user, dna):
    """Define and calculate reading milestones/achievements."""
    milestones = []
    
    # 1. Quantity milestones
    total_books = dna.get("total_books_bought", 0)
    if total_books >= 50:
        milestones.append({"id": "collector", "name": "Đại tuyển thủ", "desc": "Sở hữu trên 50 cuốn sách", "icon": "bi-trophy-fill", "color": "#FFD700"})
    elif total_books >= 20:
        milestones.append({"id": "bibliophile", "name": "Mọt sách chính hiệu", "desc": "Sở hữu trên 20 cuốn sách", "icon": "bi-book-fill", "color": "#C0C0C0"})
    elif total_books >= 5:
        milestones.append({"id": "reader", "name": "Người đọc triển vọng", "desc": "Bắt đầu xây dựng thư viện cá nhân", "icon": "bi-bookmark-star", "color": "#CD7F32"})

    # 2. Diversity milestones
    unique_cats = len(dna.get("categories", []))
    if unique_cats >= 5:
        milestones.append({"id": "polymath", "name": "Bác học đa tài", "desc": "Đọc trên 5 thể loại khác nhau", "icon": "bi-mortarboard-fill", "color": "#6C5CE7"})
    elif unique_cats >= 3:
        milestones.append({"id": "explorer", "name": "Người khám phá", "desc": "Thích trải nghiệm nhiều thể loại", "icon": "bi-compass-fill", "color": "#00B894"})

    # 3. Critic milestones
    total_ratings = dna.get("total_ratings", 0)
    if total_ratings >= 10:
        milestones.append({"id": "critic", "name": "Nhà phê bình ưu tú", "desc": "Đóng góp trên 10 đánh giá chất lượng", "icon": "bi-megaphone-fill", "color": "#FD79A8"})
    
    # 4. Big spender
    total_spent = dna.get("total_spent", 0)
    if total_spent >= 2000000:
        milestones.append({"id": "patron", "name": "Nhà bảo trợ tri thức", "desc": "Đầu tư mạnh tay cho việc đọc", "icon": "bi-gem", "color": "#0984E3"})

    return milestones


# ═══════════════════════════════════════════════════════════════════
# AI: Explainable Recommendations
# ═══════════════════════════════════════════════════════════════════


def _get_explainable_recommendations(user, limit=8):
    """Get recommended books WITH explanations for WHY each is recommended."""
    recommendations = []

    user_orders = OrderItem.objects.filter(order__user=user).select_related("book__category")
    user_ratings = Rating.objects.filter(user=user).select_related("book__category")

    bought_ids = set(user_orders.values_list("book_id", flat=True))
    rated_ids = set(user_ratings.values_list("book_id", flat=True))
    exclude_ids = bought_ids | rated_ids

    # 1. "Because you liked [Category]"
    liked_categories = {}
    for r in user_ratings.filter(score__gte=4):
        if r.book.category:
            liked_categories[r.book.category_id] = r.book.category.name
    for cat_id, cat_name in list(liked_categories.items())[:3]:
        books = (
            Book.objects.filter(category_id=cat_id)
            .exclude(pk__in=exclude_ids)
            .annotate(avg_r=Avg("ratings__score"))
            .order_by("-avg_r", "title")[:2]
        )
        for b in books:
            recommendations.append({
                "book": b,
                "reason": f"Ban thich the loai {cat_name}",
                "reason_type": "category",
                "reason_icon": "bi-tag",
            })
            exclude_ids.add(b.pk)

    # 2. "Because you bought books by [Author]"
    author_counter = Counter(item.book.author for item in user_orders)
    for author, _ in author_counter.most_common(3):
        books = (
            Book.objects.filter(author=author)
            .exclude(pk__in=exclude_ids)
            .order_by("-created_at")[:1]
        )
        for b in books:
            recommendations.append({
                "book": b,
                "reason": f"Ban da mua sach cua {author}",
                "reason_type": "author",
                "reason_icon": "bi-person-heart",
            })
            exclude_ids.add(b.pk)

    # 3. "Users with similar taste also bought"
    if bought_ids:
        similar_users = list(
            OrderItem.objects.filter(book_id__in=bought_ids)
            .exclude(order__user=user)
            .values_list("order__user", flat=True)
            .distinct()[:30]
        )
        if similar_users:
            collaborative = (
                Book.objects.filter(order_items__order__user__in=similar_users)
                .exclude(pk__in=exclude_ids)
                .annotate(buy_count=Count("order_items"))
                .order_by("-buy_count")
                .distinct()[:3]
            )
            for b in collaborative:
                recommendations.append({
                    "book": b,
                    "reason": "Nguoi dung co so thich tuong tu da mua",
                    "reason_type": "collaborative",
                    "reason_icon": "bi-people",
                })
                exclude_ids.add(b.pk)

    # 4. "Trending in your favorite categories"
    if liked_categories:
        last_30_days = timezone.now() - timedelta(days=30)
        trending = (
            Book.objects.filter(
                category_id__in=liked_categories.keys(),
                order_items__order__created_at__gte=last_30_days,
            )
            .exclude(pk__in=exclude_ids)
            .annotate(recent_sales=Count("order_items"))
            .order_by("-recent_sales")
            .distinct()[:2]
        )
        for b in trending:
            recommendations.append({
                "book": b,
                "reason": "Dang hot trong the loai ban yeu thich",
                "reason_type": "trending",
                "reason_icon": "bi-fire",
            })

    return recommendations[:limit]


# ═══════════════════════════════════════════════════════════════════
# Admin Dashboard
# ═══════════════════════════════════════════════════════════════════


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
        order.status = new_status
        order.save(update_fields=["status"])
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


@login_required
@require_POST
def cancel_order(request, pk: int):
    order = get_object_or_404(Order, pk=pk, user=request.user)
    if order.status in ("pending", "confirmed"):
        order.status = "cancelled"
        order.save(update_fields=["status"])
        # Restore stock
        for item in order.items.all():
            item.book.stock += item.quantity
            item.book.save(update_fields=["stock"])
        # Restore coupon usage
        if order.coupon:
            order.coupon.used_count = max(0, order.coupon.used_count - 1)
            order.coupon.save(update_fields=["used_count"])
        messages.success(request, f"Da huy don hang #{order.pk}.")
    else:
        messages.error(request, "Khong the huy don hang o trang thai nay.")
    return redirect("order_detail", pk=order.pk)


# ═══════════════════════════════════════════════════════════════════
# REST API
# ═══════════════════════════════════════════════════════════════════


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
# Enhanced Profile with Reading DNA
# ═══════════════════════════════════════════════════════════════════


@login_required
def reading_dna(request):
    """User's Reading DNA page — AI-analyzed reading preferences."""
    dna = _get_user_reading_dna(request.user)
    recommendations = _get_explainable_recommendations(request.user)
    
    context = {
        "dna": dna,
        "recommendations": recommendations,
        "milestones": dna.get("milestones", []) if dna else [],
    }
    return render(request, "books/reading_dna.html", context)


@login_required
def reading_history(request):
    """Show the current user's online reading progress."""
    progresses = (
        ReadingProgress.objects.filter(user=request.user)
        .select_related("book")
        .order_by("-last_read_at")
    )
    history_items = []

    for progress in progresses:
        book = progress.book
        total_pages = len(_split_reader_pages(book.content_text or ""))
        percentage = min(100, round((progress.last_page / total_pages) * 100)) if total_pages else 0
        history_items.append({
            "progress": progress,
            "book": book,
            "percentage": percentage,
            "total_pages": total_pages,
            "is_finished": progress.is_finished,
        })

    return render(request, "books/reading_history.html", {"history_items": history_items})


def _get_chat_history(request) -> list[dict[str, str]]:
    history = request.session.get("chat_history")
    if not isinstance(history, list):
        return []
    sanitized = [
        {"role": item.get("role", ""), "content": item.get("content", "")}
        for item in history
        if isinstance(item, dict)
    ]
    return sanitized


def _append_chat_history(
    request,
    history: list[dict[str, str]],
    role: str,
    content: str,
    max_turns: int,
) -> list[dict[str, str]]:
    updated = history + [{"role": role, "content": content}]
    limit = max_turns * 2
    if len(updated) > limit:
        updated = updated[-limit:]
    request.session["chat_history"] = updated
    request.session.modified = True
    return updated


def _get_last_books(request) -> list[dict[str, Any]]:
    last_books = request.session.get("chat_last_books")
    if not isinstance(last_books, list):
        return []
    sanitized = [
        {"id": item.get("id"), "title": item.get("title", "")}
        for item in last_books
        if isinstance(item, dict)
    ]
    return sanitized


def _set_last_books(request, books: list[dict[str, Any]]) -> None:
    trimmed = [
        {"id": book.get("id"), "title": book.get("title", "")}
        for book in books
        if isinstance(book, dict)
    ][:6]
    request.session["chat_last_books"] = trimmed
    request.session.modified = True


def _build_chatbot(request) -> BookieChatbot:
    config = OllamaConfig(
        base_url=settings.OLLAMA_BASE_URL,
        model=settings.OLLAMA_MODEL,
        timeout=settings.OLLAMA_TIMEOUT,
        max_tokens=settings.OLLAMA_MAX_TOKENS,
        temperature=settings.OLLAMA_TEMPERATURE,
        num_ctx=settings.OLLAMA_NUM_CTX,
    )
    client = OllamaClient(config)
    return BookieChatbot(
        user=request.user,
        client=client,
        max_turns=settings.OLLAMA_CONTEXT_TURNS,
    )


def _chatbot_rate_limit_response(request):
    limit = int(getattr(settings, "CHATBOT_RATE_LIMIT_REQUESTS", 20))
    window = int(getattr(settings, "CHATBOT_RATE_LIMIT_WINDOW", 60))
    if limit <= 0 or window <= 0:
        return None

    if request.user.is_authenticated:
        actor = f"user:{request.user.pk}"
    else:
        actor = f"ip:{request.META.get('REMOTE_ADDR', 'unknown')}"
    key = f"chatbot_rate:{actor}"

    if cache.add(key, 1, timeout=window):
        return None
    try:
        count = cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=window)
        return None

    if count > limit:
        return JsonResponse(
            {
                "error": "Bạn gửi yêu cầu quá nhanh. Vui lòng thử lại sau ít phút.",
                "retry_after": window,
            },
            status=429,
        )
    return None


def _stream_chat_payload(payload_or_generator, is_real_stream=False, chunk_size: int = 24) -> Iterable[bytes]:
    yield json.dumps({"type": "start"}, ensure_ascii=False).encode("utf-8") + b"\n"
    if is_real_stream:
        full_text = ""
        for chunk in payload_or_generator:
            full_text += chunk
            yield json.dumps({"type": "delta", "content": chunk}, ensure_ascii=False).encode("utf-8") + b"\n"
        yield json.dumps({"type": "final", "payload": {"text": full_text, "type": "text"}}, ensure_ascii=False).encode("utf-8") + b"\n"
    else:
        payload = payload_or_generator
        text = str(payload.get("text", ""))
        for i in range(0, len(text), chunk_size):
            chunk = text[i : i + chunk_size]
            yield json.dumps({"type": "delta", "content": chunk}, ensure_ascii=False).encode("utf-8") + b"\n"
        yield json.dumps({"type": "final", "payload": payload}, ensure_ascii=False).encode("utf-8") + b"\n"


def _stream_chat_payload_with_history(request, stream_gen, user_message, found_books) -> Iterable[bytes]:
    yield json.dumps({"type": "start"}, ensure_ascii=False).encode("utf-8") + b"\n"
    full_text = ""
    stream_to_user = True
    try:
        for chunk in stream_gen:
            full_text += chunk
            if stream_to_user:
                if "{" in chunk:
                    parts = chunk.split("{", 1)
                    if parts[0]:
                        yield json.dumps({"type": "delta", "content": parts[0]}, ensure_ascii=False).encode("utf-8") + b"\n"
                    stream_to_user = False
                else:
                    yield json.dumps({"type": "delta", "content": chunk}, ensure_ascii=False).encode("utf-8") + b"\n"
    except OllamaError:
        fallback_text = "Xin lỗi, Bookie đang hơi chậm. Bạn thử lại sau vài giây nhé!"
        full_text = full_text or fallback_text
        yield json.dumps({"type": "delta", "content": fallback_text}, ensure_ascii=False).encode("utf-8") + b"\n"

    # Now parse action from full_text if present
    clean_text = full_text
    parsed_action = None
    match = re.search(r"\{[\s\S]*?\}", full_text, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            clean_text = full_text[: match.start()].strip()
            if parsed and "action" in parsed:
                parsed_action = parsed
        except json.JSONDecodeError:
            pass

    bot = _build_chatbot(request)
    payload = {"text": clean_text, "type": "text"}
    
    # If there is a parsed action, execute it
    action_response = {}
    if parsed_action:
        action_response = bot._handle_action(parsed_action)
        if action_response:
            payload.update(action_response)
            # If the action response didn't specify text, use clean_text
            if "text" not in action_response or not action_response["text"]:
                payload["text"] = clean_text

    # If no action response but we have found_books (pre-fetched), fallback to book recommendations
    if not action_response and found_books:
        from .chatbot import _filter_books_by_mention
        filtered = _filter_books_by_mention(found_books, payload["text"])
        if filtered:
            payload["type"] = "books"
            payload["books"] = filtered

    yield json.dumps({"type": "final", "payload": payload}, ensure_ascii=False).encode("utf-8") + b"\n"

    history = _get_chat_history(request)
    updated = _append_chat_history(request, history, "user", user_message, settings.OLLAMA_CONTEXT_TURNS)
    
    # Use the final displayed text or clean text for history
    final_text_for_history = payload.get("text") or clean_text
    _append_chat_history(request, updated, "assistant", final_text_for_history, settings.OLLAMA_CONTEXT_TURNS)
    
    if payload.get("type") == "books":
        _set_last_books(request, payload.get("books", []))
    request.session.save()


def _split_reader_pages(content: str, max_chars: int = 1800) -> list[str]:
    """Split raw ebook text into UI-sized pages without relying on source paragraphs."""
    text = (content or "").replace("\r\n", "\n").strip()
    if not text:
        return ["Nội dung sách đang được cập nhật."]

    raw_blocks = [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]
    pages: list[str] = []
    current: list[str] = []
    current_len = 0

    def flush_current():
        nonlocal current, current_len
        if current:
            pages.append("\n\n".join(current).strip())
            current = []
            current_len = 0

    def split_long_block(block: str) -> list[str]:
        words = block.split()
        chunks: list[str] = []
        chunk: list[str] = []
        chunk_len = 0
        for word in words:
            extra = len(word) + (1 if chunk else 0)
            if chunk and chunk_len + extra > max_chars:
                chunks.append(" ".join(chunk))
                chunk = [word]
                chunk_len = len(word)
            else:
                chunk.append(word)
                chunk_len += extra
        if chunk:
            chunks.append(" ".join(chunk))
        return chunks

    for block in raw_blocks:
        block_len = len(block)
        if block_len > max_chars:
            flush_current()
            pages.extend(split_long_block(block))
            continue

        separator_len = 2 if current else 0
        if current and current_len + separator_len + block_len > max_chars:
            flush_current()

        current.append(block)
        current_len += separator_len + block_len

    flush_current()
    return pages or ["Nội dung sách đang được cập nhật."]


class ReaderHTMLSanitizer(HTMLParser):
    allowed_tags = {
        "p", "br", "strong", "em", "b", "i", "u", "h1", "h2", "h3", "h4",
        "blockquote", "img", "figure", "figcaption", "hr", "ul", "ol", "li",
    }
    void_tags = {"br", "hr", "img"}
    blocked_tags = {"script", "style", "iframe", "object", "embed", "form", "input", "button"}

    def __init__(self, base_url: str = ""):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.parts: list[str] = []
        self.block_depth = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in self.blocked_tags:
            self.block_depth += 1
            return
        if self.block_depth or tag not in self.allowed_tags:
            return

        attr_map = {name.lower(): value for name, value in attrs if value}
        safe_attrs = []
        if tag == "img":
            src = self._safe_img_src(attr_map.get("src", ""))
            if not src:
                return
            safe_attrs.append(("src", src))
            if attr_map.get("alt"):
                safe_attrs.append(("alt", attr_map["alt"][:180]))
            if attr_map.get("title"):
                safe_attrs.append(("title", attr_map["title"][:180]))

        attr_html = "".join(
            f' {name}="{html_lib.escape(value, quote=True)}"'
            for name, value in safe_attrs
        )
        self.parts.append(f"<{tag}{attr_html}>")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self.blocked_tags and self.block_depth:
            self.block_depth -= 1
            return
        if self.block_depth or tag not in self.allowed_tags or tag in self.void_tags:
            return
        self.parts.append(f"</{tag}>")

    def handle_data(self, data):
        if not self.block_depth:
            self.parts.append(html_lib.escape(data))

    def _safe_img_src(self, src: str) -> str:
        src = urljoin(self.base_url, src.strip())
        parsed = urlparse(src)
        if parsed.scheme not in {"http", "https"}:
            return ""
        return src

    def get_html(self) -> str:
        return "".join(self.parts).strip()


def _sanitize_reader_html(content: str, base_url: str = "") -> str:
    parser = ReaderHTMLSanitizer(base_url=base_url)
    parser.feed(content or "")
    parser.close()
    return parser.get_html()


def _split_reader_html_pages(content: str, max_chars: int = 2600) -> list[str]:
    html = (content or "").strip()
    if not html:
        return []
    block_pattern = re.compile(
        r"<(?:p|h[1-4]|blockquote|figure|ul|ol)\b[\s\S]*?</(?:p|h[1-4]|blockquote|figure|ul|ol)>|<img\b[^>]*>|<hr\b[^>]*>",
        re.IGNORECASE,
    )
    blocks = [match.group(0).strip() for match in block_pattern.finditer(html)]
    if not blocks:
        return [html]

    pages: list[str] = []
    current: list[str] = []
    current_len = 0
    for block in blocks:
        text_len = len(re.sub(r"<[^>]+>", "", block))
        has_image = "<img" in block.lower()
        if current and (current_len + text_len > max_chars or has_image):
            pages.append("".join(current))
            current = []
            current_len = 0
        current.append(block)
        current_len += text_len
        if has_image:
            pages.append("".join(current))
            current = []
            current_len = 0
    if current:
        pages.append("".join(current))
    return pages


def api_chatbot(request) -> JsonResponse:
    """API for Bookie Chatbot."""
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)
    limited = _chatbot_rate_limit_response(request)
    if limited:
        return limited
    
    try:
        data = json.loads(request.body)
        user_message = data.get("message", "").strip()
        
        if not user_message:
            return JsonResponse({"error": "No message provided"}, status=400)
            
        history = _get_chat_history(request)
        last_books = _get_last_books(request)
        bot = _build_chatbot(request)
        response = bot.get_response(user_message, history, last_books)
        updated = _append_chat_history(
            request,
            history,
            "user",
            user_message,
            settings.OLLAMA_CONTEXT_TURNS,
        )
        _append_chat_history(
            request,
            updated,
            "assistant",
            response.get("text", ""),
            settings.OLLAMA_CONTEXT_TURNS,
        )
        if response.get("type") == "books":
            _set_last_books(request, response.get("books", []))
        
        return JsonResponse(response)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


def api_chatbot_sync_unused(request) -> JsonResponse:
    """Legacy synchronous fallback kept out of URL routing."""
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)
    
    try:
        data = json.loads(request.body)
        user_message = data.get("message", "").strip()
        if not user_message:
            return JsonResponse({"error": "No message provided"}, status=400)
            
        history = _get_chat_history(request)
        bot = _build_chatbot(request)
        
        # 1. Xử lý phản hồi
        response = bot.get_response(user_message, history, None)
        
        # 2. Cập nhật lịch sử (User)
        updated = _append_chat_history(
            request,
            history,
            "user",
            user_message,
            settings.OLLAMA_CONTEXT_TURNS,
        )
        # 3. Cập nhật lịch sử (Assistant)
        _append_chat_history(
            request,
            updated,
            "assistant",
            response.get("text", ""),
            settings.OLLAMA_CONTEXT_TURNS,
        )
        if response.get("type") == "books":
            _set_last_books(request, response.get("books", []))
            
        return JsonResponse(response)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


def api_chatbot_stream(request) -> HttpResponse:
    """True Streaming API for Bookie Chatbot (NDJSON)."""
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)
    limited = _chatbot_rate_limit_response(request)
    if limited:
        return limited

    try:
        data = json.loads(request.body)
        user_message = data.get("message", "").strip()
        if not user_message:
            return JsonResponse({"error": "No message provided"}, status=400)

        history = _get_chat_history(request)
        bot = _build_chatbot(request)
        catalog_response = bot.get_catalog_response(user_message)
        if catalog_response:
            updated = _append_chat_history(
                request,
                history,
                "user",
                user_message,
                settings.OLLAMA_CONTEXT_TURNS,
            )
            _append_chat_history(
                request,
                updated,
                "assistant",
                catalog_response.get("text", ""),
                settings.OLLAMA_CONTEXT_TURNS,
            )
            if catalog_response.get("type") == "books":
                _set_last_books(request, catalog_response.get("books", []))
            request.session.save()
            return StreamingHttpResponse(
                _stream_chat_payload(catalog_response),
                content_type="application/x-ndjson",
            )

        found_books = bot.prepare_stream_context(user_message)
        is_fallback = False
        if not found_books and isinstance(bot, BookieChatbot):
            found_books = bot._get_fallback_books()
            is_fallback = True

        if isinstance(bot, BookieChatbot):
            prompt = bot.build_prompt(user_message, history, found_books, is_fallback=is_fallback)
        else:
            prompt = bot.build_prompt(user_message, history, found_books)
        stream_gen = bot._client.stream_generate(prompt)

        return StreamingHttpResponse(
            _stream_chat_payload_with_history(request, stream_gen, user_message, found_books),
            content_type="application/x-ndjson",
        )
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


def read_book(request, pk: int):
    book = get_object_or_404(Book, pk=pk)
    if not book.is_digital:
        messages.warning(request, "Cuốn sách này hiện chưa hỗ trợ đọc trực tuyến.")
        return redirect("book_detail", pk=pk)

    reader_content_format = "text"
    pages = []
    if book.content_html:
        pages = _split_reader_html_pages(book.content_html)
        if pages:
            reader_content_format = "html"
    if not pages:
        pages = _split_reader_pages(book.content_text or "")
    total_pages = len(pages)
    progress = None
    last_page = 1
    if request.user.is_authenticated:
        progress, _ = ReadingProgress.objects.get_or_create(user=request.user, book=book)
        last_page = progress.last_page
    current_page = min(max(1, last_page), total_pages)
    return render(
        request,
        "books/reader.html",
        {
            "book": book,
            "pages": json.dumps(pages, ensure_ascii=False),
            "total_pages": total_pages,
            "current_page": current_page,
            "progress": progress,
            "can_save_progress": request.user.is_authenticated,
            "reader_content_format": reader_content_format,
        },
    )


@login_required
@require_POST
def api_save_reading_progress(request, pk: int):
    book = get_object_or_404(Book, pk=pk)
    try:
        data = json.loads(request.body or "{}")
        page = max(1, int(data.get("page", 1)))
        finished = bool(data.get("finished", False))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        return JsonResponse({"status": "error", "message": str(exc)}, status=400)

    progress, _ = ReadingProgress.objects.get_or_create(user=request.user, book=book)
    progress.last_page = page
    progress.is_finished = finished
    progress.save(update_fields=["last_page", "is_finished", "last_read_at"])
    return JsonResponse({"status": "success"})
