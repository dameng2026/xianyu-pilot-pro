export interface GoofishStoreUrlResult {
  userId: string;
  normalizedUrl: string;
  /** 原始输入链接，仅在需要浏览器解析 userId 时返回 */
  rawUrl?: string;
  /** 标记 URL 中缺少 userId，需要上层通过浏览器解析 */
  needsBrowserResolution?: boolean;
}

/**
 * 解析闲鱼/Goofish 店铺链接，提取 userId 并返回标准化 URL。
 * 只允许 goofish.com / www.goofish.com，pathname 必须是 /personal，
 * userId 必须是纯数字。
 *
 * 当 URL 中没有 userId 参数（如首页分享链接 https://www.goofish.com/?spm=...）
 * 时，不再抛错，而是返回 userId='' 并标记 needsBrowserResolution=true，
 * 由上层调用方决定是否通过浏览器访问页面来解析 userId。
 */
export function parseGoofishStoreUrl(input: string): GoofishStoreUrlResult {
  const trimmed = input.trim();
  if (!trimmed || trimmed.length > 2048) {
    throw new Error('URL 不能为空且长度不能超过 2048 个字符');
  }

  let url: URL;
  try {
    url = new URL(trimmed);
  } catch {
    throw new Error('无效的 URL 格式');
  }
  if (url.protocol !== 'https:') {
    throw new Error('店铺 URL 必须使用 HTTPS');
  }
  if (url.username || url.password) {
    throw new Error('店铺 URL 不允许包含用户凭据');
  }
  if (url.port && url.port !== '443') {
    throw new Error('店铺 URL 仅允许 HTTPS 默认端口');
  }

  // 只允许 goofish.com 和 www.goofish.com
  const hostname = url.hostname.toLowerCase();
  if (hostname !== 'goofish.com' && hostname !== 'www.goofish.com' && hostname !== 'm.goofish.com') {
    throw new Error(`不支持的域名: ${hostname}，仅支持 goofish.com`);
  }

  // pathname 常见为 /personal，移动端或分享页可能带尾斜杠；只要能提取 userId 就允许。
  const normalizedPath = url.pathname.replace(/\/$/, '');
  if (normalizedPath && normalizedPath !== '/personal') {
    const pathUser = normalizedPath.match(/(\d{6,})/);
    if (pathUser) {
      const userId = pathUser[1];
      return { userId, normalizedUrl: `https://www.goofish.com/personal?userId=${userId}` };
    }
  }

  // 从 query 提取 userId，兼容 user_id / sellerId / seller_id。
  const userId = url.searchParams.get('userId') || url.searchParams.get('user_id') || url.searchParams.get('sellerId') || url.searchParams.get('seller_id');
  if (!userId) {
    // 没有 userId 参数（如首页分享链接 https://www.goofish.com/?spm=...），
    // 不再报错，而是返回空 userId 并标记需要浏览器解析。
    return {
      userId: '',
      normalizedUrl: trimmed,
      rawUrl: trimmed,
      needsBrowserResolution: true,
    };
  }

  // userId 必须是纯数字
  if (!/^\d+$/.test(userId)) {
    throw new Error(`userId 必须为纯数字，当前值: ${userId}`);
  }

  const normalizedUrl = `https://www.goofish.com/personal?userId=${userId}`;

  return { userId, normalizedUrl };
}
