import logging

from app.core.config import get_settings
from app.db.neo4j import get_driver

logger = logging.getLogger(__name__)


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
    vector_index = (
        "CREATE VECTOR INDEX paragraph_embedding_index IF NOT EXISTS "
        "FOR (p:Paragraph) ON (p.embedding) "
        "OPTIONS {indexConfig: {`vector.dimensions`: %d, `vector.similarity_function`: '%s'}}"
    ) % (vector_dimensions, vector_similarity)
    statements.append(vector_index)
    driver = get_driver()
    try:
        with driver.session() as session:
            for statement in statements:
                session.run(statement).consume()
        logger.info("neo4j_schema_ready")
    except Exception:
        logger.exception("neo4j_schema_init_failed")
        raise
