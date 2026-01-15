from typing import Tuple

import requests


def fetch_source(url: str) -> Tuple[bytes, str]:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    content_type = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
    return response.content, content_type
