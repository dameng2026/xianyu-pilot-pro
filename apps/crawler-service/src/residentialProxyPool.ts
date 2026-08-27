/**
 * 住址IP代理池（Residential Proxy Pool）—— 方案 H 多代理源聚合 + shenlongip 适配
 * =====================================
 * 2026-08-02 新增：用户购买短效三分钟住址IP，用于提高滑块求解成功率。
 * 2026-08-03 方案 H 升级：多代理源聚合，配额耗尽自动切换备用源，避免单点依赖。
 * 2026-08-03 供应商切换：从 xkdaili 切换到 shenlongip（神龙代理），适配新 API 格式。
 *
 * 业务背景：
 * - 服务器（数据中心）IP 被 Baxia 风控系统标记为高风险
 * - Baxia 多维度检测包括 IP 信誉，数据中心 IP 比住址 IP 风险更高
 * - 住宅IP 可用时滑块求解成功率 60%+，服务器 IP 下 0% 成功
 *
 * 方案 H 多代理源聚合：
 * - 支持配置多个代理 API URL（RESIDENTIAL_PROXY_API_URLS 逗号分隔，或 RESIDENTIAL_PROXY_API_URL 单源）
 * - 每个代理源独立跟踪配额状态（quota_exhausted）和失败次数（consecutive_failures）
 * - 配额耗尽时自动切换到下一个代理源
 * - 配额恢复后自动重新启用（QUOTA_RECOVERY_SEC=600 秒后重试）
 * - 所有代理源都耗尽时才回退到服务器 IP
 *
 * 当前代理供应商（shenlongip 神龙代理）：
 * - 提取接口：http://api.shenlongip.com/ip?key=...&protocol=1&mr=1&pattern=json&count=1&sign=...
 * - 一次只调用 1 个 IP（count=1），一个 IP 有效期 3 分钟，可重复使用
 * - 成功返回：{"data":[{"ip":"1.2.3.4","port":"8080","expire":"2026-08-03 12:00:00","city":"北京","isp":"电信"}]}
 * - 失败返回：{"code":204,"msg":"套餐已过期"}
 * - 状态码：200成功/201格式错误/202数量超限/203KEY异常/204套餐过期/205提取上限/206无可用IP/207地区超范围/208频率太快
 *
 * 缓存策略：
 * - 池中IP每3分钟刷新一次（TTL=180秒，与 shenlongip IP 有效期一致）
 * - 同一 IP 在 TTL 内可被多个求解请求复用
 * - 池中IP用完或过期时自动重新提取
 * - 提取失败时返回 null（让上层降级到无代理模式）
 *
 * 相关文件：
 * - 本文件：代理池实现（方案 H 多代理源聚合 + shenlongip 适配）
 * - server.ts：集成到 /api/goofish/slide-solve 和 /silent-extract 端点
 * - .trae/rules/x5sec-research-knowledge.md：方案 E（住址IP代理池）+ 方案 H（多代理源聚合）
 */
import { safeErrorType } from './policy.js';

// ============================================================
// 配置（环境变量）
// ============================================================
// 方案 H：支持多代理源（逗号分隔），向后兼容单源 RESIDENTIAL_PROXY_API_URL
// 优先级：RESIDENTIAL_PROXY_API_URLS（多源）> RESIDENTIAL_PROXY_API_URL（单源）
const RESIDENTIAL_PROXY_API_URLS_RAW =
  process.env.RESIDENTIAL_PROXY_API_URLS || process.env.RESIDENTIAL_PROXY_API_URL || '';
const RESIDENTIAL_PROXY_API_URLS: string[] = RESIDENTIAL_PROXY_API_URLS_RAW
  .split(',')
  .map((s) => s.trim())
  .filter((s) => s.length > 0);

const RESIDENTIAL_PROXY_TTL_SEC = Number(process.env.RESIDENTIAL_PROXY_TTL_SEC || 180); // 3分钟（与 shenlongip IP 有效期一致）
const RESIDENTIAL_PROXY_POOL_SIZE = Number(process.env.RESIDENTIAL_PROXY_POOL_SIZE || 10);
const USE_RESIDENTIAL_PROXY = String(process.env.USE_RESIDENTIAL_PROXY || 'false').toLowerCase() === 'true';
const RESIDENTIAL_PROXY_FETCH_TIMEOUT_MS = Number(process.env.RESIDENTIAL_PROXY_FETCH_TIMEOUT_MS || 8000);

// shenlongip 要求一次只调用 1 个 IP（count=1），一个 IP 有效期 3 分钟可重复使用
// 注意：URL 中的 count 参数由 buildProxyUrl() 动态覆盖为 1，无需手动改 .env.production
const RESIDENTIAL_PROXY_FETCH_QTY = 1;

// 方案 H：配额恢复重试间隔
// 某个代理源配额耗尽后（如 shenlongip 204 套餐过期/205 提取上限），间隔多久重新尝试该源
// 默认 10 分钟：避免配额耗尽的源被永久禁用，用户充值后能自动恢复
const QUOTA_RECOVERY_SEC = Number(process.env.RESIDENTIAL_PROXY_QUOTA_RECOVERY_SEC || 600);

// 方案 H：连续失败阈值，超过后暂时禁用该源（非配额耗尽的失败，如网络错误）
const SOURCE_MAX_CONSECUTIVE_FAILURES = Number(process.env.RESIDENTIAL_PROXY_SOURCE_MAX_FAILURES || 5);
const SOURCE_FAILURE_BACKOFF_SEC = Number(process.env.RESIDENTIAL_PROXY_SOURCE_BACKOFF_SEC || 120);

// shenlongip 208 频率太快：短暂等待后重试（默认 3 秒）
const RATE_LIMIT_BACKOFF_SEC = Number(process.env.RESIDENTIAL_PROXY_RATE_LIMIT_BACKOFF_SEC || 3);

// ============================================================
// 代理池数据结构
// ============================================================
export interface ProxyEntry {
  ip: string;
  port: string;
  server: string; // http://ip:port
  prov?: string;
  city?: string;
  isp?: string; // shenlongip 返回运营商字段
  expire?: string; // shenlongip 返回过期时间
  fetchedAt: number; // ms timestamp
}

interface ProxyPoolState {
  entries: ProxyEntry[];
  fetchedAt: number; // ms timestamp（最近一次提取时间）
  fetching: boolean; // 是否正在提取中（避免并发重复提取）
  lastError?: string;
  sourceIndex: number; // 方案 H：当前使用的代理源索引
}

// 方案 H：单个代理源的状态跟踪
interface ProxySourceState {
  url: string;
  quotaExhausted: boolean; // 配额是否耗尽（shenlongip 204 套餐过期 / 205 提取上限）
  quotaExhaustedAt: number; // 配额耗尽的时间戳（ms）
  rateLimited: boolean; // 是否被频率限制（shenlongip 208 频率太快）
  rateLimitedUntil: number; // 频率限制截止时间（ms）
  consecutiveFailures: number; // 连续失败次数（非配额耗尽、非频率限制）
  disabledUntil: number; // 因连续失败被禁用到的截止时间（ms）
  lastError?: string;
}

const poolState: ProxyPoolState = {
  entries: [],
  fetchedAt: 0,
  fetching: false,
  sourceIndex: 0,
};

// 方案 H：初始化所有代理源的状态
const sourceStates: ProxySourceState[] = RESIDENTIAL_PROXY_API_URLS.map((url) => ({
  url,
  quotaExhausted: false,
  quotaExhaustedAt: 0,
  rateLimited: false,
  rateLimitedUntil: 0,
  consecutiveFailures: 0,
  disabledUntil: 0,
  lastError: undefined,
}));

/**
 * 方案 H：获取下一个可用的代理源（跳过配额耗尽、频率限制和被禁用的源）
 * @returns 源索引，或 -1 表示所有源都不可用
 */
function getNextAvailableSource(): number {
  const now = Date.now();
  for (let i = 0; i < sourceStates.length; i++) {
    const idx = (poolState.sourceIndex + i) % sourceStates.length;
    const src = sourceStates[idx];
    // 跳过配额耗尽且未到恢复时间的源
    if (src.quotaExhausted) {
      const elapsed = (now - src.quotaExhaustedAt) / 1000;
      if (elapsed < QUOTA_RECOVERY_SEC) continue;
      // 超过恢复时间，重置配额状态（用户可能已充值）
      src.quotaExhausted = false;
      src.quotaExhaustedAt = 0;
      console.log(`[ResidentialProxy] 源 ${idx + 1} 配额恢复重试窗口已到，重新启用`);
    }
    // 跳过频率限制的源（短暂等待）
    if (src.rateLimited && src.rateLimitedUntil > now) continue;
    if (src.rateLimited && src.rateLimitedUntil <= now) {
      src.rateLimited = false;
    }
    // 跳过因连续失败被禁用的源
    if (src.disabledUntil > now) continue;
    return idx;
  }
  return -1;
}

/**
 * 方案 H：标记某个代理源配额耗尽
 */
function markSourceQuotaExhausted(sourceIdx: number, code: number, msg: string): void {
  if (sourceIdx < 0 || sourceIdx >= sourceStates.length) return;
  const src = sourceStates[sourceIdx];
  src.quotaExhausted = true;
  src.quotaExhaustedAt = Date.now();
  src.lastError = `quota_exhausted(code=${code}): ${msg.substring(0, 100)}`;
  console.warn(
    `[ResidentialProxy] 源 ${sourceIdx + 1}/${sourceStates.length} 配额耗尽(code=${code})，` +
    `禁用 ${QUOTA_RECOVERY_SEC}s 后重试: ${msg.substring(0, 80)}`
  );
}

/**
 * 方案 H：标记某个代理源被频率限制
 */
function markSourceRateLimited(sourceIdx: number, msg: string): void {
  if (sourceIdx < 0 || sourceIdx >= sourceStates.length) return;
  const src = sourceStates[sourceIdx];
  src.rateLimited = true;
  src.rateLimitedUntil = Date.now() + RATE_LIMIT_BACKOFF_SEC * 1000;
  src.lastError = `rate_limited: ${msg.substring(0, 100)}`;
  console.warn(
    `[ResidentialProxy] 源 ${sourceIdx + 1} 被频率限制(208)，` +
    `等待 ${RATE_LIMIT_BACKOFF_SEC}s 后重试: ${msg.substring(0, 80)}`
  );
}

/**
 * 方案 H：记录代理源失败（非配额耗尽、非频率限制）
 */
function recordSourceFailure(sourceIdx: number, error: string): void {
  if (sourceIdx < 0 || sourceIdx >= sourceStates.length) return;
  const src = sourceStates[sourceIdx];
  src.consecutiveFailures += 1;
  src.lastError = error.substring(0, 200);
  if (src.consecutiveFailures >= SOURCE_MAX_CONSECUTIVE_FAILURES) {
    src.disabledUntil = Date.now() + SOURCE_FAILURE_BACKOFF_SEC * 1000;
    console.warn(
      `[ResidentialProxy] 源 ${sourceIdx + 1} 连续失败 ${src.consecutiveFailures} 次，` +
      `禁用 ${SOURCE_FAILURE_BACKOFF_SEC}s`
    );
  }
}

/**
 * 方案 H：记录代理源成功（重置失败计数）
 */
function recordSourceSuccess(sourceIdx: number): void {
  if (sourceIdx < 0 || sourceIdx >= sourceStates.length) return;
  const src = sourceStates[sourceIdx];
  src.consecutiveFailures = 0;
  src.disabledUntil = 0;
  src.quotaExhausted = false;
  src.quotaExhaustedAt = 0;
  src.rateLimited = false;
  src.rateLimitedUntil = 0;
}

// ============================================================
// 工具函数
// ============================================================
export function isResidentialProxyEnabled(): boolean {
  // 必须同时满足：环境变量开关=true 且至少配置了一个代理源
  return USE_RESIDENTIAL_PROXY && RESIDENTIAL_PROXY_API_URLS.length > 0;
}

export function getResidentialProxyConfig() {
  return {
    enabled: isResidentialProxyEnabled(),
    apiUrlConfigured: RESIDENTIAL_PROXY_API_URLS.length > 0,
    sourceCount: RESIDENTIAL_PROXY_API_URLS.length,
    currentSourceIndex: poolState.sourceIndex,
    sourceStates: sourceStates.map((s, i) => ({
      index: i + 1,
      quotaExhausted: s.quotaExhausted,
      rateLimited: s.rateLimited && s.rateLimitedUntil > Date.now(),
      consecutiveFailures: s.consecutiveFailures,
      disabled: s.disabledUntil > Date.now(),
      lastError: s.lastError || null,
    })),
    ttlSec: RESIDENTIAL_PROXY_TTL_SEC,
    poolSize: RESIDENTIAL_PROXY_POOL_SIZE,
    currentPoolCount: poolState.entries.length,
    lastFetchedAt: poolState.fetchedAt ? new Date(poolState.fetchedAt).toISOString() : null,
    lastError: poolState.lastError || null,
  };
}

/**
 * 检查池中的IP是否已过期（超过 TTL）
 */
function isPoolExpired(): boolean {
  if (poolState.entries.length === 0) return true;
  const ageMs = Date.now() - poolState.fetchedAt;
  return ageMs > RESIDENTIAL_PROXY_TTL_SEC * 1000;
}

/**
 * 构建代理 API URL（保留原始 pattern，不强制覆盖）
 *
 * 2026-08-03 修复：shenlongip 不支持 pattern=json（返回空），必须使用 pattern=txt。
 * 之前强制覆盖 pattern=json 导致所有提取请求返回空，代理池无法工作。
 *
 * shenlongip 要求：
 * - count=1：一次只调用 1 个 IP（虽然 API 可能忽略此参数返回多个，客户端只取第一个）
 * - pattern=txt：必须使用 txt 格式（json 格式返回空）
 *
 * @param sourceUrl 指定代理源的 URL
 */
function buildProxyUrl(sourceUrl: string): string {
  if (!sourceUrl) return '';
  let url = sourceUrl;
  // 强制 count=1（shenlongip 要求一次只调用 1 个 IP）
  // 注意：实测 count=1 可能被 API 忽略（返回多个），客户端只取第一个
  if (url.includes('count=')) {
    url = url.replace(/count=\d+/, 'count=1');
  } else {
    const sep = url.includes('?') ? '&' : '?';
    url = `${url}${sep}count=1`;
  }
  // 2026-08-03 修复：不强制 pattern=json（shenlongip 不支持，返回空）
  // 保留原始 URL 中的 pattern 参数（通常是 txt）
  // 如果 URL 中没有 pattern 参数，默认添加 pattern=txt
  if (!url.includes('pattern=')) {
    const sep = url.includes('?') ? '&' : '?';
    url = `${url}${sep}pattern=txt`;
  }
  return url;
}

/**
 * 解析 shenlongip txt 格式响应
 *
 * txt 格式：每行一个 ip:port，例如：
 *   115.213.245.49:40015
 *   183.7.16.252:40049
 *
 * 2026-08-03 修复：shenlongip 不支持 pattern=json，必须解析 txt 格式。
 * 只取第一个 IP（count=1 要求一次只调用 1 个 IP）。
 *
 * @param text txt 格式文本
 * @returns 代理条目数组（通常只有 1 个）
 */
function parseTxtResponse(text: string): ProxyEntry[] {
  const lines = text.split(/\r?\n/).map(l => l.trim()).filter(l => l.length > 0);
  const entries: ProxyEntry[] = [];
  for (const line of lines) {
    // 匹配 ip:port 格式
    const match = line.match(/^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d+)$/);
    if (!match) continue;
    const ip = match[1];
    const port = match[2];
    entries.push({
      ip,
      port,
      server: `http://${ip}:${port}`,
      fetchedAt: Date.now(),
    });
    // 只取第一个 IP（shenlongip 要求一次只调用 1 个 IP）
    break;
  }
  return entries;
}

// ============================================================
// 方案 H 11.5.1-1 多源扩展：kuaidaili / ipipgo 专用解析器（2026-08-04 实施）
// ============================================================
// 统一解析结果：entries 为成功解析的代理条目；errorCode 非空表示业务错误码，
// 由上层 fetchProxiesFromApi 按统一错误码映射（mapErrorCode）处理源状态。
interface ParsedProxyResponse {
  entries: ProxyEntry[];
  errorCode?: number;
  error?: string;
}

/**
 * 统一错误码映射（shenlongip / kuaidaili / ipipgo → 统一状态）
 *
 * | 统一状态                  | shenlongip | kuaidaili | ipipgo  |
 * |---------------------------|------------|-----------|---------|
 * | quota_exhausted（配额耗尽）| 204/205    | 2         | 4001    |
 * | rate_limited（频率限制）   | 208        | 4         | 4002    |
 * | temporarily_unavailable   | 206        | 11        | 4003    |
 */
type UnifiedProxyError = 'quota_exhausted' | 'rate_limited' | 'temporarily_unavailable' | 'other';

function mapErrorCode(url: string, code: number): UnifiedProxyError {
  if (url.includes('kuaidaili.com')) {
    if (code === 2) return 'quota_exhausted';
    if (code === 4) return 'rate_limited';
    if (code === 11) return 'temporarily_unavailable';
    return 'other';
  }
  if (url.includes('ipipgo.com')) {
    if (code === 4001) return 'quota_exhausted';
    if (code === 4002) return 'rate_limited';
    if (code === 4003) return 'temporarily_unavailable';
    return 'other';
  }
  // shenlongip（默认）
  if (code === 204 || code === 205) return 'quota_exhausted';
  if (code === 208) return 'rate_limited';
  if (code === 206) return 'temporarily_unavailable';
  return 'other';
}

/**
 * kuaidaili 响应解析
 *
 * 成功格式：
 *   {"code":0,"data":{"count":1,"proxy_list":[{"ip":"1.2.3.4","port":8080,"region":"江苏","isp":"电信"}]}}
 * 失败格式：
 *   {"code":2,"msg":"提取数量超限"} / {"code":4,"msg":"提取过快"} / {"code":11,"msg":"无可用IP"}
 */
function parseKuaidailiResponse(text: string): ParsedProxyResponse {
  try {
    const json = JSON.parse(text) as {
      code?: number;
      msg?: string;
      data?: { count?: number; proxy_list?: Array<{ ip?: string; port?: number | string; region?: string; isp?: string }> };
    };
    if (!json) return { entries: [] };
    if (typeof json.code === 'number' && json.code !== 0) {
      return { entries: [], errorCode: json.code, error: json.msg || `kuaidaili code=${json.code}` };
    }
    const list = json.data?.proxy_list || [];
    const entries: ProxyEntry[] = [];
    for (const item of list) {
      const ip = String(item.ip || '').trim();
      const port = String(item.port ?? '').trim();
      if (!ip || !port) continue;
      entries.push({
        ip,
        port,
        server: `http://${ip}:${port}`,
        prov: item.region ? String(item.region) : undefined,
        isp: item.isp ? String(item.isp) : undefined,
        fetchedAt: Date.now(),
      });
      break; // 只取第一个
    }
    return { entries };
  } catch {
    return { entries: [] };
  }
}

/**
 * ipipgo 响应解析
 *
 * 成功格式：
 *   {"code":200,"data":[{"ip":"1.2.3.4","port":8080,"expire_time":"2026-08-03 12:00:00"}]}
 * 失败格式：
 *   {"code":4001,"msg":"套餐过期"} / {"code":4002,"msg":"频率限制"} / {"code":4003,"msg":"无可用IP"}
 */
function parseIpipgoResponse(text: string): ParsedProxyResponse {
  try {
    const json = JSON.parse(text) as {
      code?: number;
      msg?: string;
      data?: Array<{ ip?: string; port?: number | string; expire_time?: string; region?: string }>;
    };
    if (!json) return { entries: [] };
    if (typeof json.code === 'number' && json.code !== 200) {
      return { entries: [], errorCode: json.code, error: json.msg || `ipipgo code=${json.code}` };
    }
    const list = Array.isArray(json.data) ? json.data : [];
    const entries: ProxyEntry[] = [];
    for (const item of list) {
      const ip = String(item.ip || '').trim();
      const port = String(item.port ?? '').trim();
      if (!ip || !port) continue;
      entries.push({
        ip,
        port,
        server: `http://${ip}:${port}`,
        prov: item.region ? String(item.region) : undefined,
        expire: item.expire_time ? String(item.expire_time) : undefined,
        fetchedAt: Date.now(),
      });
      break; // 只取第一个
    }
    return { entries };
  } catch {
    return { entries: [] };
  }
}

/**
 * shenlongip / 通用响应解析（JSON 错误码 + JSON data + txt 兜底）
 *
 * shenlongip 成功格式（txt）：
 *   115.213.245.49:40015
 * shenlongip 成功格式（json）：
 *   {"data":[{"ip":"1.2.3.4","port":"8080","expire":"...","city":"北京","isp":"电信"}]}
 * shenlongip 失败格式：
 *   {"code":204,"msg":"套餐已过期"} / {"code":208,"msg":"提取频率太快"} / {"code":206,"msg":"暂无可用IP"}
 */
function parseGenericResponse(text: string): ParsedProxyResponse {
  let entries: ProxyEntry[] = [];
  let parsedAsJson = false;
  try {
    const json = JSON.parse(text) as {
      code?: number;
      msg?: string;
      data?: Array<{ ip?: string; port?: string; expire?: string; city?: string; isp?: string }>;
    };
    // 业务错误码（code 存在且不为 200）
    if (json && typeof json.code === 'number' && json.code !== 200) {
      return { entries: [], errorCode: json.code, error: json.msg || `code=${json.code}` };
    }
    // JSON 成功响应：解析 data 数组
    if (json && Array.isArray(json.data)) {
      parsedAsJson = true;
      for (const item of json.data) {
        const ip = String(item.ip || '').trim();
        const port = String(item.port || '').trim();
        if (!ip || !port) continue;
        entries.push({
          ip,
          port,
          server: `http://${ip}:${port}`,
          city: item.city ? String(item.city) : undefined,
          isp: item.isp ? String(item.isp) : undefined,
          expire: item.expire ? String(item.expire) : undefined,
          fetchedAt: Date.now(),
        });
        break; // 只取第一个
      }
    }
  } catch {
    // 非 JSON（txt 格式），走下方兜底
  }
  if (entries.length === 0 && !parsedAsJson) {
    entries = parseTxtResponse(text);
  }
  return { entries };
}

/**
 * 按代理源 URL 域名分发到对应解析器（方案 H 多源扩展）
 *
 * kuaidaili / ipipgo 用专用解析器（响应结构不同）；shenlongip 及其他源用通用解析器
 * （兼容 JSON 错误码 / JSON data / txt 三种格式）。
 */
function parseApiResponse(url: string, text: string): ParsedProxyResponse {
  if (url.includes('kuaidaili.com')) return parseKuaidailiResponse(text);
  if (url.includes('ipipgo.com')) return parseIpipgoResponse(text);
  return parseGenericResponse(text);
}

/**
 * 从指定代理源 API 提取住址IP（每次只提取 1 个）
 * 方案 H：支持多代理源，配额耗尽自动切换
 *
 * shenlongip 返回格式（2026-08-03 修复：使用 txt 格式，json 格式返回空）：
 * - 成功（txt）：每行一个 ip:port，例如 "115.213.245.49:40015"
 * - 成功（json）：{"data":[{"ip":"1.2.3.4","port":"8080"}]}
 * - 失败（json）：{"code":204,"msg":"套餐已过期"}
 * - 频率限制：返回空内容或 {"code":208,"msg":"提取频率太快"}
 *
 * @param sourceIdx 指定代理源索引（方案 H 多源）
 * @returns 提取到的代理条目数组（通常只有 1 个），失败返回空数组
 */
async function fetchProxiesFromApi(sourceIdx: number = 0): Promise<ProxyEntry[]> {
  if (sourceIdx < 0 || sourceIdx >= sourceStates.length) {
    return [];
  }
  const sourceUrl = sourceStates[sourceIdx].url;
  if (!sourceUrl) {
    return [];
  }
  const url = buildProxyUrl(sourceUrl);
  const fetchStart = Date.now();
  try {
    // 使用 AbortController 实现超时
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), RESIDENTIAL_PROXY_FETCH_TIMEOUT_MS);
    try {
      const resp = await fetch(url, {
        method: 'GET',
        signal: controller.signal,
      });
      if (!resp.ok) {
        const errText = await resp.text().catch(() => '');
        // HTTP 层面错误（非 200）
        recordSourceFailure(sourceIdx, `HTTP ${resp.status}: ${errText.substring(0, 200)}`);
        throw new Error(`HTTP ${resp.status}: ${errText.substring(0, 200)}`);
      }

      // 2026-08-03 修复：先读取 text，再尝试 JSON 解析（shenlongip 主要返回 txt）
      const rawText = await resp.text();
      if (!rawText || rawText.trim().length === 0) {
        // 空响应：可能是频率限制（208）或暂无可用 IP（206）
        // shenlongip 频率限制时返回空内容而非 JSON 错误
        markSourceRateLimited(sourceIdx, '空响应（疑似频率限制208）');
        throw new Error('空响应（疑似频率限制208）');
      }

      // 2026-08-04 方案 H 多源扩展：按代理源域名分发到专用解析器，统一错误码映射
      const parsed = parseApiResponse(sourceUrl, rawText);
      if (parsed.errorCode !== undefined) {
        const code = parsed.errorCode;
        const msg = parsed.error || `code=${code}`;
        const ucode = mapErrorCode(sourceUrl, code);
        if (ucode === 'quota_exhausted') {
          // 配额耗尽（204/205/2/4001）→ 长时间禁用，恢复窗口后自动重试
          markSourceQuotaExhausted(sourceIdx, code, msg);
        } else if (ucode === 'rate_limited') {
          // 频率限制（208/4/4002）→ 短暂等待后重试
          markSourceRateLimited(sourceIdx, msg);
        } else if (ucode === 'temporarily_unavailable') {
          // 无可用 IP（206/11/4003）→ 临时性，记录失败但不禁用
          recordSourceFailure(sourceIdx, `temporarily_unavailable(${code}): ${msg}`);
        } else {
          // 其他错误（格式/KEY/数量等）
          recordSourceFailure(sourceIdx, `API错误(code=${code}): ${msg}`);
        }
        throw new Error(`API错误: code=${code} msg=${msg}`);
      }

      const entries = parsed.entries;
      if (entries.length === 0) {
        // 两种格式都没解析出 IP
        recordSourceFailure(sourceIdx, `无法解析响应: ${rawText.substring(0, 200)}`);
        throw new Error(`无法解析响应: ${rawText.substring(0, 200)}`);
      }

      // 方案 H：记录成功，重置失败计数
      recordSourceSuccess(sourceIdx);
      console.log(
        `[ResidentialProxy] ✓ 源 ${sourceIdx + 1}/${sourceStates.length} 提取成功: ` +
        `${entries.length} 个IP (${entries[0].ip}:${entries[0].port})，耗时 ${Date.now() - fetchStart}ms`
      );
      return entries;
    } finally {
      clearTimeout(timeoutId);
    }
  } catch (e: any) {
    const errType = safeErrorType(e);
    const errMsg = e instanceof Error ? e.message : String(e);
    poolState.lastError = `${errType}: ${errMsg.substring(0, 200)}`;
    console.warn(
      `[ResidentialProxy] ✗ 源 ${sourceIdx + 1}/${sourceStates.length} 提取失败: ` +
      `${errType} ${errMsg.substring(0, 200)}，耗时 ${Date.now() - fetchStart}ms`
    );
    return [];
  }
}

/**
 * 刷新代理池（按需补充，配额最友好）
 *
 * shenlongip 策略：
 * - 一次只提取 1 个 IP（count=1），有效期 3 分钟
 * - 池中 IP 在 TTL（3分钟）内复用，不消耗配额
 * - 池为空或已过期 → 提取 1 个新 IP
 *
 * 方案 H 优化：多代理源切换
 * - 当前源配额耗尽（204/205）→ 自动切换到下一个可用源
 * - 当前源频率限制（208）→ 短暂等待后重试同一源
 * - 所有源都耗尽 → 返回 null（上层降级到服务器 IP）
 * - 配额恢复窗口（默认 10 分钟）后自动重试已耗尽的源
 *
 * 2026-08-03 修复：增加最小提取间隔（MIN_FETCH_INTERVAL_MS）
 * shenlongip 连续请求太快会返回空（疑似频率限制 208），即使池已过期也要等待间隔。
 * 实测：连续两次请求间隔 < 1 秒时，第二次返回空。
 *
 * 并发保护：fetching=true 时跳过（避免并发重复提取）
 */
// 2026-08-03 修复：最小提取间隔，避免 shenlongip 频率限制
const MIN_FETCH_INTERVAL_MS = Number(process.env.RESIDENTIAL_PROXY_MIN_FETCH_INTERVAL_MS || 2000);
let lastFetchAttemptAt = 0;

async function refreshPoolIfNeeded(): Promise<void> {
  if (poolState.fetching) {
    // 已有提取任务在执行，等待其完成
    return;
  }
  if (!isPoolExpired()) {
    // 池中仍有可用 IP 且未过期，不消耗配额
    return;
  }
  // 2026-08-03 修复：频率限制保护，两次提取之间至少间隔 MIN_FETCH_INTERVAL_MS
  const elapsedSinceLastFetch = Date.now() - lastFetchAttemptAt;
  if (lastFetchAttemptAt > 0 && elapsedSinceLastFetch < MIN_FETCH_INTERVAL_MS) {
    console.log(
      `[ResidentialProxy] 距离上次提取仅 ${elapsedSinceLastFetch}ms < ${MIN_FETCH_INTERVAL_MS}ms，跳过本次提取避免频率限制`
    );
    return;
  }
  lastFetchAttemptAt = Date.now();
  poolState.fetching = true;
  try {
    // 方案 H：遍历所有可用代理源，配额耗尽自动切换
    let newEntries: ProxyEntry[] = [];
    const totalSources = sourceStates.length;
    for (let attempt = 0; attempt < totalSources; attempt++) {
      const sourceIdx = getNextAvailableSource();
      if (sourceIdx < 0) {
        // 所有代理源都不可用（配额耗尽或被禁用）
        console.warn(
          `[ResidentialProxy] 所有 ${totalSources} 个代理源均不可用，降级到服务器 IP`
        );
        break;
      }
      poolState.sourceIndex = sourceIdx;
      newEntries = await fetchProxiesFromApi(sourceIdx);
      if (newEntries.length > 0) {
        // 提取成功，更新池
        poolState.entries = newEntries;
        poolState.fetchedAt = Date.now();
        poolState.lastError = undefined;
        return;
      }
      // 当前源失败，继续尝试下一个源
      console.log(
        `[ResidentialProxy] 源 ${sourceIdx + 1} 提取失败，尝试下一个源（${attempt + 1}/${totalSources}）`
      );
    }
    // 所有源都尝试失败
    if (poolState.entries.length === 0) {
      // 首次提取失败，记录时间避免每次请求都重试
      poolState.fetchedAt = Date.now();
    }
    // 如果已有IP但过期，且本次提取失败，保留旧IP继续用（降级策略）
  } finally {
    poolState.fetching = false;
  }
}

/**
 * 从池中随机取一个代理（3分钟TTL内复用）
 *
 * 策略：
 * - 池为空或过期 → 触发刷新
 * - 刷新后池仍为空 → 返回 null（上层降级到无代理）
 * - 池中有IP → 随机返回一个
 *
 * @returns { server, username?, password?, source: 'residential_ip', ip, port } 或 null
 */
export async function getResidentialProxy(): Promise<{
  server: string;
  username?: string;
  password?: string;
  source: 'residential_ip';
  ip: string;
  port: string;
  prov?: string;
  city?: string;
} | null> {
  if (!isResidentialProxyEnabled()) {
    return null;
  }
  await refreshPoolIfNeeded();
  if (poolState.entries.length === 0) {
    return null;
  }
  // 2026-08-04 质量评估：优先从非黑名单 IP 中选取；若全部黑名单则回退全池（避免空池）
  const qualityPool = poolState.entries.filter((e) => !proxyQualityTracker.isBlacklisted(e.ip));
  const pool = qualityPool.length > 0 ? qualityPool : poolState.entries;
  // 随机选一个IP（避免热点）
  const idx = Math.floor(Math.random() * pool.length);
  const entry = pool[idx];
  return {
    server: entry.server,
    source: 'residential_ip',
    ip: entry.ip,
    port: entry.port,
    prov: entry.prov,
    city: entry.city,
  };
}

/**
 * 标记某个代理使用失败（简单计数，达到阈值后从池中移除）
 *
 * 注意：shenlongip 短效IP本身就是3分钟有效，且 IP 失败可能是账号本身被 punish 而非 IP 问题，
 * 因此不做激进剔除，仅在连接失败时记录日志。
 */
export function reportProxyFailure(ip: string, reason: string): void {
  console.warn(`[ResidentialProxy] 代理使用失败 ip=${ip} reason=${reason.substring(0, 100)}`);
  // 不立即从池中移除，让 TTL 自然过期
  // 如果未来需要更激进的策略，可以在这里实现计数+剔除
}

/**
 * 释放代理池资源（应用关闭时调用）
 */
export function closeResidentialProxyPool(): void {
  poolState.entries = [];
  poolState.fetchedAt = 0;
  poolState.fetching = false;
}

// ============================================================
// 方案 H 11.4.4：shenlongip 白名单自动管理（2026-08-04 实施）
// ============================================================
//
// 问题：shenlongip 要求服务器 IP 在白名单中，否则代理连接返回 407。
// 服务器 IP 变更时需手动登录后台添加，容易遗漏导致代理池失效。
//
// 本实现：
// 1. 启动/提取前自动获取本机公网 IP（ipify.org，带超时兜底）
// 2. 调用 shenlongip /white/fetch 查询白名单
// 3. 本机 IP 不在白名单时调用 /white/add 自动添加
// 4. 失败仅告警不阻塞（用户可后续手动配置）
//
// 白名单 API 参数（key/sign 与提取 API 不同，可用环境变量覆盖）：
// - SHENLONGIP_WHITE_KEY（shenlongip 账号，必须通过环境变量配置，无默认值）
// - SHENLONGIP_WHITE_SIGN（默认取自提取 URL 的 sign 参数，或环境变量覆盖）
const SHENLONGIP_WHITE_BASE = process.env.SHENLONGIP_WHITE_API_URL || 'http://api.shenlongip.com/white';
const SHENLONGIP_WHITE_KEY = process.env.SHENLONGIP_WHITE_KEY || '';
const WHITELIST_FETCH_TIMEOUT_MS = 6000;
// 每次启动最多自动添加 1 次（避免反复请求导致频率限制）
let whitelistAutoChecked = false;

/** 从提取 URL 中解析 sign 参数（白名单 API 与提取 API 通常共用 sign） */
function extractSignFromSourceUrl(url: string): string {
  const m = url.match(/[?&]sign=([^&]+)/);
  return m ? decodeURIComponent(m[1]) : '';
}

/** 获取本机公网 IP（失败返回 null，不阻塞主流程） */
export async function getPublicIp(): Promise<string | null> {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), WHITELIST_FETCH_TIMEOUT_MS);
    try {
      const resp = await fetch('https://api.ipify.org?format=json', { signal: controller.signal });
      if (!resp.ok) return null;
      const data = (await resp.json()) as { ip?: string };
      return data.ip || null;
    } finally {
      clearTimeout(timeoutId);
    }
  } catch (e: any) {
    console.warn(`[ResidentialProxy] 获取公网 IP 失败: ${safeErrorType(e)}`);
    return null;
  }
}

/**
 * 自动检查并添加 shenlongip 白名单
 *
 * 流程：
 * 1. 获取本机公网 IP（失败则跳过，白名单已手动配置也可用）
 * 2. 调用 /white/fetch 查询白名单
 * 3. IP 不在白名单 → 调用 /white/add
 *
 * 幂等性：每次进程启动最多执行一次（whitelistAutoChecked 标志）
 * 失败容忍：任何步骤失败仅告警，不阻塞代理池启动
 */
export async function ensureShenlongipWhitelist(): Promise<{
  checked: boolean;
  publicIp: string | null;
  inWhitelist: boolean;
  added: boolean;
  error?: string;
}> {
  const result = {
    checked: false,
    publicIp: null as string | null,
    inWhitelist: false,
    added: false,
  };
  // 未启用住宅代理或无代理源时跳过
  if (!USE_RESIDENTIAL_PROXY || RESIDENTIAL_PROXY_API_URLS.length === 0) {
    return { ...result, error: 'residential_proxy_not_enabled' };
  }
  // 找到 shenlongip 源（白名单管理仅适用于 shenlongip）
  const shenlongipSource = RESIDENTIAL_PROXY_API_URLS.find((u) => u.includes('shenlongip.com'));
  if (!shenlongipSource) {
    return { ...result, error: 'no_shenlongip_source' };
  }
  if (whitelistAutoChecked) {
    return { ...result, error: 'already_checked' };
  }
  whitelistAutoChecked = true;

  try {
    const publicIp = await getPublicIp();
    if (!publicIp) {
      return { ...result, error: 'get_public_ip_failed' };
    }
    result.publicIp = publicIp;

    const sign = process.env.SHENLONGIP_WHITE_SIGN || extractSignFromSourceUrl(shenlongipSource) || '';
    if (!sign) {
      return { ...result, error: 'white_sign_missing' };
    }
    if (!SHENLONGIP_WHITE_KEY) {
      return { ...result, error: 'white_key_missing' };
    }

    // 1. 查询白名单
    const fetchUrl = `${SHENLONGIP_WHITE_BASE}/fetch?key=${SHENLONGIP_WHITE_KEY}&sign=${encodeURIComponent(sign)}`;
    let whitelisted = false;
    try {
      const resp = await fetch(fetchUrl, { signal: AbortSignal.timeout(WHITELIST_FETCH_TIMEOUT_MS) });
      const text = await resp.text();
      // 响应可能是 json（{"data":[...]}）或 txt（每行一个 IP）
      const ips: string[] = [];
      try {
        const json = JSON.parse(text) as { data?: string[] | Array<{ ip?: string }> };
        if (Array.isArray(json.data)) {
          for (const item of json.data) {
            if (typeof item === 'string') ips.push(item);
            else if (item && typeof item === 'object' && 'ip' in item) ips.push(String((item as { ip?: string }).ip));
          }
        }
      } catch {
        // txt 格式：每行一个 IP
        ips.push(...text.split(/\r?\n/).map((l) => l.trim()).filter((l) => /^\d+\.\d+\.\d+\.\d+$/.test(l)));
      }
      whitelisted = ips.some((ip) => ip === publicIp);
      result.inWhitelist = whitelisted;
      if (whitelisted) {
        console.log(`[ResidentialProxy] ✓ 公网 IP ${publicIp} 已在 shenlongip 白名单`);
      } else {
        console.warn(`[ResidentialProxy] ⚠ 公网 IP ${publicIp} 不在 shenlongip 白名单，尝试自动添加（当前白名单 ${ips.length} 个）`);
      }
    } catch (e: any) {
      console.warn(`[ResidentialProxy] 白名单查询失败: ${safeErrorType(e)}，跳过自动添加`);
      return { ...result, error: `fetch_failed: ${safeErrorType(e)}` };
    }

    // 2. 不在白名单则添加
    if (!whitelisted) {
      try {
        const addUrl = `${SHENLONGIP_WHITE_BASE}/add?key=${SHENLONGIP_WHITE_KEY}&sign=${encodeURIComponent(sign)}&ip=${publicIp}`;
        const resp = await fetch(addUrl, { signal: AbortSignal.timeout(WHITELIST_FETCH_TIMEOUT_MS) });
        const text = await resp.text();
        result.added = resp.ok || /success|ok|添加/i.test(text);
        if (result.added) {
          console.log(`[ResidentialProxy] ✓ 已自动添加公网 IP ${publicIp} 到 shenlongip 白名单`);
        } else {
          console.warn(`[ResidentialProxy] 白名单添加返回非成功: ${resp.status} ${text.substring(0, 100)}`);
        }
      } catch (e: any) {
        console.warn(`[ResidentialProxy] 白名单自动添加失败: ${safeErrorType(e)}`);
        return { ...result, error: `add_failed: ${safeErrorType(e)}` };
      }
    }

    result.checked = true;
    return result;
  } catch (e: any) {
    return { ...result, error: `unexpected: ${safeErrorType(e)}` };
  }
}

// ============================================================
// 方案 H 11.5.1-3：住址IP质量评估（ProxyQualityTracker，2026-08-04 实施）
// ============================================================
// 目标：自动剔除被 Baxia 标记的低质量 IP，提升单 IP 的求解成功率。
// 评估维度（简化实现，按成功/失败计数评分，对应文档 40% 求解成功率 + 30% Token API 成功率）：
//   score = 成功次数 / (成功+失败) * 100
// 评分阈值：
//   ≥ 70：优质 IP，优先分配
//   40-70：普通 IP，正常使用
//   < 40：低质量 IP，加入黑名单 30 分钟（默认 PROXY_QUALITY_BLACKLIST_SEC）
// 上报机制：automation-service 的 ws_token.py / captcha_solver.py 调用
//   POST /api/proxy/report-quality（server.ts）→ recordResult(ip, success)
interface ProxyQualityStat {
  success: number;
  fail: number;
  lastUsed: number; // ms timestamp
}

const QUALITY_BLACKLIST_SEC = Number(process.env.PROXY_QUALITY_BLACKLIST_SEC || 30 * 60);
const QUALITY_BLACKLIST_THRESHOLD = 40;
const QUALITY_DEFAULT_SCORE = 50; // 新 IP 默认评分

export class ProxyQualityTracker {
  private stats = new Map<string, ProxyQualityStat>();
  private blacklist = new Map<string, number>(); // ip -> 解禁时间戳（ms）

  /** 记录一次代理使用结果（成功/失败） */
  recordResult(ip: string, success: boolean): void {
    if (!ip) return;
    const stat = this.stats.get(ip) || { success: 0, fail: 0, lastUsed: 0 };
    if (success) stat.success++;
    else stat.fail++;
    stat.lastUsed = Date.now();
    this.stats.set(ip, stat);

    // 失败导致评分跌破阈值 → 加入黑名单（30 分钟）
    if (!success && this.getScore(ip) < QUALITY_BLACKLIST_THRESHOLD) {
      this.blacklist.set(ip, Date.now() + QUALITY_BLACKLIST_SEC * 1000);
      console.warn(
        `[ProxyQuality] IP ${ip} 评分 ${this.getScore(ip)} < ${QUALITY_BLACKLIST_THRESHOLD}，` +
        `加入黑名单 ${QUALITY_BLACKLIST_SEC}s（失败 ${stat.fail} 次）`
      );
    }
  }

  /** 获取 IP 质量评分（0-100），新 IP 默认 50 分 */
  getScore(ip: string): number {
    const stat = this.stats.get(ip);
    if (!stat) return QUALITY_DEFAULT_SCORE;
    const total = stat.success + stat.fail;
    if (total === 0) return QUALITY_DEFAULT_SCORE;
    return Math.round((stat.success / total) * 100);
  }

  /** 是否在黑名单中（黑名单到期自动解禁） */
  isBlacklisted(ip: string): boolean {
    const until = this.blacklist.get(ip);
    if (!until) return false;
    if (until <= Date.now()) {
      this.blacklist.delete(ip);
      return false;
    }
    return true;
  }

  /** 质量统计快照（供运维/诊断） */
  getSnapshot(): Array<{ ip: string; success: number; fail: number; score: number; blacklisted: boolean; lastUsed: string | null }> {
    const now = Date.now();
    const list: Array<{ ip: string; success: number; fail: number; score: number; blacklisted: boolean; lastUsed: string | null }> = [];
    for (const [ip, stat] of this.stats) {
      list.push({
        ip,
        success: stat.success,
        fail: stat.fail,
        score: this.getScore(ip),
        blacklisted: (this.blacklist.get(ip) || 0) > now,
        lastUsed: stat.lastUsed ? new Date(stat.lastUsed).toISOString() : null,
      });
    }
    list.sort((a, b) => (b.fail - a.fail) || (b.score - a.score));
    return list;
  }
}

export const proxyQualityTracker = new ProxyQualityTracker();
