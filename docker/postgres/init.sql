-- ParamX Hunter - PostgreSQL Initialization
-- Extensions for performance with millions of parameters

CREATE EXTENSION IF NOT EXISTS pg_trgm;       -- trigram search for ILIKE queries
CREATE EXTENSION IF NOT EXISTS btree_gin;     -- composite GIN indexes
CREATE EXTENSION IF NOT EXISTS pgcrypto;      -- encryption functions

-- Set sensible defaults for high-throughput workloads
ALTER SYSTEM SET shared_buffers = '512MB';
ALTER SYSTEM SET effective_cache_size = '1536MB';
ALTER SYSTEM SET maintenance_work_mem = '128MB';
ALTER SYSTEM SET work_mem = '16MB';
ALTER SYSTEM SET max_connections = '200';
ALTER SYSTEM SET random_page_cost = '1.1';   -- assume SSD storage

-- Note: Table creation handled by SQLAlchemy/Alembic migrations.
-- Additional trigram indexes for fast text search are added via migration:
--   CREATE INDEX ix_parameters_name_trgm ON parameters USING gin (name gin_trgm_ops);
--   CREATE INDEX ix_parameters_value_trgm ON parameters USING gin (value gin_trgm_ops);
--   CREATE INDEX ix_endpoints_path_trgm ON endpoints USING gin (path gin_trgm_ops);
