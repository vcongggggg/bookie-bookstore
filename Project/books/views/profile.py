from .helpers import *
from .reader import _split_reader_pages

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



_POSITIVE_WORDS = {
    "hay", "tot", "tuyet", "voi", "dep", "nhanh", "uy", "tin", "chat", "luong",
    "great", "good", "excellent", "amazing", "wonderful", "love", "best",
    "fantastic", "perfect", "recommend", "enjoyed", "beautiful", "brilliant",
    "masterpiece", "outstanding", "superb", "awesome", "incredible", "favorite",
    "exciting", "engaging", "fascinating", "captivating", "delightful",
    "impressive", "satisfying", "remarkable", "touching", "inspiring",
    "classic", "pleased", "happy", "entertaining", "fun", "intriguing",
    "profound", "thich", "xuat", "sac", "dinh", "pro", "helpful",
    "informative", "insightful", "compelling", "riveting",
}

_NEGATIVE_WORDS = {
    "te", "chan", "kem", "do", "toi", "xau", "bad", "terrible", "awful",
    "horrible", "boring", "waste", "poor", "disappointing", "worst", "hate",
    "slow", "confusing", "mediocre", "overrated", "predictable", "dull",
    "weak", "annoying", "frustrating", "tham", "nham", "that", "vong",
    "khong", "bof",
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


