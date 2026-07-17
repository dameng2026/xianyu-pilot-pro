import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import pg from 'pg';
import { isProductionLike, safeErrorType } from '../policy.js';

const { Pool } = pg;

let pool: pg.Pool | null = null;

const CRAWLER_MIGRATIONS = [
  {
    service: 'crawler-service',
    version: '1.1',
    description: 'crawler schema baseline and legacy data normalization',
    url: new URL('../../migrations/V1.1__baseline_crawler_schema.sql', import.meta.url),
  },
  {
    service: 'crawler-service',
    version: '1.2',
    description: 'add retrying status to goofish_crawl_jobs',
    url: new URL('../../migrations/V1.2__add_retrying_status_to_crawl_jobs.sql', import.meta.url),
  },
];

// Backward-compat alias for tests that reference the baseline migration descriptor.
const CRAWLER_MIGRATION = CRAWLER_MIGRATIONS[0];

const REQUIRED_COLUMNS: Record<string, string[]> = {
  goofish_stores: ['id', 'tenant_id', 'user_id', 'store_url', 'last_crawled_at', 'created_at', 'updated_at'],
  goofish_items: [
    'id', 'tenant_id', 'store_user_id', 'item_id', 'item_key', 'title', 'description', 'price_text',
    'image_url', 'item_url', 'raw_json', 'is_active', 'last_crawl_job_id', 'first_seen_at', 'last_seen_at',
  ],
  goofish_crawl_jobs: [
    'id', 'tenant_id', 'bullmq_job_id', 'store_user_id', 'status', 'item_count', 'error_message',
    'execution_token', 'created_at', 'started_at', 'finished_at',
  ],
};

const REQUIRED_INDEXES = [
  'uk_goofish_stores_tenant_user',
  'uk_goofish_items_tenant_store_url',
  'uk_goofish_items_tenant_store_key',
  'uk_goofish_jobs_tenant_bullmq_job',
  'uk_goofish_jobs_active_store',
  'idx_goofish_items_tenant_store_user_id',
  'idx_goofish_items_active_store',
  'idx_goofish_items_last_seen_at',
  'idx_goofish_crawl_jobs_tenant_status',
  'idx_goofish_crawl_jobs_tenant_store_user_id',
];

export function runtimeSchemaMutationsAllowed(environment: string, configured?: string): boolean {
  if (isProductionLike(environment)) return false;
  if (configured === undefined || configured.trim() === '') return !isProductionLike(environment);
  return configured.trim().toLowerCase() === 'true';
}

export function getPool(): pg.Pool {
  if (!pool) {
    const environment = process.env.NODE_ENV || process.env.APP_ENV || 'development';
    let connectionString = process.env.DATABASE_URL;
    if (!connectionString) {
      const host = process.env.CRAWLER_DB_HOST || process.env.POSTGRES_HOST || 'localhost';
      const port = process.env.CRAWLER_DB_PORT || process.env.POSTGRES_PORT || '5432';
      const user = process.env.CRAWLER_DB_USER || process.env.POSTGRES_USER || 'crawler';
      const password = process.env.CRAWLER_DB_PASSWORD || process.env.POSTGRES_PASSWORD || 'crawler_pass';
      const db = process.env.CRAWLER_DB || process.env.POSTGRES_DB || 'xianyu_crawler';
      if (!isProductionLike(environment)) {
        console.warn(`[DB] DATABASE_URL 未设置，使用分项数据库配置: user=${user} host=${host} port=${port} database=${db}`);
      }
      connectionString = `postgres://${encodeURIComponent(user)}:${encodeURIComponent(password)}@${host}:${port}/${db}`;
    }

    if (isProductionLike(environment)) {
      let parsed: URL;
      try {
        parsed = new URL(connectionString);
      } catch {
        throw new Error('DATABASE_URL is invalid');
      }
      const password = decodeURIComponent(parsed.password || '');
      if (!['postgres:', 'postgresql:'].includes(parsed.protocol)
          || password.length < 32
          || /(?:crawler_pass|replace-with|placeholder|dev-only|change-me)/i.test(password)) {
        throw new Error('DATABASE_URL is unsafe for production');
      }
    }

    pool = new Pool({
      connectionString,
      max: 10,
      idleTimeoutMillis: 30000,
      connectionTimeoutMillis: 5000,
    });

    pool.on('error', (err) => {
      console.error(`[DB] operation=pool errorType=${safeErrorType(err)}`);
    });
  }
  return pool;
}

export async function runMigrations(options: { maintenanceMode?: boolean } = {}): Promise<void> {
  const p = getPool();
  const environment = process.env.NODE_ENV || process.env.APP_ENV || 'development';
  const mutationsAllowed = options.maintenanceMode === true || runtimeSchemaMutationsAllowed(
      environment,
      process.env.SCHEMA_RUNTIME_MUTATIONS_ENABLED,
    );

  // Pre-read all migration files and compute checksums so the hot path is I/O-freed.
  const migrations = await Promise.all(
    CRAWLER_MIGRATIONS.map(async (descriptor) => {
      const sql = await readFile(descriptor.url, 'utf8');
      const checksum = createHash('sha256').update(sql, 'utf8').digest('hex');
      return { descriptor, sql, checksum };
    }),
  );

  const client = await p.connect();
  try {
    await client.query("SELECT pg_advisory_lock(hashtext('xianyu_crawler_schema_v1'))");
    try {
      if (mutationsAllowed) {
        await client.query('BEGIN');
        try {
          await client.query(`
            CREATE TABLE IF NOT EXISTS xianyu_schema_history (
              service VARCHAR(80) NOT NULL,
              version VARCHAR(40) NOT NULL,
              description VARCHAR(255) NOT NULL,
              checksum CHAR(64) NOT NULL,
              installed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              installed_by TEXT NOT NULL DEFAULT CURRENT_USER,
              success BOOLEAN NOT NULL,
              PRIMARY KEY (service, version)
            )
          `);
          for (const { descriptor: CRAWLER_MIGRATION, sql, checksum } of migrations) {
            const installed = await client.query(
              'SELECT checksum, success FROM xianyu_schema_history WHERE service = $1 AND version = $2',
              [CRAWLER_MIGRATION.service, CRAWLER_MIGRATION.version],
            );
            if (installed.rowCount === 1) {
              const row = installed.rows[0];
              if (row.checksum !== checksum || row.success !== true) {
                throw new Error(`crawler migration ${CRAWLER_MIGRATION.version} history checksum or success state is invalid`);
              }
            } else {
              await client.query(sql);
              await client.query(
                `INSERT INTO xianyu_schema_history(service, version, description, checksum, success)
                 VALUES ($1, $2, $3, $4, TRUE)`,
                [CRAWLER_MIGRATION.service, CRAWLER_MIGRATION.version, CRAWLER_MIGRATION.description, checksum],
              );
            }
          }
          await client.query('COMMIT');
        } catch (error) {
          await client.query('ROLLBACK');
          throw error;
        }
      } else {
        const historyTable = await client.query(
          "SELECT to_regclass('public.xianyu_schema_history') AS table_name",
        );
        if (!historyTable.rows[0]?.table_name) {
          throw new Error('crawler schema history is missing; run the reviewed migration maintenance window first');
        }
        for (const { descriptor: CRAWLER_MIGRATION, checksum } of migrations) {
          const installed = await client.query(
            'SELECT checksum, success FROM xianyu_schema_history WHERE service = $1 AND version = $2',
            [CRAWLER_MIGRATION.service, CRAWLER_MIGRATION.version],
          );
          if (installed.rowCount !== 1
              || installed.rows[0]?.checksum !== checksum
              || installed.rows[0]?.success !== true) {
            throw new Error('crawler schema version or checksum does not match the reviewed release');
          }
        }
      }

      const tables = Object.keys(REQUIRED_COLUMNS);
      const columns = await client.query(
        `SELECT table_name, column_name
         FROM information_schema.columns
         WHERE table_schema = 'public' AND table_name = ANY($1::text[])`,
        [tables],
      );
      const actualColumns = new Set(columns.rows.map((row) => `${row.table_name}.${row.column_name}`));
      const missingColumns = Object.entries(REQUIRED_COLUMNS).flatMap(([table, expected]) => (
        expected.filter((column) => !actualColumns.has(`${table}.${column}`)).map((column) => `${table}.${column}`)
      ));
      if (missingColumns.length > 0) {
        throw new Error(`crawler schema is incomplete (${missingColumns.length} required column(s) missing)`);
      }
      const indexes = await client.query(
        `SELECT indexname FROM pg_indexes
         WHERE schemaname = 'public' AND indexname = ANY($1::text[])`,
        [REQUIRED_INDEXES],
      );
      const actualIndexes = new Set(indexes.rows.map((row) => String(row.indexname)));
      if (REQUIRED_INDEXES.some((index) => !actualIndexes.has(index))) {
        throw new Error('crawler schema is missing one or more required indexes');
      }
      const statusConstraint = await client.query(
        "SELECT 1 FROM pg_constraint WHERE conname = 'ck_goofish_crawl_jobs_status'",
      );
      if (statusConstraint.rowCount !== 1) {
        throw new Error('crawler schema status constraint is missing');
      }
      const unowned = await client.query(
        `SELECT
           (SELECT COUNT(*) FROM goofish_stores WHERE tenant_id = 0)
         + (SELECT COUNT(*) FROM goofish_items WHERE tenant_id = 0)
         + (SELECT COUNT(*) FROM goofish_crawl_jobs WHERE tenant_id = 0) AS total`,
      );
      const unownedCount = Number(unowned.rows[0]?.total || 0);
      if (unownedCount > 0) {
        if (isProductionLike(environment)) {
          throw new Error('legacy crawler rows with tenant_id=0 must be migrated before production startup');
        }
        console.warn(`[DB] 检测到未归属租户的旧数据: count=${unownedCount}`);
      }
    } finally {
      await client.query("SELECT pg_advisory_unlock(hashtext('xianyu_crawler_schema_v1'))");
    }
  } finally {
    client.release();
  }
  const latestVersion = CRAWLER_MIGRATIONS[CRAWLER_MIGRATIONS.length - 1].version;
  console.log(`[DB] schema ready version=${latestVersion} mutationsAllowed=${mutationsAllowed}`);
}

export async function closePool(): Promise<void> {
  if (pool) {
    await pool.end();
    pool = null;
    console.log('[DB] 连接池已关闭');
  }
}
