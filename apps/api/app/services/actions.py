import re
from datetime import date
from typing import Dict, List, Optional, Tuple

from app.db.neo4j import get_driver
from app.services.embeddings import embed_text

def search_items(query: str, metadata_filter: Optional[Dict[str, object]], limit: int = 10) -> List[Dict[str, object]]:
    driver = get_driver()
    filters = metadata_filter or {}
    query_value = query.strip().lower()
    if not query_value:
        return []
    work_conditions, params = build_filter_conditions(filters)
    params["query"] = query_value
    params["limit"] = max(limit, 1)
    work_where = " AND ".join(["toLower(coalesce(w.title, '')) CONTAINS $query"] + work_conditions) if work_conditions else "toLower(coalesce(w.title, '')) CONTAINS $query"
    article_match = "(toLower(coalesce(a.title, '')) CONTAINS $query OR toLower(toString(a.number)) CONTAINS $query)"
    article_where = " AND ".join([article_match] + work_conditions) if work_conditions else article_match
    cypher = (
        "MATCH (w:Work) "
        f"WHERE {work_where} "
        "WITH w, "
        "CASE "
        "WHEN toLower(coalesce(w.title, '')) = $query THEN 3 "
        "WHEN toLower(coalesce(w.title, '')) STARTS WITH $query THEN 2 "
        "ELSE 1 END AS score "
        "RETURN 'work' AS kind, w.work_id AS id, w.title AS title, score "
        "UNION ALL "
        "MATCH (w:Work)-[:HAS_EXPRESSION]->(:Expression)-[:HAS_ARTICLE]->(a:Article) "
        f"WHERE {article_where} "
        "WITH a, "
        "CASE "
        "WHEN toLower(coalesce(a.title, '')) = $query THEN 3 "
        "WHEN toLower(coalesce(a.title, '')) STARTS WITH $query THEN 2 "
        "ELSE 1 END AS score "
        "RETURN 'article' AS kind, a.article_id AS id, coalesce(a.title, toString(a.number)) AS title, score "
        "ORDER BY score DESC, title ASC, id ASC "
        "LIMIT $limit"
    )
    with driver.session() as session:
        records = session.run(cypher, params).data()
    results = []
    for record in records:
        kind = record["kind"]
        component_id = record["id"]
        results.append(
            {
                "urn": f"urn:{kind}:{component_id}",
                "kind": kind,
                "component_id": component_id,
                "title": record["title"],
                "score": record["score"],
            }
        )
    return results


def resolve_temporal_scope(date_string: str) -> Dict[str, str]:
    value = date_string.strip().lower()
    today = date.today()
    if value == "current":
        return {"type": "date", "date": today.isoformat()}
    if value == "last year":
        year = today.year - 1
        return {"type": "interval", "start": f"{year}-01-01", "end": f"{year}-12-31"}
    if re.fullmatch(r"\d{4}", value):
        year = int(value)
        return {"type": "interval", "start": f"{year}-01-01", "end": f"{year}-12-31"}
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        parsed = date.fromisoformat(value)
        return {"type": "date", "date": parsed.isoformat()}
    raise ValueError("unsupported_date_format")


def get_valid_version(component_id: str, target_date: str) -> Dict[str, object]:
    kind, identifier = parse_component_id(component_id)
    query = build_valid_version_query(kind)
    try:
        target_date_value = date.fromisoformat(target_date).isoformat()
    except ValueError as exc:
        raise ValueError("invalid_target_date") from exc
    driver = get_driver()
    with driver.session() as session:
        records = session.run(
            query,
            {"identifier": identifier, "target_date": target_date_value},
        ).data()
    if not records:
        raise LookupError("expression_not_found")
    if len(records) > 1:
        raise RuntimeError("multiple_expressions_found")
    record = records[0]
    return {
        "expression_id": record["expression_id"],
        "work_id": record["work_id"],
        "valid_from": record["valid_from"],
        "valid_to": record["valid_to"],
    }


def search_text_units(expression_id: str, semantic_query: str, top_k: int = 5) -> List[Dict[str, object]]:
    driver = get_driver()
    query_value = semantic_query.strip()
    if not query_value:
        return []
    embedding = embed_text(query_value)
    vector_k = max(top_k, 1) * 3
    vector_cypher = (
        "CALL db.index.vector.queryNodes('paragraph_embedding_index', $vector_k, $embedding) "
        "YIELD node, score "
        "WITH node, score "
        "MATCH (e:Expression {expression_id: $expression_id})-[:HAS_ARTICLE]->(a:Article)-[:HAS_PARAGRAPH]->(node) "
        "OPTIONAL MATCH (e)-[:HAS_MANIFESTATION]->(m) "
        "WITH node, score, a, collect(m)[0] AS m "
        "RETURN node.paragraph_id AS paragraph_id, node.number AS paragraph_number, node.text AS text, "
        "a.article_id AS article_id, a.number AS article_number, a.title AS article_title, "
        "score AS score, m.source_url AS source_url, "
        "CASE WHEN m.published_date IS NULL THEN null ELSE toString(m.published_date) END AS published_date, "
        "m.content_type AS content_type, m.file_hash AS file_hash "
        "ORDER BY score DESC, paragraph_id ASC "
        "LIMIT $top_k"
    )
    with driver.session() as session:
        vector_results = session.run(
            vector_cypher,
            {
                "expression_id": expression_id,
                "embedding": embedding,
                "vector_k": vector_k,
                "top_k": max(top_k, 1),
            },
        ).data()
    results = normalize_paragraph_results(vector_results, expression_id, "vector")
    if len(results) >= max(top_k, 1):
        return results
    keyword_results = keyword_search(expression_id, query_value, max(top_k, 1))
    seen = {item["paragraph_id"] for item in results}
    for item in keyword_results:
        if item["paragraph_id"] in seen:
            continue
        results.append(item)
        seen.add(item["paragraph_id"])
        if len(results) >= max(top_k, 1):
            break
    return results


def keyword_search(expression_id: str, query_value: str, top_k: int) -> List[Dict[str, object]]:
    driver = get_driver()
    keyword_cypher = (
        "MATCH (e:Expression {expression_id: $expression_id})-[:HAS_ARTICLE]->(a:Article)-[:HAS_PARAGRAPH]->(p:Paragraph) "
        "WHERE toLower(p.text) CONTAINS $query "
        "OPTIONAL MATCH (e)-[:HAS_MANIFESTATION]->(m) "
        "WITH p, a, collect(m)[0] AS m "
        "RETURN p.paragraph_id AS paragraph_id, p.number AS paragraph_number, p.text AS text, "
        "a.article_id AS article_id, a.number AS article_number, a.title AS article_title, "
        "0.0 AS score, m.source_url AS source_url, "
        "CASE WHEN m.published_date IS NULL THEN null ELSE toString(m.published_date) END AS published_date, "
        "m.content_type AS content_type, m.file_hash AS file_hash "
        "ORDER BY paragraph_id ASC "
        "LIMIT $top_k"
    )
    with driver.session() as session:
        records = session.run(
            keyword_cypher,
            {"expression_id": expression_id, "query": query_value.lower(), "top_k": top_k},
        ).data()
    return normalize_paragraph_results(records, expression_id, "keyword")


def normalize_paragraph_results(records: List[Dict[str, object]], expression_id: str, mode: str) -> List[Dict[str, object]]:
    results = []
    for record in records:
        results.append(
            {
                "expression_id": expression_id,
                "paragraph_id": record["paragraph_id"],
                "paragraph_number": record["paragraph_number"],
                "text": record["text"],
                "article_id": record["article_id"],
                "article_number": record["article_number"],
                "article_title": record["article_title"],
                "score": record["score"],
                "source_url": record.get("source_url"),
                "published_date": record.get("published_date"),
                "content_type": record.get("content_type"),
                "file_hash": record.get("file_hash"),
                "retrieval_mode": mode,
            }
        )
    return results


def parse_component_id(component_id: str) -> Tuple[str, str]:
    if component_id.startswith("urn:"):
        parts = component_id.split(":", 2)
        if len(parts) == 3:
            return parts[1], parts[2]
    return "work", component_id


def build_valid_version_query(kind: str) -> str:
    match_map = {
        "work": "MATCH (w:Work {work_id: $identifier})-[:HAS_EXPRESSION]->(e:Expression)",
        "expression": "MATCH (e:Expression {expression_id: $identifier})",
        "article": "MATCH (a:Article {article_id: $identifier})<-[:HAS_ARTICLE]-(e:Expression)",
        "paragraph": "MATCH (p:Paragraph {paragraph_id: $identifier})<-[:HAS_PARAGRAPH]-(:Article)<-[:HAS_ARTICLE]-(e:Expression)",
    }
    match_clause = match_map.get(kind)
    if match_clause is None:
        match_clause = match_map["work"]
    return (
        f"{match_clause} "
        "WHERE e.valid_from <= date($target_date) "
        "AND (e.valid_to IS NULL OR e.valid_to >= date($target_date)) "
        "RETURN DISTINCT e.expression_id AS expression_id, e.work_id AS work_id, "
        "toString(e.valid_from) AS valid_from, "
        "CASE WHEN e.valid_to IS NULL THEN null ELSE toString(e.valid_to) END AS valid_to"
    )


def build_filter_conditions(filters: Dict[str, object]) -> Tuple[List[str], Dict[str, object]]:
    conditions = []
    params: Dict[str, object] = {}
    if "jurisdiction" in filters and filters["jurisdiction"]:
        conditions.append("w.jurisdiction = $jurisdiction")
        params["jurisdiction"] = filters["jurisdiction"]
    if "authority_level" in filters and filters["authority_level"] is not None:
        conditions.append("w.authority_level = $authority_level")
        params["authority_level"] = filters["authority_level"]
    if "work_id" in filters and filters["work_id"]:
        conditions.append("w.work_id = $work_id")
        params["work_id"] = filters["work_id"]
    return conditions, params
