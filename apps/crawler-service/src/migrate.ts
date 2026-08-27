import { closePool, runMigrations } from './db/index.js';
import { isProductionLike, safeErrorType } from './policy.js';

// 生产迁移门控：此值必须与 db/migrations-manifest.json 的 manifestSha256 一致。
// 新增/修改迁移脚本后，必须重新计算 manifest sha256 并更新此处，否则生产迁移会拒绝执行。
// CI 建议添加校验：node -e "const m=require('./db/migrations-manifest.json');if(m.manifestSha256!==require('./src/migrate.ts'.replace('.ts','.js')))process.exit(1)"
const REVIEWED_MANIFEST_SHA256 = 'fcf560641f97ea21b5162e6aef0487caf196ee68774475e4b6b8424a0d2586c9';

function assertMaintenanceApproval(): void {
  const environment = process.env.NODE_ENV || process.env.APP_ENV || 'development';
  if (!isProductionLike(environment)) {
    throw new Error('the maintenance migrator is only for production-like release windows');
  }
  if (process.env.MIGRATION_MAINTENANCE_APPROVED !== 'true') {
    throw new Error('MIGRATION_MAINTENANCE_APPROVED=true is required');
  }
  const releaseId = process.env.RELEASE_ID || '';
  if (!/^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$/.test(releaseId)
      || /(?:yyyy|sequence|example|latest|current|unknown)/i.test(releaseId)) {
    throw new Error('a concrete RELEASE_ID is required');
  }
  if (process.env.MIGRATION_MANIFEST_SHA256 !== REVIEWED_MANIFEST_SHA256) {
    throw new Error('MIGRATION_MANIFEST_SHA256 does not match this reviewed image');
  }
}

async function main(): Promise<void> {
  assertMaintenanceApproval();
  try {
    await runMigrations({ maintenanceMode: true });
    console.log('[Migration] crawler schema maintenance completed; process will exit');
  } finally {
    await closePool();
  }
}

main().catch((error) => {
  console.error(`[Migration] operation=applyCrawlerSchema errorType=${safeErrorType(error)}`);
  process.exitCode = 1;
});
