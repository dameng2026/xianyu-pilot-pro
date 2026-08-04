/**
 * x5sec Redis 缓存模块 —— 方案 I x5sec 持久化强化
 *
 * 作用：滑块验证成功后，x5sec cookie 可缓存复用，后续请求注入 x5sec 即可绕过滑块。
 *
 * 缓存策略：
 * - Key: x5sec:{userId} （从 cookie 的 unb 字段提取用户 ID）
 * - Fallback Key: x5sec:tk:{mtopToken} （从 _m_h5_tk 提取 token 作为后备 key）
 * - TTL: 24 小时（方案 I 优化：从 6 小时延长到 24 小时，减少重复求解频率）
 * - 惰性过期：缓存到期后自动删除，下次请求触发滑块求解刷新
 *
 * 2026-08-03 方案 I 优化：
 * - TTL 从 6 小时延长到 24 小时（x5sec 实际有效期可能更长，延长 TTL 减少重复求解）
 * - 在代理配额耗尽期间，已缓存的 x5sec 仍可复用，避免触发滑块
 * - Python 端 x5sec_cache_client.py 已同步延长到 24 小时
 *
 * 安全性：
 * - x5sec 值不落日志（只记录长度）
 * - Redis 连接独立于队列连接，避免缓存操作阻塞队列
 * - 连接失败时静默降级（不影响主流程）
 */
import IORedis from 'ioredis';
import crypto from 'crypto';

// 2026-08-03 方案 I：TTL 从 6 小时延长到 24 小时
const X5SEC_CACHE_TTL = 24 * 60 * 60; // 24 小时（秒）
const X5SEC_KEY_PREFIX = 'x5sec:';
const X5SEC_TK_KEY_PREFIX = 'x5sec:tk:';

let x5secRedis: IORedis | null = null;
let x5secRedisConnecting = false;

function getRedisConnection(): IORedis | null {
  if (x5secRedis) return x5secRedis;
  if (x5secRedisConnecting) return null; // 避免并发创建多个连接

  x5secRedisConnecting = true;

  try {
    // 2026-08-02 修复：enableOfflineQueue 改为 true，让连接断开时操作排队等待重连
    // 原因：enableOfflineQueue=false 导致连接断开时所有操作直接失败，
    //       x5sec 缓存完全失效。改为 true 后，操作会排队等待重连完成。
    // 2026-08-02 修复：移除 connectAttempted 永久标记，允许连接失败后重试
    // 原因：connectAttempted=true 后永不重试，如果 Redis 启动慢或临时断开，
    //       x5sec 缓存永久失效，无法恢复。
    x5secRedis = new IORedis({
      host: process.env.REDIS_HOST || 'localhost',
      port: parseInt(process.env.REDIS_PORT || '6379', 10),
      password: process.env.REDIS_PASSWORD || undefined,
      connectTimeout: 5000,
      retryStrategy: (attempt: number) => Math.min(attempt * 500, 5000),
      maxRetriesPerRequest: 3,
      enableOfflineQueue: true,
      lazyConnect: false,
    });

    x5secRedis.on('error', (err: Error) => {
      // Redis 不可用时静默降级，不影响主流程
      console.warn(`[X5secCache] Redis 错误（降级为无缓存）: ${err.message}`);
    });

    x5secRedis.on('close', () => {
      // 2026-08-02 修复：连接关闭时重置状态，允许下次重新创建连接
      console.warn('[X5secCache] Redis 连接已关闭，将在下次操作时重连');
      x5secRedis = null;
    });

    x5secRedis.on('end', () => {
      // 2026-08-02 修复：连接彻底断开时重置状态
      console.warn('[X5secCache] Redis 连接已断开，将在下次操作时重连');
      x5secRedis = null;
    });

    return x5secRedis;
  } catch (e: any) {
    console.warn(`[X5secCache] Redis 连接创建失败: ${e?.message || e}`);
    return null;
  } finally {
    x5secRedisConnecting = false;
  }
}

/**
 * 从 cookie 字符串提取用户标识，用于作为缓存 key。
 * 优先使用 unb（闲鱼用户 ID），其次用 _m_h5_tk 的前半部分。
 */
function extractCacheKeys(cookieStr: string): { userId?: string; tkKey?: string } {
  if (!cookieStr) return {};
  const result: { userId?: string; tkKey?: string } = {};

  // 提取 unb（用户 ID）
  const unbMatch = cookieStr.match(/(?:^|;\s*)unb=([^;]+)/);
  if (unbMatch && unbMatch[1]) {
    result.userId = unbMatch[1].trim();
  }

  // 提取 _m_h5_tk（MTOP token），取前 32 字符作为 hash key
  const tkMatch = cookieStr.match(/(?:^|;\s*)_m_h5_tk=([^;]+)/);
  if (tkMatch && tkMatch[1]) {
    const tk = tkMatch[1].trim();
    // _m_h5_tk 格式: {timestamp}_{token}，取 token 部分
    const tkPart = tk.includes('_') ? tk.split('_').slice(1).join('_') : tk;
    result.tkKey = crypto.createHash('md5').update(tkPart).digest('hex').slice(0, 16);
  }

  return result;
}

/**
 * 将 x5sec 缓存到 Redis。
 * 同时写入 user-key 和 tk-key，提高命中率。
 */
export async function cacheX5sec(cookieStr: string, x5sec: string): Promise<void> {
  if (!x5sec || !cookieStr) return;

  const redis = getRedisConnection();
  if (!redis) return;

  const keys = extractCacheKeys(cookieStr);
  const cacheKeys: string[] = [];
  if (keys.userId) cacheKeys.push(`${X5SEC_KEY_PREFIX}${keys.userId}`);
  if (keys.tkKey) cacheKeys.push(`${X5SEC_TK_KEY_PREFIX}${keys.tkKey}`);

  if (cacheKeys.length === 0) {
    console.warn('[X5secCache] 无法从 cookie 提取用户标识，跳过缓存');
    return;
  }

  try {
    // 同时写入所有 key，确保任一 key 都能命中
    const pipeline = redis.pipeline();
    for (const key of cacheKeys) {
      pipeline.set(key, x5sec, 'EX', X5SEC_CACHE_TTL);
    }
    await pipeline.exec();
    console.log(`[X5secCache] 已缓存 x5sec (keys=${cacheKeys.length}, 长度=${x5sec.length}, TTL=${X5SEC_CACHE_TTL}s)`);
  } catch (e: any) {
    console.warn(`[X5secCache] 缓存写入失败: ${e?.message || e}`);
  }
}

/**
 * 从 Redis 读取缓存的 x5sec。
 * 优先查 user-key，其次查 tk-key。
 */
export async function getCachedX5sec(cookieStr: string): Promise<string | null> {
  if (!cookieStr) return null;

  const redis = getRedisConnection();
  if (!redis) return null;

  const keys = extractCacheKeys(cookieStr);
  const cacheKeys: string[] = [];
  if (keys.userId) cacheKeys.push(`${X5SEC_KEY_PREFIX}${keys.userId}`);
  if (keys.tkKey) cacheKeys.push(`${X5SEC_TK_KEY_PREFIX}${keys.tkKey}`);

  if (cacheKeys.length === 0) return null;

  try {
    for (const key of cacheKeys) {
      const value = await redis.get(key);
      if (value) {
        console.log(`[X5secCache] 命中缓存 (key=${key.slice(0, 20)}..., 长度=${value.length})`);
        return value;
      }
    }
    return null;
  } catch (e: any) {
    console.warn(`[X5secCache] 缓存读取失败: ${e?.message || e}`);
    return null;
  }
}

/**
 * 删除缓存的 x5sec（例如 x5sec 失效后清除旧缓存）。
 */
export async function evictCachedX5sec(cookieStr: string): Promise<void> {
  if (!cookieStr) return;

  const redis = getRedisConnection();
  if (!redis) return;

  const keys = extractCacheKeys(cookieStr);
  const cacheKeys: string[] = [];
  if (keys.userId) cacheKeys.push(`${X5SEC_KEY_PREFIX}${keys.userId}`);
  if (keys.tkKey) cacheKeys.push(`${X5SEC_TK_KEY_PREFIX}${keys.tkKey}`);

  if (cacheKeys.length === 0) return;

  try {
    const pipeline = redis.pipeline();
    for (const key of cacheKeys) {
      pipeline.del(key);
    }
    await pipeline.exec();
    console.log(`[X5secCache] 已清除缓存 (keys=${cacheKeys.length})`);
  } catch (e: any) {
    console.warn(`[X5secCache] 缓存清除失败: ${e?.message || e}`);
  }
}

/**
 * 检查 cookie 字符串中是否已包含 x5sec。
 */
export function cookieHasX5sec(cookieStr: string): boolean {
  if (!cookieStr) return false;
  // x5sec 值不能为空
  const match = cookieStr.match(/(?:^|;\s*)x5sec=([^;\s]+)/);
  return !!(match && match[1] && match[1].length > 5);
}

/**
 * 将 x5sec 注入到 cookie 字符串中。
 * - 如果 cookie 已有 x5sec，替换为新值
 * - 如果没有，追加到末尾
 * - 同时清除 x5secdata（punish 标记，避免干扰验证）
 */
export function injectX5secIntoCookie(cookieStr: string, x5sec: string): string {
  if (!x5sec || !cookieStr) return cookieStr;

  let result = cookieStr;

  // 替换或追加 x5sec
  if (/(?:^|;\s*)x5sec=[^;]+/i.test(result)) {
    result = result.replace(/(?:^|;\s*)x5sec=[^;]+/i, `; x5sec=${x5sec}`);
  } else {
    result = `${result}; x5sec=${x5sec}`;
  }

  // 清除 x5secdata（punish 数据，有 x5sec 后不再需要）
  result = result.replace(/(?:^|;\s*)x5secdata=[^;]*/gi, '');

  // 清理多余的空格和分号
  result = result.replace(/;\s*;\s*/g, '; ').replace(/^;\s*/, '').trim();

  return result;
}

/**
 * 关闭 Redis 连接（在进程退出时调用）。
 */
export async function closeX5secCache(): Promise<void> {
  if (x5secRedis) {
    try {
      await x5secRedis.quit();
    } catch {
      // 忽略关闭错误
    }
    x5secRedis = null;
  }
}
