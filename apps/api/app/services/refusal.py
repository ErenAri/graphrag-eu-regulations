import re
from typing import List

REFUSAL_MESSAGE = "I can't provide legal or financial advice. I can summarize relevant rules with citations if you want."


def normalize_text(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def advisory_patterns() -> List[re.Pattern]:
    raw_patterns = [
        r"\bshould i\b",
        r"\bshould we\b",
        r"\bshould our\b",
        r"\bwhat should i do\b",
        r"\bwhat should we do\b",
        r"\btell me what to do\b",
        r"\bcan you tell me what to do\b",
        r"\bdo you think i should\b",
        r"\bdo you think we should\b",
        r"\badvise me\b",
        r"\bcan you advise\b",
        r"\bprovide advice\b",
        r"\bwhat do you recommend\b",
        r"\brecommend that i\b",
        r"\brecommend that we\b",
        r"\bis my token a security\b",
        r"\bis my token considered a security\b",
        r"\bis our token a security\b",
        r"\bis this token a security\b",
        r"\bbypass regulation\b",
        r"\bcan we bypass regulation\b",
        r"\bhow to bypass regulation\b",
        r"\bavoid regulation\b",
        r"\bget around regulation\b",
        r"\bwork around regulation\b",
        r"\bhow do we avoid compliance\b",
        r"\bshould i register\b",
        r"\bshould we register\b",
        r"\bshould i comply\b",
        r"\bshould we comply\b",
        r"\bwhat should our company do\b",
    ]
    return [re.compile(pattern) for pattern in raw_patterns]


ADVISORY_PATTERNS = advisory_patterns()


def classify_request(text: str) -> str:
    normalized = normalize_text(text)
    for pattern in ADVISORY_PATTERNS:
        if pattern.search(normalized):
            return "advisory"
    return "informational"


def refusal_message() -> str:
    return REFUSAL_MESSAGE

