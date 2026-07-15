import { closePool, runMigrations } from './db/index.js';
import { isProductionLike, safeErrorType } from './policy.js';

const REVIEWED_MANIFEST_SHA256 = '1def51a91fd3402852e17a8dadb4471e6a0e5bb4092b2a37948bd2385193adf0';

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
