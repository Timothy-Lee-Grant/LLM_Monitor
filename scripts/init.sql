






-- TODO: Investigate how this is working
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS corporate_policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content TEXT NOT NULL,
    embedding VECTOR(768),
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS corporate_policies_hnsw_idx
ON corporate_policies USING hnsw (embedding vector_cosine_ops);