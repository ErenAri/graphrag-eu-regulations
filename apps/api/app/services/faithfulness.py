from typing import List, Protocol


class FaithfulnessScorer(Protocol):
    def score(self, answer_text: str, evidence_texts: List[str]) -> float:
        ...


class StubScorer:
    def score(self, answer_text: str, evidence_texts: List[str]) -> float:
        return 1.0


class ExternalModelScorer:
    def score(self, answer_text: str, evidence_texts: List[str]) -> float:
        return 0.0
