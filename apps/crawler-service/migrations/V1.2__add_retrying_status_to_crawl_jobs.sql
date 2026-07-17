-- Crawler V1.2: introduce 'retrying' status for BullMQ automatic retries.
--
-- Background: markCrawlJobRetrying previously reset the DB status to 'pending'
-- when a crawl job entered a BullMQ retry backoff. This caused two problems:
--   1. The retrying job was indistinguishable from a freshly submitted 'pending'
--      job, so concurrent submissions for the same store could claim it and
--      lose track of the in-flight retry.
--   2. The retrying job blocked new submissions via the partial unique index
--      but the worker's claim SQL only matched 'pending'/'running', so the
--      BullMQ retry could not reclaim its own job.
--
-- The new 'retrying' status keeps the row distinct from fresh 'pending' rows
-- while still being claimable by the worker on the next BullMQ attempt and
-- being treated as "active" by the partial unique index that prevents
-- duplicate store submissions.
--
-- This migration is non-destructive: no columns are added, no data is lost.
-- The CHECK constraint is replaced (drop + re-add) to include 'retrying',
-- and the partial unique index is recreated with the expanded WHERE clause.

-- 1. Extend the status CHECK constraint to include 'retrying'.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_goofish_crawl_jobs_status') THEN
    ALTER TABLE goofish_crawl_jobs DROP CONSTRAINT ck_goofish_crawl_jobs_status;
  END IF;
END $$;

ALTER TABLE goofish_crawl_jobs
  ADD CONSTRAINT ck_goofish_crawl_jobs_status
  CHECK (status IN ('pending', 'running', 'retrying', 'completed', 'failed'));

-- 2. Recreate the active-store partial unique index so 'retrying' is treated
--    as an active state: concurrent submissions for the same store are rejected
--    while a retry is in flight, preventing duplicate crawl jobs.
DROP INDEX IF EXISTS uk_goofish_jobs_active_store;

CREATE UNIQUE INDEX uk_goofish_jobs_active_store
  ON goofish_crawl_jobs(tenant_id, store_user_id)
  WHERE status IN ('pending', 'running', 'retrying');
