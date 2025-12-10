import io
from typing import Any, Dict

try:
    import requests
    from PIL import Image, ImageEnhance, ImageOps
    import pytesseract
except Exception: 
    requests = None
    Image = None
    ImageEnhance = None
    ImageOps = None
    pytesseract = None


def analyze_image_stub(image_url: str) -> Dict[str, Any]:
    if not requests or not Image or not pytesseract:
        return _fallback_template("Missing OCR dependencies")

    try:
        buffer = _fetch_image(image_url)
        cleaned = _preprocess_image(buffer)
        text = _run_ocr(cleaned)
        template = _build_template_from_text(text)
        channel_total = sum(len(cat.get("channels", [])) for cat in template.get("categories", []))
        template["summary"] = f"{len(template.get('categories', []))} categories / {channel_total} channels (OCR)"
        return template
    except Exception as err:  
        return _fallback_template(str(err))


def _fetch_image(url: str) -> bytes:
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return resp.content


def _preprocess_image(buffer: bytes) -> bytes:
    img = Image.open(io.BytesIO(buffer)).convert("L")
    if img.width > 1400:
        ratio = 1400 / float(img.width)
        img = img.resize((1400, int(img.height * ratio)))
    img = ImageOps.autocontrast(img)
    img = ImageEnhance.Contrast(img).enhance(1.2)
    return _to_bytes(img)


def _to_bytes(image: "Image.Image") -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _run_ocr(buffer: bytes) -> str:
    img = Image.open(io.BytesIO(buffer))
    return pytesseract.image_to_string(img) or ""


def _build_template_from_text(raw_text: str) -> Dict[str, Any]:
    lines = [clean_line(line) for line in raw_text.splitlines()]
    lines = [line for line in lines if line]

    template: Dict[str, Any] = {"categories": []}
    current_category: Dict[str, Any] | None = None

    for line in lines:
        if looks_like_category(line):
            current_category = {"name": normalize_name(line), "channels": []}
            template["categories"].append(current_category)
            continue

        if looks_like_channel(line):
            if current_category is None:
                current_category = {"name": "general", "channels": []}
                template["categories"].append(current_category)
            current_category["channels"].append(parse_channel(line))

    if not template["categories"]:
        return _fallback_template("No categories found")
    return template


def looks_like_channel(line: str) -> bool:
    lower = line.lower()
    return lower.startswith("#") or " #" in lower or "voice" in lower or lower.startswith("- #")


def looks_like_category(line: str) -> bool:
    lower = line.lower()
    if not lower:
        return False
    if looks_like_channel(line):
        return False
    return len(lower) < 80


def parse_channel(line: str) -> Dict[str, Any]:
    lower = line.lower()
    is_voice = "voice" in lower
    stripped = line.lstrip("- #")
    name = normalize_name(stripped)
    return {
        "name": name,
        "type": "voice" if is_voice else "text",
        "topic": suggest_description(name, is_voice),
        "private": False,
    }


def clean_line(value: str) -> str:
    return " ".join(value.split()).strip()


def normalize_name(text: str) -> str:
    trimmed = text.strip()
    if not trimmed:
        return "channel"
    return "-".join(trimmed.split()).lower()


def suggest_description(name: str, is_voice: bool) -> str:
    lower = name.lower()
    if "welcome" in lower:
        return "Welcome channel with info."
    if "rules" in lower:
        return "Server rules."
    if "announce" in lower:
        return "Announcements."
    if is_voice:
        return "Simple voice channel."
    return "Auto description from OCR."


def _fallback_template(reason: str) -> Dict[str, Any]:
    return {
        "categories": [
          {
            "name": "from-image",
            "channels": [
              {"name": "welcome", "type": "text", "topic": "Welcome channel with info.", "private": False},
              {"name": "rules", "type": "text", "topic": "Server rules.", "private": False},
              {"name": "hangout", "type": "voice", "topic": "Simple voice channel.", "private": False},
            ],
          }
        ],
        "summary": f"Fallback template ({reason})",
    }
