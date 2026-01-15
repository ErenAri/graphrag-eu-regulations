import io
import re
from typing import Tuple

from bs4 import BeautifulSoup
from pypdf import PdfReader


def parse_content(content: bytes, content_type: str, source_url: str) -> Tuple[str, str]:
    if content_type == "application/pdf" or source_url.lower().endswith(".pdf"):
        return normalize_text(extract_pdf_text(content)), "application/pdf"
    return normalize_text(extract_html_text(content)), "text/html"


def extract_html_text(content: bytes) -> str:
    soup = BeautifulSoup(content, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text("\n")
    return text


def extract_pdf_text(content: bytes) -> str:
    reader = PdfReader(io.BytesIO(content))
    parts = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        parts.append(page_text)
    return "\n".join(parts)


def normalize_text(text: str) -> str:
    text = text.replace("\r", "")
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()
