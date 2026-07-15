import assert from 'node:assert/strict';
import test from 'node:test';

import {
  assertQueueCookieEncryptionReady,
  decryptQueueCookie,
  encryptQueueCookie,
} from '../src/queue/secretEnvelope.js';

test('queue cookie envelope round-trips without retaining plaintext', () => {
  const previousEnvironment = process.env.NODE_ENV;
  const previousSecret = process.env.COOKIE_CRYPTO_SECRET;
  process.env.NODE_ENV = 'test';
  process.env.COOKIE_CRYPTO_SECRET = 'test-secret-with-at-least-thirty-two-characters';
  try {
    assertQueueCookieEncryptionReady();
    const plaintext = 'sid=private-session; token=secret-value';
    const encrypted = encryptQueueCookie(plaintext, '7:job-123');
    assert.match(encrypted, /^v2:/);
    assert.equal(encrypted.includes('private-session'), false);
    assert.equal(decryptQueueCookie(encrypted, '7:job-123'), plaintext);
    assert.throws(() => decryptQueueCookie(encrypted, '8:job-123'), /authentication/);
    assert.throws(() => decryptQueueCookie(`${encrypted.slice(0, -1)}x`, '7:job-123'), /authentication/);
    assert.equal(encryptQueueCookie('', '7:job-123'), '');
    assert.equal(decryptQueueCookie('', '7:job-123'), '');
  } finally {
    if (previousEnvironment === undefined) delete process.env.NODE_ENV;
    else process.env.NODE_ENV = previousEnvironment;
    if (previousSecret === undefined) delete process.env.COOKIE_CRYPTO_SECRET;
    else process.env.COOKIE_CRYPTO_SECRET = previousSecret;
  }
});

test('production rejects missing and placeholder queue encryption secrets', () => {
  const previousEnvironment = process.env.NODE_ENV;
  const previousSecret = process.env.COOKIE_CRYPTO_SECRET;
  process.env.NODE_ENV = 'production';
  try {
    delete process.env.COOKIE_CRYPTO_SECRET;
    assert.throws(() => assertQueueCookieEncryptionReady(), /COOKIE_CRYPTO_SECRET/);
    process.env.COOKIE_CRYPTO_SECRET = 'replace-with-cookie-secret-change-me';
    assert.throws(() => assertQueueCookieEncryptionReady(), /COOKIE_CRYPTO_SECRET/);
    process.env.NODE_ENV = 'prodcution';
    delete process.env.COOKIE_CRYPTO_SECRET;
    assert.throws(() => assertQueueCookieEncryptionReady(), /COOKIE_CRYPTO_SECRET/);
  } finally {
    if (previousEnvironment === undefined) delete process.env.NODE_ENV;
    else process.env.NODE_ENV = previousEnvironment;
    if (previousSecret === undefined) delete process.env.COOKIE_CRYPTO_SECRET;
    else process.env.COOKIE_CRYPTO_SECRET = previousSecret;
  }
});
