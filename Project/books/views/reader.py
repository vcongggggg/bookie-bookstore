from .helpers import *

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


def service_worker(request):
    import os
    from django.http import Http404
    sw_path = os.path.join(settings.BASE_DIR, 'static', 'js', 'service-worker.js')
    try:
        with open(sw_path, 'r', encoding='utf-8') as f:
            content = f.read()
        response = HttpResponse(content, content_type='application/javascript')
        response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return response
    except IOError:
        raise Http404("Service Worker not found")


def manifest_json(request):
    import os
    from django.http import Http404
    manifest_path = os.path.join(settings.BASE_DIR, 'static', 'manifest.json')
    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return HttpResponse(content, content_type='application/json')
    except IOError:
        raise Http404("Manifest not found")

