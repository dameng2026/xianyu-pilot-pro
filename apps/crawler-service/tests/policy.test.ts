import assert from 'node:assert/strict';
import test from 'node:test';

import {
  isCorsOriginAllowed,
  isAllowedBrowserNavigationUrl,
  isSafeBrowserResourceUrl,
  normalizeGoofishTargetUrl,
  parseSearchInput,
  resolveInternalTokenPolicy,
  resolveRedisPasswordPolicy,
  areProductionCorsOriginsSafe,
  normalizeCookieInput,
  normalizeTenantId,
  safeErrorType,
  toPublicCrawlerError,
} from '../src/policy.js';
import { parseGoofishStoreUrl } from '../src/crawler/parseGoofishStoreUrl.js';
import { paginateCurrentCapturedPage } from '../src/crawler/goofishSearch.js';


test('production rejects missing, short, and default internal tokens', () => {
  assert.equal(resolveInternalTokenPolicy('', 'production').ready, false);
  assert.equal(resolveInternalTokenPolicy('short', 'production').ready, false);
  assert.equal(
    resolveInternalTokenPolicy('dev-only-internal-api-token-change-me-32-chars', 'production').ready,
    false,
  );
  assert.equal(resolveInternalTokenPolicy('A'.repeat(48), 'production').ready, true);
  assert.equal(resolveInternalTokenPolicy('', 'prodcution').ready, false);
  assert.equal(resolveRedisPasswordPolicy('', 'unknown-environment').ready, false);
});


test('production CORS is fail-closed when no browser origins are configured', () => {
  assert.equal(isCorsOriginAllowed(undefined, [], 'production'), true);
  assert.equal(isCorsOriginAllowed('https://console.example.com', [], 'production'), false);
  assert.equal(
    isCorsOriginAllowed('https://console.example.com', ['https://console.example.com'], 'production'),
    true,
  );
  assert.equal(isCorsOriginAllowed('https://evil.example', [], 'development'), true);
});

test('production requires Redis authentication and explicit HTTPS CORS origins', () => {
  assert.equal(resolveRedisPasswordPolicy('', 'production').ready, false);
  assert.equal(resolveRedisPasswordPolicy('short', 'production').ready, false);
  assert.equal(resolveRedisPasswordPolicy('R3d!s-' + 'xY7p'.repeat(10), 'production').ready, true);
  assert.equal(areProductionCorsOriginsSafe([], 'production'), false);
  assert.equal(areProductionCorsOriginsSafe(['http://admin.example.com'], 'production'), false);
  assert.equal(areProductionCorsOriginsSafe(['https://*.example.com'], 'production'), false);
  assert.equal(areProductionCorsOriginsSafe(['https://admin.example.com'], 'production'), true);
});

test('public crawler errors keep remediation but never expose credentials', () => {
  assert.equal(
    toPublicCrawlerError(new Error('Cookie sid=secret expired at https://example.com?a=token'), '采集失败'),
    '账号登录状态已失效，请重新登录',
  );
  assert.equal(
    toPublicCrawlerError(new Error('connect ETIMEDOUT token=secret'), '采集失败'),
    '采集请求超时，请稍后重试',
  );
  assert.equal(toPublicCrawlerError(new Error('password=secret'), '采集失败'), '采集失败');
});

test('log-safe error metadata never includes exception messages', () => {
  const secret = new Error('Cookie sid=secret and token=private');
  assert.equal(safeErrorType(secret), 'Error');
  assert.equal(safeErrorType('token=private'), 'UnknownError');
});

test('shared cookie and tenant validation is fail-closed and bounded', () => {
  assert.equal(normalizeCookieInput(' a=b '), 'a=b');
  assert.equal(normalizeCookieInput(undefined), '');
  assert.throws(() => normalizeCookieInput({ cookie: 'a=b' }), /string/);
  assert.throws(() => normalizeCookieInput('a=b\r\nX-Injected: true'), /Cookie/);
  assert.throws(() => normalizeCookieInput('x'.repeat(16385)), /16384/);

  assert.equal(normalizeTenantId('1'), '1');
  assert.equal(normalizeTenantId('9223372036854775807'), '9223372036854775807');
  for (const invalid of ['', '0', '-1', '01', '9223372036854775808', '1 OR 1=1']) {
    assert.throws(() => normalizeTenantId(invalid), /tenant/i);
  }
});


test('browser navigation only accepts HTTPS Goofish targets', () => {
  assert.equal(
    normalizeGoofishTargetUrl('https://www.goofish.com/personal?userId=123'),
    'https://www.goofish.com/personal?userId=123',
  );
  assert.equal(
    normalizeGoofishTargetUrl('https://passport.goofish.com/login'),
    'https://passport.goofish.com/login',
  );
  assert.throws(() => normalizeGoofishTargetUrl('http://www.goofish.com/'), /HTTPS/);
  assert.throws(() => normalizeGoofishTargetUrl('https://goofish.com.evil.example/'), /域名/);
  assert.throws(() => normalizeGoofishTargetUrl('https://127.0.0.1/admin'), /域名/);
  assert.throws(() => normalizeGoofishTargetUrl('https://user:pass@www.goofish.com/'), /凭据/);
  assert.equal(isAllowedBrowserNavigationUrl('https://www.goofish.com/item?id=1'), true);
  assert.equal(isAllowedBrowserNavigationUrl('https://login.taobao.com/', true), true);
  assert.equal(isAllowedBrowserNavigationUrl('https://login.taobao.com.evil.example/', true), false);
  assert.equal(isAllowedBrowserNavigationUrl('http://login.taobao.com/', true), false);
  assert.equal(isAllowedBrowserNavigationUrl('https://127.0.0.1/', true), false);
  for (const blocked of (
    ['http://127.0.0.1/', 'http://10.0.0.1/', 'http://172.16.0.1/',
      'http://192.168.1.1/', 'http://169.254.169.254/latest/meta-data/',
      'http://[::1]/', 'http://metadata.google.internal/', 'file:///etc/passwd']
  )) {
    assert.equal(isSafeBrowserResourceUrl(blocked), false, blocked);
  }
  assert.equal(isSafeBrowserResourceUrl('https://gw.alicdn.com/image.png'), true);
  assert.equal(isSafeBrowserResourceUrl('data:image/png;base64,AA=='), true);
});


test('search input is bounded and rejects unsafe cookie text', () => {
  assert.deepEqual(parseSearchInput({ q: '显卡', page: '2', pageSize: '500', cookie: 'a=b' }), {
    q: '显卡',
    page: 2,
    pageSize: 50,
    cookie: 'a=b',
  });
  assert.throws(() => parseSearchInput({ q: '' }), /关键词/);
  assert.throws(() => parseSearchInput({ q: 'x'.repeat(51) }), /50/);
  assert.throws(() => parseSearchInput({ q: '显卡', cookie: `a=b\r\nX-Test: injected` }), /Cookie/);
  assert.throws(() => parseSearchInput({ q: '显卡', cookie: 'x'.repeat(16385) }), /Cookie/);
});


test('store URL parser rejects insecure transport and embedded credentials', () => {
  assert.throws(() => parseGoofishStoreUrl('http://www.goofish.com/personal?userId=123'), /HTTPS/);
  assert.throws(
    () => parseGoofishStoreUrl('https://user:pass@www.goofish.com/personal?userId=123'),
    /凭据/,
  );
  assert.throws(
    () => parseGoofishStoreUrl('https://www.goofish.com:444/personal?userId=123'),
    /端口/,
  );
});

test('search pagination does not slice a captured page twice', () => {
  const capturedPageTwo = Array.from({ length: 20 }, (_, index) => `page-2-item-${index}`);
  assert.deepEqual(paginateCurrentCapturedPage(capturedPageTwo, 10), capturedPageTwo.slice(0, 10));
  assert.deepEqual(paginateCurrentCapturedPage(capturedPageTwo, 50), capturedPageTwo);
});
