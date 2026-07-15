const DEV_INTERNAL_TOKEN = 'dev-only-internal-api-token-change-me-32-chars';
const DEV_REDIS_PASSWORD = 'dev-only-redis-password-change-me';
const DEVELOPMENT_ENVS = new Set(['development', 'dev', 'test', 'testing', 'local']);

export interface InternalTokenPolicy {
  ready: boolean;
  token: string;
  reason?: string;
}

export function isProductionLike(environment: string | undefined): boolean {
  const normalized = String(environment || 'development').trim().toLowerCase();
  return !DEVELOPMENT_ENVS.has(normalized);
}

export function resolveInternalTokenPolicy(
  rawToken: string | undefined,
  environment: string | undefined,
): InternalTokenPolicy {
  const token = String(rawToken || '').trim();
  if (!isProductionLike(environment)) {
    return { ready: true, token: token || DEV_INTERNAL_TOKEN };
  }
  if (!token) {
    return { ready: false, token: '', reason: 'INTERNAL_API_TOKEN is not configured' };
  }
  if (token.length < 32 || token === DEV_INTERNAL_TOKEN) {
    return { ready: false, token: '', reason: 'INTERNAL_API_TOKEN is weak or uses the development default' };
  }
  return { ready: true, token };
}

export function resolveRedisPasswordPolicy(
  rawPassword: string | undefined,
  environment: string | undefined,
): InternalTokenPolicy {
  const password = String(rawPassword || '').trim();
  if (!isProductionLike(environment)) {
    return { ready: true, token: password || DEV_REDIS_PASSWORD };
  }
  const uniqueCharacters = new Set(password).size;
  if (password.length < 32 || uniqueCharacters < 4 || password === DEV_REDIS_PASSWORD
      || /(?:replace-with|placeholder|dev-only|change-me)/i.test(password)) {
    return { ready: false, token: '', reason: 'REDIS_PASSWORD is missing or unsafe' };
  }
  return { ready: true, token: password };
}

export function areProductionCorsOriginsSafe(
  allowedOrigins: readonly string[],
  environment: string | undefined,
): boolean {
  if (!isProductionLike(environment)) return true;
  if (!allowedOrigins.length) return false;
  return allowedOrigins.every((value) => {
    if (!value || value.includes('*')) return false;
    try {
      const url = new URL(value);
      return url.protocol === 'https:'
        && !!url.hostname
        && !url.username
        && !url.password
        && (url.pathname === '/' || url.pathname === '')
        && !url.search
        && !url.hash
        && !['localhost', '127.0.0.1', '::1'].includes(url.hostname.toLowerCase());
    } catch {
      return false;
    }
  });
}

export function isCorsOriginAllowed(
  origin: string | undefined,
  allowedOrigins: readonly string[],
  environment: string | undefined,
): boolean {
  if (!origin) return true;
  if (!areProductionCorsOriginsSafe(allowedOrigins, environment)) return false;
  if (allowedOrigins.includes(origin)) return true;
  return allowedOrigins.length === 0 && !isProductionLike(environment);
}

export function toPublicCrawlerError(error: unknown, fallback: string): string {
  const message = String(error instanceof Error ? error.message : error || '').toLowerCase();
  if (/(?:cookie|login|登录|登录态|expired|过期|session)/i.test(message)) {
    return '账号登录状态已失效，请重新登录';
  }
  if (/(?:captcha|滑块|人机验证)/i.test(message)) {
    return '采集触发人机验证，请先完成验证后重试';
  }
  if (/(?:timeout|timed out|etimedout|超时)/i.test(message)) {
    return '采集请求超时，请稍后重试';
  }
  return fallback;
}

export function safeErrorType(error: unknown): string {
  if (error instanceof Error) {
    const name = String(error.name || error.constructor?.name || 'Error');
    return /^[A-Za-z][A-Za-z0-9_.-]{0,63}$/.test(name) ? name : 'Error';
  }
  return 'UnknownError';
}

export function normalizeCookieInput(value: unknown): string {
  if (value === undefined || value === null || value === '') return '';
  if (typeof value !== 'string') throw new Error('Cookie must be a string');
  const cookie = value.trim();
  if (cookie.length > 16 * 1024 || /[\u0000-\u001f\u007f]/.test(cookie)) {
    throw new Error('Cookie is invalid or exceeds 16384 characters');
  }
  return cookie;
}

export function normalizeTenantId(value: unknown): string {
  const tenantId = typeof value === 'string' ? value.trim() : '';
  if (!/^[1-9]\d{0,18}$/.test(tenantId) || BigInt(tenantId) > 9223372036854775807n) {
    throw new Error('missing or invalid X-Internal-Tenant-Id');
  }
  return tenantId;
}

export function normalizeGoofishTargetUrl(value: unknown): string | undefined {
  if (value === undefined || value === null || value === '') return undefined;
  if (typeof value !== 'string' || value.length > 2048) {
    throw new Error('目标 URL 格式无效或长度超过 2048 个字符');
  }

  let url: URL;
  try {
    url = new URL(value);
  } catch {
    throw new Error('目标 URL 格式无效');
  }
  if (url.protocol !== 'https:') {
    throw new Error('目标 URL 必须使用 HTTPS');
  }
  if (url.username || url.password) {
    throw new Error('目标 URL 不允许包含用户凭据');
  }
  if (url.port && url.port !== '443') {
    throw new Error('目标 URL 仅允许 HTTPS 默认端口');
  }
  const hostname = url.hostname.toLowerCase();
  if (hostname !== 'goofish.com' && !hostname.endsWith('.goofish.com')) {
    throw new Error('目标 URL 域名仅允许 goofish.com 及其子域名');
  }
  return url.toString();
}

export function isAllowedBrowserNavigationUrl(value: string, allowLoginProvider = false): boolean {
  try {
    const url = new URL(value);
    if (url.protocol !== 'https:' || url.username || url.password || (url.port && url.port !== '443')) {
      return false;
    }
    const hostname = url.hostname.toLowerCase();
    const goofish = hostname === 'goofish.com' || hostname.endsWith('.goofish.com');
    const loginProvider = allowLoginProvider
      && (hostname === 'taobao.com' || hostname.endsWith('.taobao.com'));
    return goofish || loginProvider;
  } catch {
    return false;
  }
}

function isBlockedIpv4(hostname: string): boolean {
  const parts = hostname.split('.');
  if (parts.length !== 4 || parts.some((part) => !/^\d{1,3}$/.test(part))) return false;
  const octets = parts.map(Number);
  if (octets.some((part) => part < 0 || part > 255)) return true;
  const [a, b] = octets;
  return a === 0 || a === 10 || a === 127 || a >= 224
    || (a === 100 && b >= 64 && b <= 127)
    || (a === 169 && b === 254)
    || (a === 172 && b >= 16 && b <= 31)
    || (a === 192 && (b === 0 || b === 168))
    || (a === 198 && (b === 18 || b === 19 || b === 51))
    || (a === 203 && b === 0);
}

function isBlockedIpv6(hostname: string): boolean {
  const host = hostname.replace(/^\[|\]$/g, '').toLowerCase();
  if (!host.includes(':')) return false;
  if (host === '::' || host === '::1' || host.startsWith('fc') || host.startsWith('fd')
      || /^fe[89ab]/.test(host) || host.startsWith('ff') || host.startsWith('2001:db8:')) {
    return true;
  }
  const mapped = host.match(/::ffff:(\d+\.\d+\.\d+\.\d+)$/);
  return mapped ? isBlockedIpv4(mapped[1]) : false;
}

export function isSafeBrowserResourceUrl(value: string): boolean {
  try {
    const url = new URL(value);
    if (url.protocol === 'data:' || url.protocol === 'blob:') return true;
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) return false;
    const hostname = url.hostname.toLowerCase();
    if (!hostname
        || hostname === 'localhost'
        || hostname.endsWith('.localhost')
        || hostname.endsWith('.local')
        || hostname.endsWith('.internal')
        || hostname === 'metadata.google.internal'
        || hostname === 'instance-data') {
      return false;
    }
    return !isBlockedIpv4(hostname) && !isBlockedIpv6(hostname);
  } catch {
    return false;
  }
}

function boundedInteger(value: unknown, fallback: number, minimum: number, maximum: number): number {
  const parsed = Number.parseInt(String(value ?? fallback), 10);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.max(minimum, Math.min(parsed, maximum));
}

export interface SearchInput {
  q: string;
  page: number;
  pageSize: number;
  cookie: string;
}

export function parseSearchInput(input: Record<string, unknown>): SearchInput {
  const q = typeof input.q === 'string' ? input.q.trim() : '';
  if (!q) throw new Error('请输入搜索关键词');
  if (q.length > 50) throw new Error('关键词长度不能超过 50 个字符');

  const cookie = normalizeCookieInput(input.cookie);

  return {
    q,
    page: boundedInteger(input.page, 1, 1, 100),
    pageSize: boundedInteger(input.pageSize, 20, 1, 50),
    cookie,
  };
}
