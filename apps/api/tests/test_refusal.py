from app.services.answering import answer_question
from app.services.orchestration import run_orchestrated_query
from app.services.refusal import classify_request, refusal_message


ADVISORY_PROMPTS = [
    "Should I do X?",
    "Should we proceed with the token launch?",
    "Should our company register as a crypto-asset service provider?",
    "What should I do to stay compliant?",
    "What should we do next?",
    "Tell me what to do.",
    "Can you tell me what to do about this regulation?",
    "Do you think I should apply for a license?",
    "Do you think we should change our onboarding?",
    "Advise me on whether to halt trading.",
    "Can you advise on the best compliance path?",
    "Provide advice on our go-to-market strategy.",
    "What do you recommend for MiCA compliance?",
    "Recommend that I register in France.",
    "Recommend that we register in Germany.",
    "Is my token a security?",
    "Is my token considered a security?",
    "Is our token a security?",
    "Is this token a security?",
    "Can we bypass regulation?",
    "How to bypass regulation?",
    "Avoid regulation in the EU.",
    "How can we get around regulation?",
    "How can we work around regulation?",
    "How do we avoid compliance obligations?",
    "Should I register as a VASP?",
    "Should we register as a CASP?",
    "Should I comply with MiCA?",
    "Should we comply with MiCA?",
    "What should our company do about PSD2?",
]


INFORMATIONAL_PROMPTS = [
    "Summarize MiCA obligations for crypto-asset issuers.",
    "What are the reporting requirements under PSD2?",
    "List the key articles on stablecoins in MiCA.",
    "Explain the definition of a crypto-asset in EU law.",
    "Which authorities supervise CASPs in the EU?",
]


def test_advisory_prompts_are_refused():
    for prompt in ADVISORY_PROMPTS:
        assert classify_request(prompt) == "advisory"


def test_informational_prompts_are_allowed():
    for prompt in INFORMATIONAL_PROMPTS:
        assert classify_request(prompt) == "informational"


def test_answer_question_refuses_advisory(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("retrieval called")

    monkeypatch.setattr("app.services.answering.search_items", fail)
    result = answer_question(
        question="Should I do X?",
        role="compliance",
        as_of_date="2024-01-01",
        jurisdiction="EU",
    )
    assert result["answer"] == refusal_message()
    assert result["citations"] == []


def test_orchestrated_refusal_short_circuits(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("retrieval called")

    monkeypatch.setattr("app.services.orchestration.search_items", fail)
    result = run_orchestrated_query(
        question="Tell me what to do",
        role="compliance",
        jurisdiction="EU",
        as_of_date="2024-01-01",
    )
    assert result["answer"] == refusal_message()
    assert result["citations"] == []

