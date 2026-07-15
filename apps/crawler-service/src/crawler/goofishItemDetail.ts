import { chromium, Browser, BrowserContextOptions, Cookie } from 'playwright';
import { isSafeBrowserResourceUrl, normalizeGoofishTargetUrl } from '../policy.js';

export interface GoofishItemDetail {
  itemId?: string;
  title?: string;
  picUrl?: string;
  price?: string;
  desc?: string;
  userNickName?: string;
  area?: string;
}

const ITEM_DETAIL_API_MARKER = 'mtop.taobao.idle.pc.detail';

/**
 * 通过 Playwright 浏览器打开商品详情页，拦截 mtop.taobao.idle.pc.detail 响应，
 * 提取商品封面图、标题、价格等信息。
 *
 * 事件驱动：用 Promise.race 竞速等待 detail 响应到达 vs. 10 秒超时，
 * 响应到达后立即返回，不固定等待。
 *
 * 注意：必须用 ?id= 而非 ?itemId=，否则闲鱼网页 JS 会发送空 itemId。
 */
export async function fetchGoofishItemDetail(
  itemId: string,
  cookieStr: string = ''
): Promise<GoofishItemDetail> {
  const detailUrl = `https://www.goofish.com/item?id=${itemId}`;
  console.log(`[ItemDetailCrawler] 开始获取商品详情: itemId=${itemId}, hasCookie=${!!cookieStr}`);

  const headless = process.env.HEADLESS !== 'false';
  const isWindows = process.platform === 'win32';
  let browser: Browser | null = null;

  let detailResolve!: (detail: GoofishItemDetail) => void;
  const detailPromise = new Promise<GoofishItemDetail>((resolve) => {
    detailResolve = resolve;
  });
  let settled = false;

  try {
    browser = await chromium.launch({
      headless,
      chromiumSandbox: true,
      ...(isWindows && !headless ? { channel: 'chrome' } : {}),
    });

    const contextOptions: BrowserContextOptions = {
      viewport: { width: 1366, height: 900 },
      userAgent:
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    };

    // 注入 Cookie，让浏览器使用已登录的闲鱼会话
    if (cookieStr) {
      const cookies = cookieStr
        .split(';')
        .map((part): Cookie | null => {
          part = part.trim();
          if (!part || !part.includes('=')) return null;
          const idx = part.indexOf('=');
          const name = part.substring(0, idx).trim();
          const value = part.substring(idx + 1).trim();
          return {
            name,
            value,
            domain: '.goofish.com',
            path: '/',
            expires: -1,
            httpOnly: false,
            secure: true,
            sameSite: 'Lax',
          };
        })
        .filter((c): c is Cookie => c !== null);
      if (cookies.length > 0) {
        contextOptions.storageState = { cookies, origins: [] };
      }
    }

    const context = await browser.newContext(contextOptions);
    await context.route('**/*', async (route) => {
      const request = route.request();
      if (!isSafeBrowserResourceUrl(request.url())) {
        await route.abort('blockedbyclient');
        return;
      }
      if (!request.isNavigationRequest() || request.frame().parentFrame()) {
        await route.continue();
        return;
      }
      try {
        normalizeGoofishTargetUrl(request.url());
        await route.continue();
      } catch {
        await route.abort('blockedbyclient');
      }
    });

    const page = await context.newPage();

    // 监听网络响应，拦截 MTOP 商品详情 API 响应
    page.on('response', async (response) => {
      const req = response.request();
      const resourceType = req.resourceType();
      if (resourceType !== 'xhr' && resourceType !== 'fetch') {
        return;
      }

      const reqUrl = req.url() || '';
      if (!reqUrl.includes(ITEM_DETAIL_API_MARKER)) {
        return;
      }

      const contentType = response.headers()['content-type'] || '';
      if (!contentType.includes('json')) {
        return;
      }

      try {
        const text = await response.text();
        if (!text || text.length < 50 || text.length > 2 * 1024 * 1024) return;

        let json: unknown;
        try {
          json = JSON.parse(text);
        } catch {
          return;
        }

        const jsonObj = json as Record<string, unknown>;
        const ret = jsonObj.ret;
        const retMsg = Array.isArray(ret) && ret.length > 0 ? String(ret[0]) : String(ret || '');
        if (!retMsg.includes('SUCCESS')) {
          console.log(`[ItemDetailCrawler] MTOP 响应非成功: itemId=${itemId} ret=${retMsg}`);
          return;
        }

        const data = jsonObj.data as Record<string, unknown> | undefined;
        if (!data || typeof data !== 'object') return;

        const itemDO = (data.itemDO as Record<string, unknown>) || undefined;
        const item = (data.item as Record<string, unknown>) || undefined;
        const seller = (data.sellerDO as Record<string, unknown>) || undefined;

        const detail: GoofishItemDetail = {
          itemId: String(itemDO?.itemId || item?.itemId || itemId || ''),
          title: String(itemDO?.title || item?.title || '').trim(),
          picUrl: String(itemDO?.picUrl || item?.picUrl || itemDO?.coverPic || '').trim(),
          price: String(itemDO?.reservePrice || itemDO?.price || item?.price || '').trim(),
          desc: String(itemDO?.desc || '').trim(),
          userNickName: String(seller?.userNickName || seller?.nickName || '').trim(),
          area: String(itemDO?.area || item?.area || '').trim(),
        };

        // 尝试从 imageUrls 列表提取封面图（如果 picUrl 为空）
        if (!detail.picUrl) {
          const imageUrls = itemDO?.imageUrls as unknown[] | undefined;
          if (Array.isArray(imageUrls) && imageUrls.length > 0) {
            detail.picUrl = String(imageUrls[0] || '').trim();
          }
        }

        if (!settled) {
          settled = true;
          console.log(`[ItemDetailCrawler] 拦截到商品详情: itemId=${itemId} picUrl=${detail.picUrl ? detail.picUrl.substring(0, 60) : '(空)'}`);
          detailResolve(detail);
        }
      } catch {
        // 忽略解析异常
      }
    });

    await page.goto(detailUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });

    // 竞速：detail 响应到达 vs. 10 秒超时
    const result = await Promise.race([
      detailPromise,
      new Promise<GoofishItemDetail>((resolve) =>
        setTimeout(() => resolve({ itemId }), 10000)
      ),
    ]);

    // 如果 MTOP API 被风控拦截（未拿到 picUrl），从 DOM 兜底提取封面图
    if (!result.picUrl) {
      try {
        // 等待页面渲染完成（图片可能异步加载）
        await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {});

        // 调试：检查当前页面 URL 和标题
        const currentUrl = page.url();
        const pageTitle = await page.title();
        console.log(`[ItemDetailCrawler] 页面状态: itemId=${itemId} url=${currentUrl} title=${pageTitle.substring(0, 50)}`);

        const domDetail = await page.evaluate(() => {
          const detail: { picUrl?: string; title?: string; price?: string } = {};

          // 1. 尝试从 og:image meta 标签提取
          const ogImage = document.querySelector('meta[property="og:image"]') as HTMLMetaElement | null;
          if (ogImage?.content) {
            detail.picUrl = ogImage.content;
          }

          // 2. 尝试从商品图片容器提取（闲鱼商品页通常有主图）
          if (!detail.picUrl) {
            const imgSelectors = [
              '.item-main-image img',
              '.item-image img',
              '.goods-image img',
              '.pic-container img',
              '.main-pic img',
              '[class*="itemPic"] img',
              '[class*="mainImage"] img',
              '[class*="goodsPic"] img',
            ];
            for (const selector of imgSelectors) {
              const img = document.querySelector(selector) as HTMLImageElement | null;
              if (img?.src && img.src.includes('alicdn.com')) {
                detail.picUrl = img.src;
                break;
              }
            }
          }

          // 3. 如果仍未找到，尝试从所有 alicdn.com 图片中提取（排除头像）
          if (!detail.picUrl) {
            const imgs = Array.from(document.querySelectorAll('img'));
            for (const img of imgs) {
              const src = img.src || img.getAttribute('data-src') || '';
              if (src.includes('alicdn.com') && !src.includes('avatar') && !src.includes('logo')) {
                // 排除小图标（宽高小于 100）
                const w = img.naturalWidth || img.width || 0;
                const h = img.naturalHeight || img.height || 0;
                if (w >= 100 && h >= 100) {
                  detail.picUrl = src;
                  break;
                }
              }
            }
          }

          // 提取标题
          const ogTitle = document.querySelector('meta[property="og:title"]') as HTMLMetaElement | null;
          if (ogTitle?.content) {
            detail.title = ogTitle.content;
          }

          return detail;
        });

        if (domDetail.picUrl) {
          console.log(`[ItemDetailCrawler] DOM 兜底提取封面图: itemId=${itemId} picUrl=${domDetail.picUrl.substring(0, 60)}`);
          return { ...result, ...domDetail };
        }
      } catch (domErr) {
        console.debug(`[ItemDetailCrawler] DOM 提取失败: itemId=${itemId} err=${domErr}`);
      }
    }

    return result;
  } catch (error) {
    console.error(`[ItemDetailCrawler] 获取商品详情失败: itemId=${itemId} err=${error}`);
    return { itemId };
  } finally {
    if (browser) {
      try {
        await browser.close();
      } catch {
        // 忽略关闭异常
      }
    }
  }
}
