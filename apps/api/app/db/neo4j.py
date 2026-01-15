import logging
from typing import Optional

from neo4j import GraphDatabase, Driver

from app.core.config import get_settings


_driver: Optional[Driver] = None


def get_driver() -> Driver:
    global _driver
    if _driver is None:
        settings = get_settings()
        _driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
    return _driver


def check_ready() -> bool:
    try:
        get_driver().verify_connectivity()
        return True
    except Exception:
        logging.getLogger(__name__).exception("neo4j_connectivity_failed")
        return False


def close_driver() -> None:
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None
