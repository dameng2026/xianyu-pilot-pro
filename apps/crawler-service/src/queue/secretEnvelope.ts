import crypto from 'crypto';
import { isProductionLike } from '../policy.js';

const VERSION = 'v2';
const DEVELOPMENT_SECRET = 'dev-only-crawler-queue-cookie-secret-change-me';

function configuredSecret(): string {
  const environment = process.env.NODE_ENV || process.env.APP_ENV || 'development';
  const productionLike = isProductionLike(environment);
  const secret = String(process.env.COOKIE_CRYPTO_SECRET || '').trim();

  if (productionLike) {
    if (secret.length < 32
        || /(?:replace-with|placeholder|dev-only|change-me)/i.test(secret)) {
      throw new Error('COOKIE_CRYPTO_SECRET is missing or unsafe');
    }
    return secret;
  }
  return secret || DEVELOPMENT_SECRET;
}

function keyFor(secret: string): Buffer {
  return crypto.createHash('sha256').update(secret, 'utf8').digest();
}

function keyId(secret: string): string {
  return crypto.createHash('sha256').update(`crawler-queue:${secret}`, 'utf8').digest('hex').slice(0, 16);
}

function decryptionSecrets(): string[] {
  const current = configuredSecret();
  const previous = String(process.env.COOKIE_CRYPTO_PREVIOUS_SECRETS || '')
    .split(',')
    .map((value) => value.trim())
    .filter(Boolean);
  return [...new Set([current, ...previous])];
}

export function assertQueueCookieEncryptionReady(): void {
  configuredSecret();
}

export function encryptQueueCookie(value: string, binding: string): string {
  if (!value) return '';
  if (!binding || binding.length > 256) throw new Error('queue cookie binding is invalid');
  const secret = configuredSecret();
  const iv = crypto.randomBytes(12);
  const cipher = crypto.createCipheriv('aes-256-gcm', keyFor(secret), iv);
  cipher.setAAD(Buffer.from(binding, 'utf8'));
  const encrypted = Buffer.concat([cipher.update(value, 'utf8'), cipher.final()]);
  const tag = cipher.getAuthTag();
  return [VERSION, keyId(secret), iv.toString('base64url'), tag.toString('base64url'), encrypted.toString('base64url')].join(':');
}

export function decryptQueueCookie(envelope: string | undefined, binding: string): string {
  if (!envelope) return '';
  if (!binding || binding.length > 256) throw new Error('queue cookie binding is invalid');
  const [version, envelopeKeyId, ivText, tagText, encryptedText, ...extra] = envelope.split(':');
  if (version !== VERSION || !envelopeKeyId || !ivText || !tagText || !encryptedText || extra.length > 0) {
    throw new Error('invalid encrypted queue cookie envelope');
  }
  try {
    const secret = decryptionSecrets().find((candidate) => keyId(candidate) === envelopeKeyId);
    if (!secret) throw new Error('unknown envelope key');
    const iv = Buffer.from(ivText, 'base64url');
    const tag = Buffer.from(tagText, 'base64url');
    const encrypted = Buffer.from(encryptedText, 'base64url');
    if (iv.length !== 12 || tag.length !== 16 || encrypted.length === 0) throw new Error('invalid envelope');
    const decipher = crypto.createDecipheriv('aes-256-gcm', keyFor(secret), iv);
    decipher.setAAD(Buffer.from(binding, 'utf8'));
    decipher.setAuthTag(tag);
    return Buffer.concat([decipher.update(encrypted), decipher.final()]).toString('utf8');
  } catch {
    throw new Error('encrypted queue cookie authentication failed');
  }
}
