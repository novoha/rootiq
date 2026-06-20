"""
extract_log skill — PDF/image -> raw text + detected error codes.

PDF text via pdfminer.six; image OCR via pytesseract (optional — degrades
gracefully if Tesseract is not installed). Error-code detection is heuristic:
uppercase tokens with underscores/digits, plus common IQAN fault patterns.
"""
import io
import re

SKILL = {
    "name": "extract_log",
    "description": "Extract raw text and PLC error codes from a PDF or image log.",
}

# Patterns that look like PLC/IQAN error codes.
_CODE_PATTERNS = [
    r"\b[A-Z]{2,}[A-Z0-9]*_[A-Z0-9_]{2,}\b",   # COUT_OVERCURRENT
    r"\b[A-Z]{3,}\d{2,}\b",                      # ERR1234 / CAN01
    r"\bE-?\d{3,}\b",                            # E-205 / E205
    r"\b(?:err(?:or)?|fault|alarm|code)\s*[:#]?\s*([A-Z0-9_\-]{3,})\b",
]


def _extract_pdf(data: bytes) -> str:
    try:
        from pdfminer.high_level import extract_text
        return extract_text(io.BytesIO(data)) or ""
    except Exception as e:  # noqa: BLE001
        return f"[extract_log] PDF extraction failed: {e}"


def _extract_image(data: bytes) -> str:
    try:
        from PIL import Image
        import pytesseract
        img = Image.open(io.BytesIO(data))
        return pytesseract.image_to_string(img) or ""
    except Exception as e:  # noqa: BLE001
        return (
            f"[extract_log] OCR unavailable or failed: {e}. "
            "Install Tesseract and pytesseract to read image logs."
        )


def detect_error_codes(text: str) -> list[str]:
    """Return a de-duplicated, order-preserving list of candidate error codes."""
    found: list[str] = []
    seen = set()
    for pat in _CODE_PATTERNS:
        for m in re.finditer(pat, text, re.IGNORECASE):
            token = (m.group(1) if m.groups() else m.group(0)).strip().upper()
            # Filter obvious noise
            if len(token) < 3 or token in seen:
                continue
            if token.isalpha() and len(token) < 5:
                continue
            seen.add(token)
            found.append(token)
    return found


def run(filename: str, data: bytes) -> dict:
    """
    Main entry point.
    Returns: {"text": str, "error_codes": [str], "filename": str}
    """
    lower = filename.lower()
    if lower.endswith(".pdf"):
        text = _extract_pdf(data)
    elif lower.endswith((".png", ".jpg", ".jpeg", ".tiff", ".bmp")):
        text = _extract_image(data)
    else:
        text = data.decode("utf-8", errors="replace")

    return {
        "filename": filename,
        "text": text,
        "error_codes": detect_error_codes(text),
    }
