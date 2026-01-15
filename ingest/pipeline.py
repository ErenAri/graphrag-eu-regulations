import hashlib
import re
import unicodedata
from datetime import date
from typing import Dict, List, Optional

from ingest.chunking import split_articles, split_paragraphs
from ingest.config import get_settings
from ingest.embeddings import embed_text
from ingest.neo4j import close_driver, get_driver
from ingest.parsers import parse_content
from ingest.sources import fetch_source


def run_ingest(
    source_url: str,
    work_title: str,
    jurisdiction: str,
    authority_level: int,
    valid_from: str,
    published_date: Optional[str] = None,
    work_id: Optional[str] = None,
    expression_id: Optional[str] = None,
) -> None:
    valid_from_date = date.fromisoformat(valid_from).isoformat()
    published_date_value = None
    if published_date:
        published_date_value = date.fromisoformat(published_date).isoformat()
    content, response_type = fetch_source(source_url)
    text, content_type = parse_content(content, response_type, source_url)
    file_hash = "sha256:" + hashlib.sha256(content).hexdigest()
    slug = slugify(work_title)
    work_id_value = work_id or f"{jurisdiction}-{authority_level}-{slug}"
    expression_id_value = expression_id or f"{work_id_value}-{valid_from_date}"
    manifestation_id = f"{expression_id_value}-{file_hash[-12:]}"
    articles = build_articles(text, work_title, expression_id_value)
    persist_graph(
        work_id_value,
        work_title,
        jurisdiction,
        authority_level,
        expression_id_value,
        valid_from_date,
        None,
        manifestation_id,
        source_url,
        file_hash,
        content_type,
        published_date_value,
        articles,
    )


def build_articles(text: str, work_title: str, expression_id: str) -> List[Dict[str, object]]:
    articles = []
    for article in split_articles(text, work_title):
        number = str(article["number"]).strip()
        title = str(article["title"]).strip() if article["title"] else None
        article_id = f"{expression_id}-A{number}"
        paragraphs = []
        for paragraph in split_paragraphs(article["body"]):
            paragraph_number = str(paragraph["number"]).strip()
            text_value = paragraph["text"].strip()
            embedding = embed_text(text_value)
            paragraph_id = f"{article_id}-P{paragraph_number}"
            paragraphs.append(
                {
                    "paragraph_id": paragraph_id,
                    "number": paragraph_number,
                    "text": text_value,
                    "embedding": embedding,
                }
            )
        articles.append(
            {
                "article_id": article_id,
                "number": number,
                "title": title,
                "paragraphs": paragraphs,
            }
        )
    return articles


def persist_graph(
    work_id: str,
    work_title: str,
    jurisdiction: str,
    authority_level: int,
    expression_id: str,
    valid_from: str,
    valid_to: Optional[str],
    manifestation_id: str,
    source_url: str,
    file_hash: str,
    content_type: str,
    published_date: Optional[str],
    articles: List[Dict[str, object]],
) -> None:
    driver = get_driver()
    work_query = (
        "MERGE (w:Work {work_id: $work_id}) "
        "SET w.title = $work_title, "
        "w.authority_level = $authority_level, "
        "w.jurisdiction = $jurisdiction "
        "MERGE (e:Expression {expression_id: $expression_id}) "
        "SET e.work_id = $work_id, "
        "e.valid_from = date($valid_from), "
        "e.valid_to = CASE WHEN $valid_to IS NULL THEN null ELSE date($valid_to) END "
        "MERGE (w)-[:HAS_EXPRESSION]->(e) "
        "MERGE (m:Manifestation {manifestation_id: $manifestation_id}) "
        "SET m.expression_id = $expression_id, "
        "m.source_url = $source_url, "
        "m.file_hash = $file_hash, "
        "m.url = $source_url, "
        "m.hash = $file_hash, "
        "m.content_type = $content_type, "
        "m.published_date = CASE WHEN $published_date IS NULL THEN null ELSE date($published_date) END "
        "MERGE (e)-[:HAS_MANIFESTATION]->(m)"
    )
    article_query = (
        "MATCH (e:Expression {expression_id: $expression_id}) "
        "UNWIND $articles AS article "
        "MERGE (a:Article {article_id: article.article_id}) "
        "SET a.number = article.number, a.title = article.title "
        "MERGE (e)-[:HAS_ARTICLE]->(a) "
        "WITH a, article "
        "UNWIND article.paragraphs AS paragraph "
        "MERGE (p:Paragraph {paragraph_id: paragraph.paragraph_id}) "
        "SET p.number = paragraph.number, "
        "p.text = paragraph.text, "
        "p.embedding = paragraph.embedding "
        "MERGE (a)-[:HAS_PARAGRAPH]->(p)"
    )
    parameters = {
        "work_id": work_id,
        "work_title": work_title,
        "jurisdiction": jurisdiction,
        "authority_level": authority_level,
        "expression_id": expression_id,
        "valid_from": valid_from,
        "valid_to": valid_to,
        "manifestation_id": manifestation_id,
        "source_url": source_url,
        "file_hash": file_hash,
        "content_type": content_type,
        "published_date": published_date,
    }
    try:
        with driver.session() as session:
            session.run(work_query, parameters).consume()
            session.run(article_query, {"expression_id": expression_id, "articles": articles}).consume()
    finally:
        close_driver()


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value).strip("-")
    return cleaned.lower() or "document"
