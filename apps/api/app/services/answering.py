import concurrent.futures
import os
import re
import time
from typing import Dict, List, Optional, Tuple

from llama_index.core.prompts import PromptTemplate
from llama_index.core.query_engine import CitationQueryEngine
from llama_index.core.retrievers import BaseRetriever
from llama_index.core.schema import NodeWithScore, TextNode
from llama_index.llms.openai import OpenAI
from llama_index.llms.openai.utils import openai_modelname_to_contextsize

from app.core.config import get_settings
from app.services.actions import get_valid_version, search_items, search_text_units
from app.services.refusal import classify_request, refusal_message

INSUFFICIENT_MESSAGE = "Insufficient information from available sources."
CITATION_RE = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")


class StaticRetriever(BaseRetriever):
    def __init__(self, nodes: List[TextNode]):
        super().__init__()
        self._nodes = nodes

    def _retrieve(self, query_bundle):
        return [NodeWithScore(node=node, score=1.0) for node in self._nodes]


def answer_question(
    question: str,
    role: str,
    as_of_date: str,
    jurisdiction: str,
    top_k: int = 6,
    item_limit: int = 5,
) -> Dict[str, object]:
    if classify_request(question) == "advisory":
        return {
            "answer": refusal_message(),
            "expression_id": None,
            "work_id": None,
            "citations": [],
            "sources": [],
        }
    items = search_items(question, {"jurisdiction": jurisdiction}, item_limit)
    if not items:
        return insufficient_response()
    selected = items[0]
    try:
        version = get_valid_version(selected["urn"], as_of_date)
    except Exception:
        return insufficient_response()
    paragraphs = search_text_units(version["expression_id"], question, top_k)
    if not paragraphs:
        return insufficient_response()
    try:
        answer_text, cited_ids = generate_answer(
            question=question,
            role=role,
            as_of_date=as_of_date,
            jurisdiction=jurisdiction,
            paragraphs=paragraphs,
        )
    except RuntimeError:
        raise
    except Exception:
        return insufficient_response()
    if not answer_text:
        return insufficient_response()
    if answer_text.strip() == INSUFFICIENT_MESSAGE:
        return insufficient_response()
    return {
        "answer": answer_text,
        "expression_id": version["expression_id"],
        "work_id": version["work_id"],
        "citations": cited_ids,
        "sources": paragraphs,
    }


def generate_answer(
    question: str,
    role: str,
    as_of_date: str,
    jurisdiction: str,
    paragraphs: List[Dict[str, object]],
) -> Tuple[str, List[str]]:
    nodes = build_nodes(paragraphs)
    if not nodes:
        return "", []
    llm = build_llm()
    query_engine = CitationQueryEngine.from_args(
        retriever=StaticRetriever(nodes),
        llm=llm,
        text_qa_template=build_prompt(),
        citation_chunk_size=512,
    )
    query_text = build_query_text(question, role, as_of_date, jurisdiction)
    response = query_with_retry(query_engine, query_text)
    raw_answer = str(response)
    mapped_answer, invalid = map_citations(raw_answer, response.source_nodes)
    retrieved_ids = {paragraph["paragraph_id"] for paragraph in paragraphs}
    if invalid:
        return INSUFFICIENT_MESSAGE, []
    if not validate_answer(mapped_answer, retrieved_ids):
        return INSUFFICIENT_MESSAGE, []
    cited_ids = sorted({cid for cid in extract_citations(mapped_answer) if cid in retrieved_ids})
    return mapped_answer, cited_ids


def build_nodes(paragraphs: List[Dict[str, object]]) -> List[TextNode]:
    nodes = []
    for paragraph in paragraphs:
        metadata = {
            "paragraph_id": paragraph["paragraph_id"],
            "paragraph_number": paragraph["paragraph_number"],
            "article_id": paragraph["article_id"],
            "article_number": paragraph["article_number"],
            "article_title": paragraph.get("article_title"),
            "source_url": paragraph.get("source_url"),
            "published_date": paragraph.get("published_date"),
            "content_type": paragraph.get("content_type"),
            "file_hash": paragraph.get("file_hash"),
        }
        nodes.append(TextNode(text=paragraph["text"], id_=paragraph["paragraph_id"], metadata=metadata))
    return nodes


def build_prompt() -> PromptTemplate:
    template = (
        "You are a regulatory assistant. Use only the provided context to answer. "
        "Each paragraph in the answer must include at least one inline citation. "
        "If the answer is not supported by the context, respond with 'Insufficient information from available sources.'\n"
        "Context:\n{context_str}\n\nQuestion:\n{query_str}\n\nAnswer:\n"
    )
    return PromptTemplate(template)


def build_query_text(question: str, role: str, as_of_date: str, jurisdiction: str) -> str:
    return "\n".join(
        [
            f"Role: {role}",
            f"Jurisdiction: {jurisdiction}",
            f"As-of date: {as_of_date}",
            f"Question: {question}",
        ]
    )


def build_llm() -> OpenAI:
    settings = get_settings()
    api_key = settings.openai_api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("openai_api_key_missing")
    api_base = settings.openai_base_url or os.getenv("OPENAI_BASE_URL")
    model_name = settings.openai_model
    try:
        openai_modelname_to_contextsize(model_name)
        return OpenAI(
            model=model_name,
            temperature=0,
            api_key=api_key,
            api_base=api_base,
        )
    except ValueError:
        return OpenAI(
            model="gpt-4o-mini",
            temperature=0,
            api_key=api_key,
            api_base=api_base,
            additional_kwargs={"model": model_name},
        )


def query_with_retry(query_engine: CitationQueryEngine, query_text: str):
    settings = get_settings()
    attempts = max(1, settings.llm_max_retries + 1)
    for attempt in range(1, attempts + 1):
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(query_engine.query, query_text)
                return future.result(timeout=settings.llm_timeout_seconds)
        except concurrent.futures.TimeoutError as exc:
            if attempt >= attempts:
                raise RuntimeError("llm_timeout") from exc
        except Exception:
            if attempt >= attempts:
                raise
        time.sleep(min(0.2 * (2 ** (attempt - 1)), 2.0))


def map_citations(answer_text: str, source_nodes: Optional[List[NodeWithScore]]) -> Tuple[str, bool]:
    if not source_nodes:
        return answer_text, True
    citation_map = {}
    for index, node_with_score in enumerate(source_nodes, start=1):
        node = node_with_score.node
        paragraph_id = node.metadata.get("paragraph_id") if node.metadata else None
        citation_map[index] = paragraph_id or node.node_id
    invalid = False

    def replace(match: re.Match) -> str:
        nonlocal invalid
        numbers = [int(value) for value in re.findall(r"\d+", match.group(1))]
        paragraph_ids = []
        for number in numbers:
            paragraph_id = citation_map.get(number)
            if not paragraph_id:
                invalid = True
                return match.group(0)
            paragraph_ids.append(paragraph_id)
        return "[" + ", ".join(paragraph_ids) + "]"

    updated = CITATION_RE.sub(replace, answer_text)
    return updated, invalid


def validate_answer(answer_text: str, retrieved_ids: set[str]) -> bool:
    paragraphs = [segment.strip() for segment in answer_text.split("\n\n") if segment.strip()]
    if not paragraphs:
        return False
    for paragraph in paragraphs:
        citations = [cid for cid in extract_citations(paragraph) if cid in retrieved_ids]
        if not citations:
            return False
        for citation in extract_citations(paragraph):
            if citation not in retrieved_ids:
                return False
    return True


def extract_citations(text: str) -> List[str]:
    cited = []
    for match in re.finditer(r"\[([^\]]+)\]", text):
        parts = [part.strip() for part in match.group(1).split(",") if part.strip()]
        cited.extend(parts)
    return cited


def insufficient_response() -> Dict[str, object]:
    return {
        "answer": INSUFFICIENT_MESSAGE,
        "expression_id": None,
        "work_id": None,
        "citations": [],
        "sources": [],
    }
