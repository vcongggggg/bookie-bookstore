from __future__ import annotations

import json
import re
from typing import Any, Iterable, Sequence, TypedDict

from django.db.models import Count, Q

from .models import Book, Order
from .ollama_client import OllamaClient, OllamaError


class ChatMessage(TypedDict):
    role: str
    content: str


class BookieChatbot:
    """LLM-powered Bookie assistant backed by Ollama."""

    def __init__(
        self,
        user,
        client: OllamaClient,
        max_turns: int,
    ) -> None:
        self.user = user
        self._client = client
        self._max_turns = max_turns

    def get_response(
        self,
        text: str,
        history: Sequence[ChatMessage],
        last_books: Sequence[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        prompt = self._build_prompt(text, history, last_books or [])
        try:
            raw = self._client.generate(prompt)
        except OllamaError:
            return self._fallback_response()

        parsed = _parse_model_output(raw)
        if not parsed:
            parsed = self._repair_json(raw)
            if not parsed:
                return self._fallback_response()

        if "action" in parsed:
            action_response = self._handle_action(parsed)
            if action_response:
                return action_response
            return self._fallback_response()

        normalized = _normalize_response(parsed)
        if not normalized:
            return self._fallback_response()
        return normalized

    def _build_prompt(
        self,
        text: str,
        history: Sequence[ChatMessage],
        last_books: Sequence[dict[str, Any]],
    ) -> str:
        user_name = self.user.username if self.user and self.user.is_authenticated else ""
        user_state = "đăng nhập" if user_name else "khách"
        clipped_history = list(history)[-self._max_turns * 2 :]
        history_lines = []
        for item in clipped_history:
            role = "User" if item.get("role") == "user" else "Assistant"
            content = item.get("content", "").strip()
            if content:
                history_lines.append(f"{role}: {content}")
        history_block = "\n".join(history_lines)

        system_prompt = (
            "Bạn là Bookie, trợ lý ảo của Smart Bookstore. "
            "Trả lời bằng tiếng Việt, thân thiện, ngắn gọn. "
            "Chỉ được xuất JSON hợp lệ, không thêm bất kỳ text nào khác. "
            "Không dùng ngôn ngữ khác ngoài tiếng Việt. "
            "Nếu câu hỏi ngoài phạm vi bookstore, hãy trả lời bình thường (type=text). "
            "Nếu cần danh sách sách, sử dụng action thay vì tự ý tưởng tượng.\n"
            "Schema hợp lệ:\n"
            "1) {\"text\": \"...\", \"type\": \"text\", \"quick_replies\": [\"...\"]}\n"
            "2) {\"action\": \"search_books\", \"query\": \"...\", \"limit\": 3}\n"
            "3) {\"action\": \"order_status\"}\n"
            "4) {\"action\": \"reading_dna\"}\n"
            "5) {\"action\": \"popular_books\", \"limit\": 3}\n"
            "6) {\"action\": \"book_details\", \"ids\": [1, 2]}\n"
            f"Trạng thái người dùng: {user_state}."
        )

        if user_name:
            system_prompt += f" Tên người dùng: {user_name}."

        prompt_parts = [system_prompt]
        if last_books:
            book_lines = [
                f"- {book.get('id')}: {book.get('title', '')}"
                for book in last_books
                if book.get("id")
            ]
            if book_lines:
                prompt_parts.append(
                    "Sách vừa gợi ý (dùng khi người dùng hỏi 'nội dung/chi tiết/giới thiệu'):\n"
                    + "\n".join(book_lines)
                )
        if history_block:
            prompt_parts.append("Lịch sử hội thoại:\n" + history_block)
        prompt_parts.append(f"User: {text}\nAssistant:")
        return "\n\n".join(prompt_parts)

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
            ids = action_data.get("ids")
            return self._book_details(ids)
        return {}

    def _handle_order_lookup(self) -> dict[str, Any]:
        if not self.user or not self.user.is_authenticated:
            return {
                "text": "Bạn vui lòng đăng nhập để Bookie có thể tra cứu đơn hàng giúp bạn nhé!",
                "type": "text",
                "quick_replies": ["Đăng nhập"],
            }

        last_order = Order.objects.filter(user=self.user).order_by("-created_at").first()
        if not last_order:
            return {
                "text": "Bạn chưa có đơn hàng nào tại Smart Bookstore. Mau mau chốt đơn để được Bookie phục vụ tận tình nhé!",
                "type": "text",
                "quick_replies": ["Mua sách ngay"],
            }

        return {
            "text": (
                f"Đơn hàng gần nhất của bạn là **#{last_order.pk}**. "
                f"Trạng thái hiện tại: **{last_order.status_display_vi}**. "
                "Cảm ơn bạn đã tin tưởng Bookie!"
            ),
            "type": "text",
            "quick_replies": ["Chi tiết đơn hàng", "Mua thêm sách"],
        }

    def _search_books(self, query: str, limit: int) -> dict[str, Any]:
        cleaned = _normalize_query(query)
        if not cleaned:
            return {
                "text": "Bạn muốn tìm sách về chủ đề gì nè? Ví dụ: 'Sách Python' hay 'Tác giả Nguyễn Nhật Ánh'.",
                "type": "text",
            }

        books = (
            Book.objects.filter(
                Q(title__icontains=cleaned)
                | Q(author__icontains=cleaned)
                | Q(category__name__icontains=cleaned)
            )
            .annotate(sales=Count("order_items"))
            .order_by("-sales")[:limit]
        )

        if not books:
            return {
                "text": f"Tiếc quá, Bookie chưa thấy cuốn nào liên quan tới '{cleaned}'. Bạn thử tìm với từ khóa khác xem sao?",
                "type": "text",
            }

        results = [
            {
                "id": book.pk,
                "title": book.title,
                "price": f"{book.price:,.0f}₫",
                "url": f"/books/{book.pk}/",
                "image": book.cover_image or None,
            }
            for book in books
        ]

        return {
            "text": f"Đã tìm thấy vài cuốn hay ho cho bạn về '{cleaned}' đây:",
            "type": "books",
            "books": results,
        }

    def _handle_dna_recommendation(self) -> dict[str, Any]:
        if not self.user or not self.user.is_authenticated:
            return {
                "text": "Đăng nhập ngay để Bookie phân tích DNA đọc sách và gợi ý 'chuẩn gu' nhất cho bạn nhé!",
                "type": "text",
            }

        from .views import _get_explainable_recommendations

        recommendations = _get_explainable_recommendations(self.user, limit=3)
        if not recommendations:
            return {
                "text": "Bookie đang nghiên cứu thêm gu của bạn. Hãy mua và đánh giá thêm vài cuốn để mình hiểu bạn hơn nhé!",
                "type": "text",
                "quick_replies": ["Xem sách bán chạy"],
            }

        results = [
            {
                "id": rec["book"].pk,
                "title": rec["book"].title,
                "price": f"{rec['book'].price:,.0f}₫",
                "url": f"/books/{rec['book'].pk}/",
                "image": rec["book"].cover_image or None,
                "reason": rec["reason"],
            }
            for rec in recommendations
        ]

        return {
            "text": "Dựa trên DNA của bạn, Bookie cá là bạn sẽ thích những cuốn này:",
            "type": "books",
            "books": results,
        }

    def _popular_books(self, limit: int) -> dict[str, Any]:
        books = (
            Book.objects.annotate(total_sold=Count("order_items"))
            .order_by("-total_sold", "title")[:limit]
        )
        results = [
            {
                "id": book.pk,
                "title": book.title,
                "price": f"{book.price:,.0f}₫",
                "url": f"/books/{book.pk}/",
                "image": book.cover_image or None,
            }
            for book in books
        ]
        return {
            "text": "Đây là những cuốn sách bán chạy nhất hiện tại:",
            "type": "books",
            "books": results,
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
            return {
                "text": "Bookie chưa tìm thấy thông tin nội dung cho các sách đó.",
                "type": "text",
            }

        lines = []
        for book in books:
            desc = (book.description or "Chưa có mô tả.").strip()
            lines.append(f"**{book.title}**: {desc}")

        return {
            "text": "\n\n".join(lines),
            "type": "text",
        }

    def _fallback_response(self) -> dict[str, Any]:
        return {
            "text": "Xin lỗi, Bookie đang gặp chút sự cố. Bạn thử lại giúp mình nhé!",
            "type": "text",
            "quick_replies": ["Tìm sách hay", "Đơn hàng của tôi", "Gợi ý cho tôi"],
        }

    def _repair_json(self, raw: str) -> dict[str, Any]:
        prompt = (
            "Hãy chuyển đổi nội dung sau thành JSON hợp lệ theo schema chatbot. "
            "Chỉ trả JSON, không kèm giải thích. "
            "Nếu không thể, trả {\"text\": \"Xin lỗi, Bookie đang gặp chút sự cố.\", \"type\": \"text\"}.\n"
            f"Noi dung: {raw}"
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
        data: dict[str, Any] = json.loads(cleaned)
        return data
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

    response: dict[str, Any] = {
        "text": text,
        "type": response_type,
    }

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
    if numeric < min_value:
        return min_value
    if numeric > max_value:
        return max_value
    return numeric


def _normalize_query(query: str) -> str:
    cleaned = query.lower().strip()
    cleaned = re.sub(r"\b(tim|sach|co|khong|ve|cua|tac gia|muon|quyen|cuon|gia|re)\b", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned
