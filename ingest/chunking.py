import re
from typing import Dict, List


ARTICLE_RE = re.compile(r"^\s*Article\s+(\d+[A-Za-z]*)\b\s*(.*)$", re.IGNORECASE)
PARA_MARK_RE = re.compile(r"^\s*\((\d+)\)\s+(.*)$")
PARA_MARK_ALT_RE = re.compile(r"^\s*(\d+)[.)]\s+(.*)$")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def split_articles(text: str, default_title: str) -> List[Dict[str, object]]:
    lines = [line.strip() for line in text.splitlines()]
    articles: List[Dict[str, object]] = []
    current = None
    i = 0
    while i < len(lines):
        line = lines[i]
        match = ARTICLE_RE.match(line)
        if match:
            if current:
                articles.append(current)
            number = match.group(1)
            title = match.group(2).strip() if match.group(2) else ""
            current = {"number": number, "title": title, "body": []}
            if not title:
                next_index = i + 1
                if next_index < len(lines):
                    next_line = lines[next_index].strip()
                    if next_line and not ARTICLE_RE.match(next_line):
                        current["title"] = next_line
                        i = next_index
            i += 1
            continue
        if current is not None:
            current["body"].append(line)
        i += 1
    if current:
        articles.append(current)
    if not articles:
        articles = [{"number": "1", "title": default_title, "body": lines}]
    return articles


def split_paragraphs(body_lines: List[str], max_chunk_chars: int = 1200) -> List[Dict[str, str]]:
    paragraphs = []
    current = None
    marker_used = False
    for line in body_lines:
        if line.strip() == "":
            if current:
                current["text_parts"].append("")
            continue
        match = PARA_MARK_RE.match(line) or PARA_MARK_ALT_RE.match(line)
        if match:
            marker_used = True
            if current:
                paragraphs.append(current)
            current = {"number": match.group(1), "text_parts": [match.group(2).strip()]}
        else:
            if current is None:
                current = {"number": None, "text_parts": [line]}
            else:
                current["text_parts"].append(line)
    if current:
        paragraphs.append(current)
    if marker_used:
        return finalize_marked_paragraphs(paragraphs)
    text = "\n".join(body_lines).strip()
    if not text:
        return []
    return semantic_chunks(text, max_chunk_chars)


def finalize_marked_paragraphs(paragraphs: List[Dict[str, object]]) -> List[Dict[str, str]]:
    finalized = []
    for index, paragraph in enumerate(paragraphs, start=1):
        number = paragraph["number"] or "0"
        parts = [part.strip() for part in paragraph["text_parts"] if part.strip()]
        text = " ".join(parts).strip()
        if text:
            finalized.append({"number": str(number), "text": text})
        elif paragraph["number"] is None:
            fallback_number = str(index)
            finalized.append({"number": fallback_number, "text": text})
    return finalized


def semantic_chunks(text: str, max_chunk_chars: int) -> List[Dict[str, str]]:
    blocks = [block.strip() for block in text.split("\n\n") if block.strip()]
    if len(blocks) > 1:
        return [
            {"number": str(index + 1), "text": block}
            for index, block in enumerate(blocks)
        ]
    sentences = [sentence.strip() for sentence in SENTENCE_SPLIT_RE.split(text) if sentence.strip()]
    if not sentences:
        return [{"number": "1", "text": text}]
    chunks = []
    current = ""
    for sentence in sentences:
        candidate = (current + " " + sentence).strip()
        if not current:
            current = sentence
            continue
        if len(candidate) <= max_chunk_chars:
            current = candidate
        else:
            chunks.append(current)
            current = sentence
    if current:
        chunks.append(current)
    return [
        {"number": str(index + 1), "text": chunk}
        for index, chunk in enumerate(chunks)
    ]
