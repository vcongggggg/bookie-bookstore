CATEGORY_DISPLAY_NAMES = {
    "classic": "Kinh điển",
    "classics": "Kinh điển",
    "cong nghe": "Công nghệ",
    "công nghệ": "Công nghệ",
    "fiction": "Văn học",
    "it": "Công nghệ",
    "kinh dien": "Kinh điển",
    "kinh điển": "Kinh điển",
    "mystery": "Trinh thám",
    "programming": "Lập trình",
    "romance": "Lãng mạn",
    "science": "Khoa học",
    "khoa học": "Khoa học",
    "lãng mạn": "Lãng mạn",
    "lập trình": "Lập trình",
    "technology": "Công nghệ",
    "trinh thám": "Trinh thám",
    "văn học": "Văn học",
}


def normalize_category_name(name):
    value = (name or "").replace("_", " ").strip()
    if not value:
        return "Khác"

    normalized_key = " ".join(value.lower().split())
    return CATEGORY_DISPLAY_NAMES.get(normalized_key, value.title())
