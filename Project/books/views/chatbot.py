from .helpers import *
from .helpers import _rate_limit_response

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
    return _rate_limit_response(
        request,
        "chatbot",
        int(getattr(settings, "CHATBOT_RATE_LIMIT_REQUESTS", 20)),
        int(getattr(settings, "CHATBOT_RATE_LIMIT_WINDOW", 60)),
        "Bạn gửi yêu cầu quá nhanh. Vui lòng thử lại sau ít phút.",
    )


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

    import books.views
    bot = books.views._build_chatbot(request)
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
        from ..chatbot import _filter_books_by_mention
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
        import books.views
        bot = books.views._build_chatbot(request)
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
        import books.views
        bot = books.views._build_chatbot(request)
        
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
        import books.views
        bot = books.views._build_chatbot(request)
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


