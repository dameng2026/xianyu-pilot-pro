import { crawlGoofishStoreDetailed } from '../src/crawler/goofish.js';

const url = process.env.GOOFISH_TEST_STORE_URL || process.argv[2];
const cookie = process.env.GOOFISH_COOKIE || process.env.GOOFISH_TEST_COOKIE || '';

if (!url) {
  console.error('Usage: GOOFISH_COOKIE="..." GOOFISH_TEST_STORE_URL="https://www.goofish.com/personal?userId=..." npm run test:store-crawl');
  process.exit(2);
}

const started = Date.now();
const result = await crawlGoofishStoreDetailed(url, cookie);
console.log(JSON.stringify({
  ok: true,
  elapsedMs: Date.now() - started,
  diagnostics: result.diagnostics,
  count: result.items.length,
  sample: result.items.slice(0, 5).map((item) => ({
    itemId: item.itemId,
    title: item.title,
    price: item.price,
    imageUrl: item.imageUrl,
    itemUrl: item.itemUrl,
  })),
}, null, 2));
