import logging
from pathlib import Path
from typing import List

from app.db.neo4j import get_driver

logger = logging.getLogger(__name__)


def _default_migrations_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "migrations"


def _load_statements(path: Path) -> List[str]:
    content = path.read_text(encoding="utf-8")
    return [statement.strip() for statement in content.split(";") if statement.strip()]


def _is_seed_file(path: Path) -> bool:
    return "seed" in path.stem.lower()


def run_migrations(migrations_dir: Path | None = None, include_seed: bool = False) -> List[str]:
    directory = migrations_dir or _default_migrations_dir()
    if not directory.exists():
        raise FileNotFoundError(f"migration_directory_not_found:{directory}")

    files = sorted(path for path in directory.glob("*.cypher") if include_seed or not _is_seed_file(path))
    if not files:
        logger.info("no_migrations_found")
        return []

    driver = get_driver()
    applied: List[str] = []
    with driver.session() as session:
        session.run(
            "CREATE CONSTRAINT migration_id_unique IF NOT EXISTS "
            "FOR (m:_Migration) REQUIRE m.id IS UNIQUE"
        ).consume()
        existing = {
            record["id"]
            for record in session.run("MATCH (m:_Migration) RETURN m.id AS id").data()
            if record.get("id")
        }
        for file in files:
            if file.name in existing:
                continue
            statements = _load_statements(file)
            for statement in statements:
                session.run(statement).consume()
            session.run(
                "MERGE (m:_Migration {id: $id}) SET m.applied_at = datetime()",
                {"id": file.name},
            ).consume()
            applied.append(file.name)
            logger.info("migration_applied:%s", file.name)
    return applied

