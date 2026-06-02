from __future__ import annotations

import json
import re
import unicodedata
from typing import Any, Sequence, TypedDict

from django.db.models import Count, Q

from .models import Book, Order
from .ollama_client import OllamaClient, OllamaError


class ChatMessage(TypedDict):
    role: str
    content: str


class BookieChatbot:
    """Bookie assistant with database-first catalog answers."""

    def __init__(self, user, client: OllamaClient, max_turns: int) -> None:
        self.user = user
        self._client = client
        self._max_turns = max_turns

    def _get_fallback_books(self) -> list[dict[str, Any]]:
        db_books = Book.objects.annotate(sales=Count("order_items")).order_by("-sales", "title")[:3]
        return [_format_book_result(book) for book in db_books]

    def get_response(
        self,
        text: str,
        history: Sequence[ChatMessage],
        last_books: Sequence[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        catalog_response = self.get_catalog_response(text)
        if catalog_response:
            return catalog_response

        found_books = [_format_book_result(book) for book in self._find_books(text, limit=3)]
        is_fallback = False
        if not found_books:
            found_books = self._get_fallback_books()
            is_fallback = True

        prompt = self.build_prompt(text, history, found_books, is_fallback=is_fallback)
        try:
            raw = self._client.generate(prompt)
        except Exception:
            return self._fallback_response()

        clean_text = raw
        parsed = None
        match = re.search(r"\{[\s\S]*?\}", raw, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(0))
                clean_text = raw[: match.start()].strip()
            except json.JSONDecodeError:
                pass

        if parsed and "action" in parsed:
            action_response = self._handle_action(parsed)
            if action_response:
                action_response["text"] = clean_text or action_response.get("text", "")
                return action_response

        response = {"text": clean_text or raw.strip(), "type": "text"}
        if found_books:
            filtered = _filter_books_by_mention(found_books, response["text"])
            if filtered:
                response["type"] = "books"
                response["books"] = filtered
        return response

    def get_catalog_response(self, text: str, limit: int = 3) -> dict[str, Any] | None:
        if not _looks_like_book_search(text):
            return None

        books = list(self._find_books(text, limit=limit))
        query_label = _normalize_query(text) or "yêu cầu này"
        if not books:
            return {
                "text": (
                    f"Bookie chưa tìm thấy sách nào khớp với '{query_label}' trong kho hiện tại. "
                    "Bạn thử tìm bằng chủ đề khác như Python, lập trình, khoa học, văn học hoặc trinh thám nhé."
                ),
                "type": "text",
                "quick_replies": ["Sách Python", "Sách khoa học", "Sách trinh thám"],
            }

        return {
            "text": f"Bookie tìm thấy {len(books)} sách đang có trong kho phù hợp với '{query_label}':",
            "type": "books",
            "books": [_format_book_result(book) for book in books],
        }

    def build_prompt(
        self,
        text: str,
        history: Sequence[ChatMessage],
        found_books: list[dict[str, Any]] | None = None,
        is_fallback: bool = False,
    ) -> str:
        user_name = self.user.username if self.user and self.user.is_authenticated else "Khách"
        clipped_history = list(history)[-self._max_turns * 2 :]
        history_lines = []
        for item in clipped_history:
            role = "User" if item.get("role") == "user" else "Assistant"
            content = item.get("content", "").strip()
            if content:
                history_lines.append(f"{role}: {content}")

        rules = [
            "Bạn là Bookie, trợ lý thân thiện của nhà sách Bookie.",
            f"Người dùng hiện tại: {user_name}.",
            "Trả lời ngắn gọn bằng tiếng Việt.",
            "TUYỆT ĐỐI KHÔNG ĐƯỢC TỰ BỊA RA sách, tác giả, giá cả hoặc thể loại không có trong database.",
            "Nếu người dùng hỏi mua/tìm sách, hệ thống đã xử lý bằng database trước. Bạn chỉ được phép tư vấn và gợi ý các sách thực tế có trong database dựa trên danh sách được cung cấp dưới đây.",
        ]

        if found_books:
            titles = ", ".join([f"'{book['title']}' (Giá: {book['price']}, Link: {book['url']})" for book in found_books])
            if not is_fallback:
                rules.append(f"Các sách phù hợp tìm thấy trong database: {titles}.")
                rules.append("Hãy giới thiệu các sách này cho người dùng.")
            else:
                rules.append(
                    f"Không tìm thấy sách nào khớp với yêu cầu cụ thể của người dùng trong database. "
                    f"Bạn BẮT BUỘC phải thông báo rõ là Bookie hiện chưa có sách hoặc thể loại này, "
                    f"sau đó giới thiệu cho họ các sách khác hiện đang có sẵn tại Bookie dưới đây làm gợi ý thay thế: {titles}."
                )

        # Action instructions
        action_instructions = (
            "Nếu người dùng muốn thực hiện một hành động cụ thể, hãy thêm một đối tượng JSON vào cuối câu trả lời của bạn ở định dạng: "
            "{\"action\": \"tên_hành_động\", ...}. "
            "Các hành động được hỗ trợ:\n"
            "- Tra cứu đơn hàng của tôi: {\"action\": \"order_status\"}\n"
            "- Tìm kiếm sách: {\"action\": \"search_books\", \"query\": \"từ khóa\"}\n"
            "- Gợi ý sách theo DNA/sở thích: {\"action\": \"reading_dna\"}\n"
            "- Xem sách bán chạy/phổ biến: {\"action\": \"popular_books\", \"limit\": số_lượng}\n"
            "Ví dụ: 'Để mình kiểm tra đơn hàng giúp bạn nhé. {\"action\": \"order_status\"}'"
        )
        rules.append(action_instructions)

        return (
            f"System: {' '.join(rules)}\n\n"
            f"History:\n{chr(10).join(history_lines)}\n\n"
            f"User: {text}\n\n"
            "Assistant:"
        )

    def prepare_stream_context(self, text: str) -> list[dict[str, Any]]:
        return [_format_book_result(book) for book in self._find_books(text, limit=3)]

    def _find_books(self, text: str, limit: int = 3):
        terms = _search_terms(text)
        if not terms:
            return []

        query = Q()
        for term in terms:
            query |= (
                Q(title__icontains=term)
                | Q(author__icontains=term)
                | Q(category__name__icontains=term)
                | Q(description__icontains=term)
            )

        books = list(
            Book.objects.filter(query)
            .annotate(sales=Count("order_items"))
            .order_by("-sales", "title")[:100]
        )
        scored_books = [(book, _book_relevance(book, terms)) for book in books]
        valid_books = [item for item in scored_books if item[1] > 0]
        valid_books.sort(key=lambda item: item[1], reverse=True)
        return [book for book, score in valid_books][:limit]

    def _handle_action(self, action_data: dict[str, Any]) -> dict[str, Any]:
        action = str(action_data.get("action", "")).strip().lower()
        if action == "search_books":
            query = str(action_data.get("query", "")).strip()
            limit = _coerce_int(action_data.get("limit"), default=3, min_value=1, max_value=5)
            return self._search_books(query, limit)
        if action == "order_status":
            return self._handle_order_lookup()
        if action == "reading_dna":
            return self._handle_dna_recommendation()
        if action == "popular_books":
            limit = _coerce_int(action_data.get("limit"), default=3, min_value=1, max_value=5)
            return self._popular_books(limit)
        if action == "book_details":
            return self._book_details(action_data.get("ids"))
        return {}

    def _handle_order_lookup(self) -> dict[str, Any]:
        if not self.user or not self.user.is_authenticated:
            return {
                "text": "Bạn vui lòng đăng nhập để Bookie tra cứu đơn hàng giúp bạn nhé!",
                "type": "text",
                "quick_replies": ["Đăng nhập"],
            }

        last_order = Order.objects.filter(user=self.user).order_by("-created_at").first()
        if not last_order:
            return {
                "text": "Bạn chưa có đơn hàng nào tại Bookie. Ghé kho sách để chọn một cuốn hợp gu nhé!",
                "type": "text",
                "quick_replies": ["Mua sách ngay"],
            }

        return {
            "text": (
                f"Đơn hàng gần nhất của bạn là #{last_order.pk}. "
                f"Trạng thái hiện tại: {last_order.status_display_vi}."
            ),
            "type": "text",
            "quick_replies": ["Chi tiết đơn hàng", "Mua thêm sách"],
        }

    def _search_books(self, query: str, limit: int) -> dict[str, Any]:
        cleaned = _normalize_query(query)
        if not cleaned:
            return {"text": "Bạn muốn tìm sách về chủ đề gì?", "type": "text"}

        books = list(self._find_books(query, limit=limit))
        if not books:
            return {
                "text": f"Bookie chưa thấy cuốn nào liên quan tới '{cleaned}' trong kho hiện tại.",
                "type": "text",
            }

        return {
            "text": f"Bookie tìm thấy vài cuốn phù hợp với '{cleaned}':",
            "type": "books",
            "books": [_format_book_result(book) for book in books],
        }

    def _handle_dna_recommendation(self) -> dict[str, Any]:
        if not self.user or not self.user.is_authenticated:
            return {
                "text": "Đăng nhập để Bookie phân tích DNA đọc sách và gợi ý chuẩn gu hơn nhé!",
                "type": "text",
            }

        from .views import _get_explainable_recommendations

        recommendations = _get_explainable_recommendations(self.user, limit=3)
        if not recommendations:
            return {
                "text": "Bookie cần thêm dữ liệu đọc/mua sách để hiểu gu của bạn hơn.",
                "type": "text",
                "quick_replies": ["Xem sách bán chạy"],
            }

        return {
            "text": "Dựa trên DNA đọc sách của bạn, Bookie gợi ý các cuốn này:",
            "type": "books",
            "books": [_format_book_result(rec["book"]) | {"reason": rec["reason"]} for rec in recommendations],
        }

    def _popular_books(self, limit: int) -> dict[str, Any]:
        books = (
            Book.objects.annotate(total_sold=Count("order_items"))
            .order_by("-total_sold", "title")[:limit]
        )
        return {
            "text": "Đây là những cuốn sách nổi bật hiện tại:",
            "type": "books",
            "books": [_format_book_result(book) for book in books],
        }

    def _book_details(self, ids: Any) -> dict[str, Any]:
        if not isinstance(ids, list):
            return {}
        cleaned_ids = [
            int(book_id)
            for book_id in ids
            if isinstance(book_id, (int, str)) and str(book_id).isdigit()
        ]
        if not cleaned_ids:
            return {}

        books = Book.objects.filter(pk__in=cleaned_ids)
        if not books:
            return {"text": "Bookie chưa tìm thấy thông tin cho các sách đó.", "type": "text"}

        lines = []
        for book in books:
            desc = (book.description or "Chưa có mô tả.").strip()
            lines.append(f"**{book.title}**: {desc}")
        return {"text": "\n\n".join(lines), "type": "text"}

    def _fallback_response(self) -> dict[str, Any]:
        return {
            "text": "Xin lỗi, Bookie đang gặp chút sự cố. Bạn thử lại giúp mình nhé!",
            "type": "text",
            "quick_replies": ["Tìm sách hay", "Đơn hàng của tôi", "Gợi ý cho tôi"],
        }

    def _repair_json(self, raw: str) -> dict[str, Any]:
        prompt = (
            "Chuyển nội dung sau thành JSON hợp lệ theo schema chatbot. "
            "Chỉ trả JSON, không giải thích.\n"
            f"Nội dung: {raw}"
        )
        try:
            fixed = self._client.generate(prompt)
        except OllamaError:
            return {}
        return _parse_model_output(fixed)


def _parse_model_output(raw: str) -> dict[str, Any]:
    cleaned = raw.strip()
    if not cleaned:
        return {}
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            return {}
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}


def _normalize_response(payload: dict[str, Any]) -> dict[str, Any]:
    text = str(payload.get("text", "")).strip()
    if not text:
        return {}

    response_type = str(payload.get("type", "text")).strip().lower()
    if response_type not in {"text", "books"}:
        response_type = "text"

    response: dict[str, Any] = {"text": text, "type": response_type}
    quick_replies = payload.get("quick_replies")
    if isinstance(quick_replies, list):
        replies = [str(item) for item in quick_replies if str(item).strip()]
        if replies:
            response["quick_replies"] = replies

    if response_type == "books":
        books = payload.get("books")
        if isinstance(books, list):
            response["books"] = books
        else:
            response["type"] = "text"
    return response


def _coerce_int(value: Any, default: int, min_value: int, max_value: int) -> int:
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return default
    return max(min_value, min(numeric, max_value))


def _normalize_query(query: str) -> str:
    cleaned = _strip_accents(query).lower().strip()
    cleaned = re.sub(
        r"\b(tim|sach|book|co|khong|ko|ve|cua|tac gia|muon|quyen|cuon|gia|bao|nhieu|hay|nao|dang|ban|toi|minh)\b",
        "",
        cleaned,
    )
    return re.sub(r"\s+", " ", cleaned).strip()


def _looks_like_book_search(text: str) -> bool:
    normalized = _strip_accents(text).lower()
    markers = [
        "sach",
        "book",
        "cuon",
        "quyen",
        "gia",
        "python",
        "lap trinh",
        "khung long",
        "dinosaur",
        "trinh tham",
        "khoa hoc",
        "van hoc",
    ]
    return any(marker in normalized for marker in markers)


def _search_terms(text: str) -> list[str]:
    normalized_query = _normalize_query(text)
    if not normalized_query or len(normalized_query) < 2:
        return []

    if "khung long" in normalized_query:
        return ["khủng long", "khung long", "dinosaur", "dinosaurs"]

    terms = {normalized_query}
    terms.update(token for token in normalized_query.split() if len(token) > 2)

    if "python" in terms:
        terms.update({"python", "programming", "lập trình", "lap trinh"})
    if "lap trinh" in normalized_query:
        terms.update({"programming", "lập trình"})
    if "khoa hoc" in normalized_query:
        terms.add("khoa học")
    if "trinh tham" in normalized_query:
        terms.add("trinh thám")
    if "van hoc" in normalized_query:
        terms.add("văn học")
    if "khung long" in normalized_query:
        terms.update({"khủng long", "dinosaur", "dinosaurs"})

    return [term for term in terms if len(term) > 2]


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value or "")
    without_marks = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    return without_marks.replace("đ", "d").replace("Đ", "D")


def _format_book_result(book: Book) -> dict[str, Any]:
    return {
        "id": book.pk,
        "title": book.title,
        "price": f"{book.price:,.0f}₫",
        "url": f"/books/{book.pk}/",
        "image": book.cover_image or None,
    }


def _book_relevance(book: Book, terms: list[str]) -> int:
    title = _strip_accents(book.title).lower()
    author = _strip_accents(book.author).lower()
    description = _strip_accents(book.description or "").lower()
    category = _strip_accents(book.category.name if book.category else "").lower()

    score = 0
    for term in terms:
        normalized_term = _strip_accents(term).lower()
        exact_topic_bonus = 10 if normalized_term == "python" else 1
        if _title_matches(normalized_term, title):
            score += 8 * exact_topic_bonus
        if _title_matches(normalized_term, description):
            score += 4 * exact_topic_bonus
        if _title_matches(normalized_term, author):
            score += 3
        if _title_matches(normalized_term, category):
            score += 1
    return score


def _title_matches(title: str, text: str) -> bool:
    title_clean = title.split("(")[0].split(":")[0].strip().lower()
    if not title_clean:
        return False
    if len(title_clean) <= 3:
        try:
            return bool(re.search(rf"\b{re.escape(title_clean)}\b", text.lower()))
        except Exception:
            return title_clean in text.lower()
    return title_clean in text.lower()


def _filter_books_by_mention(books: list[dict[str, Any]], text: str) -> list[dict[str, Any]]:
    if not books or not text:
        return []
    filtered = []
    for book in books:
        title = str(book.get("title", ""))
        if _title_matches(title, text):
            filtered.append(book)
    return filtered
