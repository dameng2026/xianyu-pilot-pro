import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

function read(relative: string): string {
  return readFileSync(new URL(`../${relative}`, import.meta.url), 'utf8');
}

test('API process only publishes work and never embeds plaintext cookies in queue jobs', () => {
  const server = read('src/server.ts');
  const worker = read('src/worker.ts');

  assert.equal(server.includes('createWorker('), false);
  assert.match(server, /cookieEnvelope:\s*encryptQueueCookie\(cookie, `\$\{tenantId\}:\$\{jobId\}`\)/);
  assert.equal(server.includes('...(cookie ? { cookie }'), false);
  assert.match(worker, /decryptQueueCookie\(cookieEnvelope, `\$\{tenantId\}:\$\{jobId\}`\)/);
  assert.equal(server.includes('url: normalizedUrl'), false);
  assert.equal(server.includes('userId,\n        ...(cookie'), false);
});

test('browser runtime keeps sandboxing and does not copy Goofish cookies to unrelated domains', () => {
  const sources = [
    read('src/crawler/goofish.ts'),
    read('src/crawler/goofishSearch.ts'),
    read('src/crawler/qrLoginSolver.ts'),
    read('src/crawler/sliderSolver.ts'),
  ].join('\n');

  const launchCount = sources.match(/chromium\.launch\(\{/g)?.length ?? 0;
  const sandboxCount = sources.match(/chromiumSandbox:\s*true/g)?.length ?? 0;
  assert.equal(launchCount, 6);
  assert.equal(sandboxCount, launchCount);
  assert.equal(sources.includes('--no-sandbox'), false);
  assert.equal(sources.includes('secure: false'), false);
  assert.equal(sources.includes("domain: '.taobao.com'"), false);
  assert.equal(sources.includes('text.slice(0, 300)'), false);
  assert.equal(sources.includes('keyword=${keyword}'), false);
});

test('production runtime disables browser debug artifacts and has navigation guards', () => {
  const goofish = read('src/crawler/goofish.ts');
  const slider = read('src/crawler/sliderSolver.ts');
  const qr = read('src/crawler/qrLoginSolver.ts');

  assert.match(goofish, /!dir \|\| isProductionLike\(environment\)/);
  assert.match(slider, /!debugDir \|\| isProductionLike\(environment\)/);
  assert.match(goofish, /guardMainFrameNavigation\(context\)/);
  assert.match(goofish, /isSafeBrowserResourceUrl\(request\.url\(\)\)/);
  assert.match(slider, /isAllowedBrowserNavigationUrl\(request\.url\(\), true\)/);
  assert.match(slider, /isSafeBrowserResourceUrl\(request\.url\(\)\)/);
  assert.match(qr, /isAllowedBrowserNavigationUrl\(request\.url\(\), true\)/);
  assert.match(qr, /isSafeBrowserResourceUrl\(request\.url\(\)\)/);
});

test('credential responses are non-cacheable and QR capabilities stay out of URLs', () => {
  const server = read('src/server.ts');

  assert.match(server, /Cache-Control', 'no-store, max-age=0/);
  assert.match(server, /app\.post\('\/api\/qrlogin\/cancel'/);
  assert.equal(server.includes('/api/qrlogin/sessions/:sessionId'), false);
  assert.equal(server.includes('path=${req.path}'), false);
});

test('crawl persistence uses execution fencing and current-snapshot visibility', () => {
  const schema = `${read('src/db/index.ts')}\n${read('migrations/V1.1__baseline_crawler_schema.sql')}`;
  const persistence = read('src/db/saveItems.ts');
  const server = read('src/server.ts');

  assert.match(schema, /execution_token TEXT/);
  assert.match(persistence, /execution_token = \$4/);
  assert.match(persistence, /SET is_active = FALSE/);
  assert.match(persistence, /is_active = TRUE/);
  assert.match(server, /AND is_active = TRUE/);
  assert.match(server, /SELECT COUNT\(\*\) AS total/);
  assert.match(server, /LIMIT \$3 OFFSET \$4/);
  assert.match(server, /ORDER BY last_seen_at DESC, id DESC/);
  assert.match(server, /hasMore: page \* pageSize < total/);
  assert.equal(read('src/crawler/goofishSearch.ts').includes('raw: ex'), false);
});

test('search pagination marks inferred continuation and totals as non-authoritative', () => {
  const search = read('src/crawler/goofishSearch.ts');

  assert.match(search, /hasMoreKnown: networkHasMore !== undefined/);
  assert.match(search, /hasMoreKnown: pagination\.hasMore !== undefined/);
  assert.match(search, /totalExact: networkTotal !== undefined/);
  assert.equal(search.includes('(pageNum - 1) * pageSize;\n      const pagedItems'), false);
});
