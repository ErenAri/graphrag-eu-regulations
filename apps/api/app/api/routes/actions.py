from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.actions import (
    get_valid_version,
    resolve_temporal_scope,
    search_items,
    search_text_units,
)
from app.services.answering import answer_question
from app.services.orchestration import run_orchestrated_query

router = APIRouter(prefix="/actions")


class MetadataFilter(BaseModel):
    jurisdiction: Optional[str] = None
    authority_level: Optional[int] = None
    work_id: Optional[str] = None


class SearchItemsRequest(BaseModel):
    query: str
    metadata_filter: Optional[MetadataFilter] = None
    limit: int = Field(default=10, ge=1, le=50)


class SearchItem(BaseModel):
    urn: str
    kind: str
    component_id: str
    title: Optional[str]
    score: float


class SearchItemsResponse(BaseModel):
    items: List[SearchItem]


class ResolveTemporalScopeRequest(BaseModel):
    date_string: str


class ResolveTemporalScopeResponse(BaseModel):
    type: str
    date: Optional[str] = None
    start: Optional[str] = None
    end: Optional[str] = None


class GetValidVersionRequest(BaseModel):
    component_id: str
    target_date: str


class GetValidVersionResponse(BaseModel):
    expression_id: str
    work_id: str
    valid_from: str
    valid_to: Optional[str]


class SearchTextUnitsRequest(BaseModel):
    expression_id: str
    semantic_query: str
    top_k: int = Field(default=5, ge=1, le=50)


class ParagraphResult(BaseModel):
    expression_id: str
    paragraph_id: str
    paragraph_number: str
    text: str
    article_id: str
    article_number: str
    article_title: Optional[str]
    score: float
    source_url: Optional[str]
    published_date: Optional[str]
    content_type: Optional[str]
    file_hash: Optional[str]
    retrieval_mode: str


class SearchTextUnitsResponse(BaseModel):
    items: List[ParagraphResult]


class AnswerRequest(BaseModel):
    question: str
    role: str
    as_of_date: str
    jurisdiction: str
    top_k: int = Field(default=6, ge=1, le=50)
    item_limit: int = Field(default=5, ge=1, le=20)


class AnswerResponse(BaseModel):
    answer: str
    expression_id: Optional[str]
    work_id: Optional[str]
    citations: List[str]
    sources: List[ParagraphResult]


class OrchestratedAnswerRequest(BaseModel):
    question: str
    role: str
    jurisdiction: str
    as_of_date: str
    top_k: int = Field(default=6, ge=1, le=50)
    item_limit: int = Field(default=5, ge=1, le=20)


class OrchestratedAnswerResponse(BaseModel):
    answer: str
    citations: List[str]
    plan_steps: List[str]
    retrieved_items: List[dict]
    verification_results: dict


@router.post("/search-items", response_model=SearchItemsResponse)
def search_items_endpoint(payload: SearchItemsRequest) -> SearchItemsResponse:
    items = search_items(
        payload.query,
        payload.metadata_filter.model_dump() if payload.metadata_filter else None,
        payload.limit,
    )
    return SearchItemsResponse(items=items)


@router.post("/resolve-temporal-scope", response_model=ResolveTemporalScopeResponse)
def resolve_temporal_scope_endpoint(payload: ResolveTemporalScopeRequest) -> ResolveTemporalScopeResponse:
    try:
        result = resolve_temporal_scope(payload.date_string)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return ResolveTemporalScopeResponse(**result)


@router.post("/get-valid-version", response_model=GetValidVersionResponse)
def get_valid_version_endpoint(payload: GetValidVersionRequest) -> GetValidVersionResponse:
    try:
        result = get_valid_version(payload.component_id, payload.target_date)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return GetValidVersionResponse(**result)


@router.post("/search-text-units", response_model=SearchTextUnitsResponse)
def search_text_units_endpoint(payload: SearchTextUnitsRequest) -> SearchTextUnitsResponse:
    items = search_text_units(payload.expression_id, payload.semantic_query, payload.top_k)
    return SearchTextUnitsResponse(items=items)


@router.post("/answer", response_model=AnswerResponse)
def answer_endpoint(payload: AnswerRequest) -> AnswerResponse:
    result = answer_question(
        question=payload.question,
        role=payload.role,
        as_of_date=payload.as_of_date,
        jurisdiction=payload.jurisdiction,
        top_k=payload.top_k,
        item_limit=payload.item_limit,
    )
    return AnswerResponse(**result)


@router.post("/answer-orchestrated", response_model=OrchestratedAnswerResponse)
def answer_orchestrated_endpoint(payload: OrchestratedAnswerRequest) -> OrchestratedAnswerResponse:
    result = run_orchestrated_query(
        question=payload.question,
        role=payload.role,
        jurisdiction=payload.jurisdiction,
        as_of_date=payload.as_of_date,
        top_k=payload.top_k,
        item_limit=payload.item_limit,
    )
    return OrchestratedAnswerResponse(**result)
