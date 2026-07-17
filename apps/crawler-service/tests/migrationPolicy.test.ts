import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

import { runtimeSchemaMutationsAllowed } from '../src/db/index.js';


test('runtime schema mutations default off in production and on in development', () => {
  assert.equal(runtimeSchemaMutationsAllowed('production'), false);
  assert.equal(runtimeSchemaMutationsAllowed('staging'), false);
  assert.equal(runtimeSchemaMutationsAllowed('development'), true);
  assert.equal(runtimeSchemaMutationsAllowed('test'), true);
});

test('runtime schema mutation override is explicit and fail closed', () => {
  assert.equal(runtimeSchemaMutationsAllowed('production', 'true'), false);
  assert.equal(runtimeSchemaMutationsAllowed('staging', 'TRUE'), false);
  assert.equal(runtimeSchemaMutationsAllowed('development', 'false'), false);
  assert.equal(runtimeSchemaMutationsAllowed('development', 'yes'), false);
});

test('crawler migration is file-backed, checksummed, transactional, and history-gated', () => {
  const source = readFileSync(new URL('../src/db/index.ts', import.meta.url), 'utf8');
  const migration = readFileSync(
    new URL('../migrations/V1.1__baseline_crawler_schema.sql', import.meta.url),
    'utf8',
  );

  // Multiple migrations are now supported; the file-backed read still uses readFile
  // with a migration descriptor's url and computes a sha256 checksum per file.
  assert.match(source, /readFile\([A-Za-z_$.]+\.url, 'utf8'\)/);
  assert.match(source, /createHash\('sha256'\)/);
  assert.match(source, /xianyu_schema_history/);
  assert.match(source, /await client\.query\('BEGIN'\)/);
  assert.match(source, /await client\.query\('COMMIT'\)/);
  assert.match(source, /await client\.query\('ROLLBACK'\)/);
  assert.match(source, /crawler schema version or checksum does not match/);
  assert.match(migration, /CREATE TABLE IF NOT EXISTS goofish_stores/);
  assert.equal(source.includes('CREATE TABLE IF NOT EXISTS goofish_stores'), false);
});

test('production migration is a dedicated approval-gated one-shot process', () => {
  const source = readFileSync(new URL('../src/migrate.ts', import.meta.url), 'utf8');
  const packageJson = readFileSync(new URL('../package.json', import.meta.url), 'utf8');

  assert.match(source, /MIGRATION_MAINTENANCE_APPROVED/);
  assert.match(source, /MIGRATION_MANIFEST_SHA256/);
  assert.match(source, /runMigrations\(\{ maintenanceMode: true \}\)/);
  assert.match(source, /await closePool\(\)/);
  assert.equal(source.includes('app.listen'), false);
  assert.match(packageJson, /"migrate:maintenance": "node dist\/migrate\.js"/);
});
