from .helpers import *
from django.urls import reverse
from .helpers import (
    _push_recently_viewed, _recently_viewed_books, _get_popular_books,
    _get_top_rated_books, _get_content_similar_books, _also_bought_books,
    _books_queryset
)
from .profile import _get_explainable_recommendations, _get_book_sentiment_summary, _analyze_sentiment

@ensure_csrf_cookie
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
    categories = cache.get("category_list_cache")
    if categories is None:
        categories = list(Category.objects.annotate(book_count=Count("books")).order_by("name"))
        cache.set("category_list_cache", categories, 3600)
    
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


@ensure_csrf_cookie
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


@ensure_csrf_cookie
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


@ensure_csrf_cookie
def category_list(request):
    categories = cache.get("category_list_cache")
    if categories is None:
        categories = list(Category.objects.annotate(book_count=Count("books")).order_by("name"))
        cache.set("category_list_cache", categories, 3600)
    return render(request, "books/category_list.html", {"categories": categories})


@ensure_csrf_cookie
def category_detail(request, pk: int):
    category = get_object_or_404(Category, pk=pk)
    sort = request.GET.get("sort", "title")
    qs = _books_queryset(category_id=pk, sort=sort)
    paginator = Paginator(qs, 12)
    page_num = request.GET.get("page", 1)
    page = paginator.get_page(page_num)
    context = {"category": category, "page": page, "books": page.object_list, "current_sort": sort}
    return render(request, "books/category_detail.html", context)


@ensure_csrf_cookie
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


@ensure_csrf_cookie
def about(request):
    return render(request, "books/about.html")


@ensure_csrf_cookie
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
    "tham", "nham", "that vong", "khong hay", "bof",
}


def health_check(request):
    from django.db import connections
    from django.core.cache import cache
    
    health_status = {
        "status": "healthy",
        "database": "untested",
        "cache": "untested"
    }
    
    # Check Database
    try:
        db_conn = connections['default']
        db_conn.cursor()
        health_status["database"] = "healthy"
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["database"] = f"unhealthy: {str(e)}"
        
    # Check Cache
    try:
        cache.set("health_check_key", "alive", 10)
        val = cache.get("health_check_key")
        if val == "alive":
            health_status["cache"] = "healthy"
        else:
            health_status["cache"] = "unhealthy: mismatch value"
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["cache"] = f"unhealthy: {str(e)}"
        
    status_code = 200 if health_status["status"] == "healthy" else 503
    return JsonResponse(health_status, status=status_code)



