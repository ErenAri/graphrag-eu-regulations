CREATE CONSTRAINT work_id_unique IF NOT EXISTS FOR (w:Work) REQUIRE w.work_id IS UNIQUE;
CREATE CONSTRAINT expression_id_unique IF NOT EXISTS FOR (e:Expression) REQUIRE e.expression_id IS UNIQUE;
CREATE CONSTRAINT manifestation_id_unique IF NOT EXISTS FOR (m:Manifestation) REQUIRE m.manifestation_id IS UNIQUE;
CREATE CONSTRAINT article_id_unique IF NOT EXISTS FOR (a:Article) REQUIRE a.article_id IS UNIQUE;
CREATE CONSTRAINT paragraph_id_unique IF NOT EXISTS FOR (p:Paragraph) REQUIRE p.paragraph_id IS UNIQUE;
