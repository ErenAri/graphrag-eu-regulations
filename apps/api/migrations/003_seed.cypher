MERGE (work:Work {work_id: "EU-MICA"})
SET work.title = "Markets in Crypto-Assets Regulation",
    work.authority_level = "EU",
    work.jurisdiction = "EU"
MERGE (expression:Expression {expression_id: "EU-MICA-2024"})
SET expression.work_id = work.work_id,
    expression.valid_from = date("2024-06-30"),
    expression.version_label = "2024",
    expression.published_date = date("2023-06-09")
MERGE (work)-[:HAS_EXPRESSION]->(expression)
MERGE (manifestation:Manifestation {manifestation_id: "EU-MICA-2024-EN"})
SET manifestation.expression_id = expression.expression_id,
    manifestation.source_url = "https://eur-lex.europa.eu/eli/reg/2023/1114/oj",
    manifestation.file_hash = "sha256:placeholder",
    manifestation.content_type = "application/pdf"
MERGE (article:Article {article_id: "EU-MICA-1"})
SET article.number = "1",
    article.title = "Subject matter"
MERGE (paragraph:Paragraph {paragraph_id: "EU-MICA-1-1"})
SET paragraph.number = "1",
    paragraph.text = "This Regulation lays down uniform rules for crypto-asset services."
MERGE (expression)-[:HAS_MANIFESTATION]->(manifestation)
MERGE (expression)-[:HAS_ARTICLE]->(article)
MERGE (article)-[:HAS_PARAGRAPH]->(paragraph);
