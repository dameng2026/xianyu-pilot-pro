import IORedis from 'ioredis';

import { assertQueueCookieEncryptionReady } from './queue/secretEnvelope.js';
import { closePool, getPool } from './db/index.js';
import { resolveRedisPasswordPolicy } from './policy.js';

async function main(): Promise<void> {
  const environment = process.env.NODE_ENV || process.env.APP_ENV || 'development';
  const redisPolicy = resolveRedisPasswordPolicy(process.env.REDIS_PASSWORD, environment);
  if (!redisPolicy.ready) throw new Error('Redis authentication configuration is invalid');
  assertQueueCookieEncryptionReady();

  const redis = new IORedis({
    host: process.env.REDIS_HOST || 'localhost',
    port: Number(process.env.REDIS_PORT || 6379),
    password: redisPolicy.token,
    connectTimeout: 3000,
    maxRetriesPerRequest: 1,
    lazyConnect: true,
    retryStrategy: () => null,
  });
  try {
    await Promise.race([
      Promise.all([getPool().query('SELECT 1'), redis.connect().then(() => redis.ping())]),
      new Promise((_, reject) => setTimeout(() => reject(new Error('healthcheck timeout')), 5000)),
    ]);
  } finally {
    await Promise.allSettled([redis.quit(), closePool()]);
  }
}

main().then(
  () => { process.exitCode = 0; },
  () => { process.exitCode = 1; },
);
