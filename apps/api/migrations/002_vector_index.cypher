CREATE VECTOR INDEX paragraph_embedding_index IF NOT EXISTS FOR (p:Paragraph) ON (p.embedding) OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}};
