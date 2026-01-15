from typing import Dict, List, Optional, TypedDict

from langgraph.graph import END, StateGraph

from app.services.actions import get_valid_version, resolve_temporal_scope, search_items, search_text_units
from app.services.answering import INSUFFICIENT_MESSAGE, extract_citations, generate_answer, validate_answer
from app.services.refusal import classify_request, refusal_message
from app.services.faithfulness import StubScorer


class RegulatoryState(TypedDict, total=False):
    user_question: str
    role: str
    jurisdiction: str
    as_of_date: str
    plan_steps: List[str]
    retrieved_items: List[Dict[str, object]]
    draft_answer: str
    verification_results: Dict[str, object]
    resolved_date: Optional[str]
    retrieval_attempts: int
    top_k: int
    item_limit: int
    response: Dict[str, object]


def plan_node(state: RegulatoryState) -> Dict[str, object]:
    steps = [
        "Plan",
        "Resolve Temporal Scope",
        "Retrieve Evidence",
        "Verify Citations",
        "Output Guardrail",
        "Respond",
    ]
    return {
        "plan_steps": steps,
        "retrieval_attempts": state.get("retrieval_attempts", 0),
        "retrieved_items": state.get("retrieved_items", []),
        "verification_results": state.get("verification_results", {}),
    }


def resolve_temporal_node(state: RegulatoryState) -> Dict[str, object]:
    scope = resolve_temporal_scope(state["as_of_date"])
    if scope["type"] == "date":
        resolved_date = scope["date"]
    else:
        resolved_date = scope["end"]
    verification = dict(state.get("verification_results", {}))
    verification["temporal_scope"] = scope
    verification["resolved_date"] = resolved_date
    return {"resolved_date": resolved_date, "verification_results": verification}


def retrieve_evidence_node(state: RegulatoryState) -> Dict[str, object]:
    attempt = state.get("retrieval_attempts", 0) + 1
    item_limit = state.get("item_limit", 5)
    top_k = state.get("top_k", 6) + (attempt - 1) * 2
    items = search_items(state["user_question"], {"jurisdiction": state["jurisdiction"]}, item_limit)
    retrieved_items = list(state.get("retrieved_items", []))
    verification = dict(state.get("verification_results", {}))
    if not items:
        verification["reason"] = "no_items"
        return {
            "retrieval_attempts": attempt,
            "draft_answer": INSUFFICIENT_MESSAGE,
            "retrieved_items": retrieved_items,
            "verification_results": verification,
        }
    selected_index = min(attempt - 1, len(items) - 1)
    selected = items[selected_index]
    try:
        version = get_valid_version(selected["urn"], state.get("resolved_date") or state["as_of_date"])
    except Exception:
        verification["reason"] = "version_unavailable"
        retrieved_items.append(
            {
                "attempt": attempt,
                "item": selected,
                "expression_id": None,
                "work_id": None,
                "paragraphs": [],
            }
        )
        return {
            "retrieval_attempts": attempt,
            "draft_answer": INSUFFICIENT_MESSAGE,
            "retrieved_items": retrieved_items,
            "verification_results": verification,
        }
    paragraphs = search_text_units(version["expression_id"], state["user_question"], top_k)
    paragraph_ids = [paragraph["paragraph_id"] for paragraph in paragraphs]
    if not paragraphs:
        verification["reason"] = "no_paragraphs"
        retrieved_items.append(
            {
                "attempt": attempt,
                "item": selected,
                "expression_id": version["expression_id"],
                "work_id": version["work_id"],
                "paragraphs": [],
            }
        )
        verification["retrieved_ids"] = paragraph_ids
        return {
            "retrieval_attempts": attempt,
            "draft_answer": INSUFFICIENT_MESSAGE,
            "retrieved_items": retrieved_items,
            "verification_results": verification,
        }
    answer_text, cited_ids = generate_answer(
        question=state["user_question"],
        role=state["role"],
        as_of_date=state.get("resolved_date") or state["as_of_date"],
        jurisdiction=state["jurisdiction"],
        paragraphs=paragraphs,
    )
    verification["retrieved_ids"] = paragraph_ids
    verification["citations"] = cited_ids
    retrieved_items.append(
        {
            "attempt": attempt,
            "item": selected,
            "expression_id": version["expression_id"],
            "work_id": version["work_id"],
            "paragraphs": paragraphs,
        }
    )
    return {
        "retrieval_attempts": attempt,
        "draft_answer": answer_text,
        "retrieved_items": retrieved_items,
        "verification_results": verification,
    }


def verify_citations_node(state: RegulatoryState) -> Dict[str, object]:
    verification = dict(state.get("verification_results", {}))
    retrieved_ids = set(verification.get("retrieved_ids", []))
    answer_text = state.get("draft_answer", "")
    citations_valid = False
    if answer_text and answer_text.strip() != INSUFFICIENT_MESSAGE and retrieved_ids:
        citations_valid = validate_answer(answer_text, retrieved_ids)
    verification["citations_valid"] = citations_valid
    verification["extracted_citations"] = [
        citation for citation in extract_citations(answer_text) if citation in retrieved_ids
    ]
    if not citations_valid and "reason" not in verification:
        verification["reason"] = "invalid_citations"
    return {"verification_results": verification}


def guardrail_node(state: RegulatoryState) -> Dict[str, object]:
    verification = dict(state.get("verification_results", {}))
    citations_valid = bool(verification.get("citations_valid"))
    answer_text = state.get("draft_answer", "").strip()
    retrieved_items = state.get("retrieved_items", [])
    evidence_texts = []
    if retrieved_items:
        evidence_texts = [paragraph["text"] for paragraph in retrieved_items[-1].get("paragraphs", [])]
    scorer = StubScorer()
    faithfulness_score = 0.0
    if citations_valid and answer_text and answer_text != INSUFFICIENT_MESSAGE:
        faithfulness_score = scorer.score(answer_text, evidence_texts)
    verification["faithfulness_score"] = faithfulness_score
    guardrail_passed = citations_valid and answer_text != INSUFFICIENT_MESSAGE and faithfulness_score >= 0.9
    verification["guardrail_passed"] = guardrail_passed
    if not guardrail_passed and "reason" not in verification:
        verification["reason"] = "faithfulness_score_low" if faithfulness_score < 0.9 else "guardrail_failed"
    if not guardrail_passed:
        return {"draft_answer": INSUFFICIENT_MESSAGE, "verification_results": verification}
    return {"verification_results": verification}


def respond_node(state: RegulatoryState) -> Dict[str, object]:
    verification = dict(state.get("verification_results", {}))
    attempts = state.get("retrieval_attempts", 0)
    answer_text = state.get("draft_answer", "")
    if not verification.get("guardrail_passed") or (attempts >= 3 and not verification.get("citations_valid")):
        answer_text = INSUFFICIENT_MESSAGE
    citations = []
    if answer_text.strip() != INSUFFICIENT_MESSAGE:
        citations = [
            citation
            for citation in extract_citations(answer_text)
            if citation in set(verification.get("retrieved_ids", []))
        ]
    response = {
        "answer": answer_text,
        "plan_steps": state.get("plan_steps", []),
        "retrieved_items": state.get("retrieved_items", []),
        "verification_results": verification,
        "citations": citations,
    }
    return {"response": response}


def route_after_verify(state: RegulatoryState) -> str:
    attempts = state.get("retrieval_attempts", 0)
    if state.get("verification_results", {}).get("citations_valid"):
        return "output_guardrail"
    if attempts >= 3:
        return "output_guardrail"
    return "retrieve_evidence"


def build_graph():
    graph = StateGraph(RegulatoryState)
    graph.add_node("plan", plan_node)
    graph.add_node("resolve_temporal_scope", resolve_temporal_node)
    graph.add_node("retrieve_evidence", retrieve_evidence_node)
    graph.add_node("verify_citations", verify_citations_node)
    graph.add_node("output_guardrail", guardrail_node)
    graph.add_node("respond", respond_node)
    graph.set_entry_point("plan")
    graph.add_edge("plan", "resolve_temporal_scope")
    graph.add_edge("resolve_temporal_scope", "retrieve_evidence")
    graph.add_edge("retrieve_evidence", "verify_citations")
    graph.add_conditional_edges("verify_citations", route_after_verify, {
        "retrieve_evidence": "retrieve_evidence",
        "output_guardrail": "output_guardrail",
    })
    graph.add_edge("output_guardrail", "respond")
    graph.add_edge("respond", END)
    return graph.compile()


GRAPH = build_graph()


def run_orchestrated_query(
    question: str,
    role: str,
    jurisdiction: str,
    as_of_date: str,
    top_k: int = 6,
    item_limit: int = 5,
) -> Dict[str, object]:
    if classify_request(question) == "advisory":
        return {
            "answer": refusal_message(),
            "plan_steps": [],
            "retrieved_items": [],
            "verification_results": {"reason": "advisory_refusal"},
            "citations": [],
        }
    initial_state: RegulatoryState = {
        "user_question": question,
        "role": role,
        "jurisdiction": jurisdiction,
        "as_of_date": as_of_date,
        "top_k": top_k,
        "item_limit": item_limit,
        "plan_steps": [],
        "retrieved_items": [],
        "draft_answer": "",
        "verification_results": {},
        "retrieval_attempts": 0,
    }
    result = GRAPH.invoke(initial_state)
    return result.get("response", {
        "answer": INSUFFICIENT_MESSAGE,
        "plan_steps": [],
        "retrieved_items": [],
        "verification_results": {"reason": "graph_failure"},
        "citations": [],
    })
