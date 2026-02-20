from functools import lru_cache
from typing import Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from ingest.config import get_settings


@lru_cache
def get_session() -> requests.Session:
    settings = get_settings()
    retries = Retry(
        total=max(settings.http_max_retries, 0),
        backoff_factor=max(settings.http_retry_backoff_seconds, 0.0),
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["GET", "HEAD"]),
    )
    adapter = HTTPAdapter(max_retries=retries)
    session = requests.Session()
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def fetch_source(url: str) -> Tuple[bytes, str]:
    settings = get_settings()
    response = get_session().get(url, timeout=settings.http_timeout_seconds)
    response.raise_for_status()
    content_type = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
    return response.content, content_type
