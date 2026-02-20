import logging

from app.core.config import get_settings
from app.db.neo4j import get_driver

logger = logging.getLogger(__name__)


def _vector_index_statement(vector_dimensions: int, vector_similarity: str) -> str:
    return (
        "CREATE VECTOR INDEX paragraph_embedding_index IF NOT EXISTS "
        "FOR (p:Paragraph) ON (p.embedding) "
        "OPTIONS {indexConfig: {`vector.dimensions`: %d, `vector.similarity_function`: '%s'}}"
    ) % (vector_dimensions, vector_similarity)


def _current_vector_index_config(raw_options: object) -> tuple[int | None, str | None]:
    if not isinstance(raw_options, dict):
        return None, None
    raw_index_config = raw_options.get("indexConfig")
    if not isinstance(raw_index_config, dict):
        return None, None
    raw_dimension = raw_index_config.get("vector.dimensions")
    raw_similarity = raw_index_config.get("vector.similarity_function")
    dimension = int(raw_dimension) if isinstance(raw_dimension, (int, float)) else None
    similarity = str(raw_similarity) if raw_similarity is not None else None
    return dimension, similarity


def ensure_schema() -> None:
    settings = get_settings()
    vector_dimensions = settings.vector_dimensions
    vector_similarity = settings.neo4j_vector_similarity
    statements = [
        "CREATE CONSTRAINT work_id_unique IF NOT EXISTS FOR (w:Work) REQUIRE w.work_id IS UNIQUE",
        "CREATE CONSTRAINT expression_id_unique IF NOT EXISTS FOR (e:Expression) REQUIRE e.expression_id IS UNIQUE",
        "CREATE CONSTRAINT manifestation_id_unique IF NOT EXISTS FOR (m:Manifestation) REQUIRE m.manifestation_id IS UNIQUE",
        "CREATE CONSTRAINT article_id_unique IF NOT EXISTS FOR (a:Article) REQUIRE a.article_id IS UNIQUE",
        "CREATE CONSTRAINT paragraph_id_unique IF NOT EXISTS FOR (p:Paragraph) REQUIRE p.paragraph_id IS UNIQUE",
    ]
    vector_index_statement = _vector_index_statement(vector_dimensions, vector_similarity)
    driver = get_driver()
    try:
        with driver.session() as session:
            for statement in statements:
                session.run(statement).consume()
            index_record = session.run(
                "SHOW INDEXES YIELD name, options "
                "WHERE name = 'paragraph_embedding_index' "
                "RETURN options"
            ).single()
            recreate_vector_index = index_record is None
            if index_record is not None:
                current_dimensions, current_similarity = _current_vector_index_config(
                    index_record.get("options")
                )
                if (
                    current_dimensions != vector_dimensions
                    or str(current_similarity).lower() != vector_similarity.lower()
                ):
                    session.run("DROP INDEX paragraph_embedding_index IF EXISTS").consume()
                    recreate_vector_index = True
                    logger.info(
                        "neo4j_vector_index_recreated:old_dimensions=%s:new_dimensions=%s",
                        current_dimensions,
                        vector_dimensions,
                    )
            if recreate_vector_index:
                session.run(vector_index_statement).consume()
        logger.info("neo4j_schema_ready")
    except Exception:
        logger.exception("neo4j_schema_init_failed")
        raise
