-- Crawler PostgreSQL baseline. Executed transactionally by src/db/index.ts.
CREATE TABLE IF NOT EXISTS goofish_stores (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL,
  user_id TEXT NOT NULL,
  store_url TEXT NOT NULL,
  last_crawled_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS goofish_items (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL,
  store_user_id TEXT NOT NULL,
  item_id TEXT,
  item_key TEXT,
  title TEXT,
  price_text TEXT,
  image_url TEXT,
  item_url TEXT,
  raw_json JSONB,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  last_crawl_job_id TEXT,
  first_seen_at TIMESTAMP DEFAULT NOW(),
  last_seen_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS goofish_crawl_jobs (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL,
  bullmq_job_id TEXT,
  store_user_id TEXT NOT NULL,
  status TEXT NOT NULL,
  item_count INTEGER DEFAULT 0,
  error_message TEXT,
  execution_token TEXT,
  created_at TIMESTAMP DEFAULT NOW(),
  started_at TIMESTAMP,
  finished_at TIMESTAMP
);

ALTER TABLE goofish_stores ADD COLUMN IF NOT EXISTS tenant_id BIGINT NOT NULL DEFAULT 0;
ALTER TABLE goofish_items ADD COLUMN IF NOT EXISTS tenant_id BIGINT NOT NULL DEFAULT 0;
ALTER TABLE goofish_items ADD COLUMN IF NOT EXISTS item_key TEXT;
ALTER TABLE goofish_items ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE goofish_items ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE goofish_items ADD COLUMN IF NOT EXISTS last_crawl_job_id TEXT;
ALTER TABLE goofish_crawl_jobs ADD COLUMN IF NOT EXISTS tenant_id BIGINT NOT NULL DEFAULT 0;
ALTER TABLE goofish_crawl_jobs ADD COLUMN IF NOT EXISTS execution_token TEXT;
ALTER TABLE goofish_stores ALTER COLUMN tenant_id DROP DEFAULT;
ALTER TABLE goofish_items ALTER COLUMN tenant_id DROP DEFAULT;
ALTER TABLE goofish_crawl_jobs ALTER COLUMN tenant_id DROP DEFAULT;

UPDATE goofish_items
SET item_key = COALESCE(NULLIF(item_id, ''), NULLIF(item_url, ''), md5(COALESCE(title, '') || '|' || COALESCE(price_text, '') || '|' || COALESCE(image_url, '')))
WHERE item_key IS NULL OR item_key = '';

UPDATE goofish_crawl_jobs
SET status = 'failed', error_message = '旧任务状态无效，请重新提交', finished_at = NOW(), execution_token = NULL
WHERE status NOT IN ('pending', 'running', 'completed', 'failed');

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'goofish_stores_user_id_key') THEN
    ALTER TABLE goofish_stores DROP CONSTRAINT goofish_stores_user_id_key;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'goofish_items_store_user_id_item_url_key') THEN
    ALTER TABLE goofish_items DROP CONSTRAINT goofish_items_store_user_id_item_url_key;
  END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uk_goofish_stores_tenant_user ON goofish_stores(tenant_id, user_id);
CREATE UNIQUE INDEX IF NOT EXISTS uk_goofish_items_tenant_store_url ON goofish_items(tenant_id, store_user_id, item_url);
CREATE UNIQUE INDEX IF NOT EXISTS uk_goofish_items_tenant_store_key ON goofish_items(tenant_id, store_user_id, item_key);
CREATE UNIQUE INDEX IF NOT EXISTS uk_goofish_jobs_tenant_bullmq_job ON goofish_crawl_jobs(tenant_id, bullmq_job_id);

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_goofish_crawl_jobs_status') THEN
    ALTER TABLE goofish_crawl_jobs
      ADD CONSTRAINT ck_goofish_crawl_jobs_status
      CHECK (status IN ('pending', 'running', 'completed', 'failed'));
  END IF;
END $$;

WITH ranked_active_jobs AS (
  SELECT id,
         ROW_NUMBER() OVER (PARTITION BY tenant_id, store_user_id ORDER BY created_at DESC, id DESC) AS rank
  FROM goofish_crawl_jobs
  WHERE status IN ('pending', 'running')
)
UPDATE goofish_crawl_jobs
SET status = 'failed', error_message = '重复采集任务已取消，请轮询最新任务', finished_at = NOW()
WHERE id IN (SELECT id FROM ranked_active_jobs WHERE rank > 1);

CREATE UNIQUE INDEX IF NOT EXISTS uk_goofish_jobs_active_store
  ON goofish_crawl_jobs(tenant_id, store_user_id)
  WHERE status IN ('pending', 'running');

CREATE INDEX IF NOT EXISTS idx_goofish_items_tenant_store_user_id ON goofish_items(tenant_id, store_user_id);
CREATE INDEX IF NOT EXISTS idx_goofish_items_active_store ON goofish_items(tenant_id, store_user_id, is_active);
CREATE INDEX IF NOT EXISTS idx_goofish_items_last_seen_at ON goofish_items(last_seen_at);
CREATE INDEX IF NOT EXISTS idx_goofish_crawl_jobs_tenant_status ON goofish_crawl_jobs(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_goofish_crawl_jobs_tenant_store_user_id ON goofish_crawl_jobs(tenant_id, store_user_id);
