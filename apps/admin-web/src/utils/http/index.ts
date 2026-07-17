/**
 * HTTP 请求封装模块
 * 基于 Axios 封装的 HTTP 请求工具，提供统一的请求/响应处理
 *
 * ## 主要功能
 *
 * - 请求/响应拦截器（自动添加 Token、统一错误处理）
 * - 401 未授权自动登出（带防抖机制）
 * - 请求失败自动重试（可配置）
 * - 统一的成功/错误消息提示
 * - 支持 GET/POST/PUT/DELETE 等常用方法
 *
 * @module utils/http
 * @author Art Design Pro Team
 */

import axios, { AxiosRequestConfig, AxiosResponse, InternalAxiosRequestConfig } from 'axios'
import { useUserStore } from '@/store/modules/user'
import { ApiStatus } from './status'
import {
  createHttpError,
  extractRequestId,
  HttpError,
  handleError,
  showError,
  showSuccess
} from './error'
import {
  isAuthorizationForCurrentSession,
  selectSafeServerMessage,
  shouldRetryHttpRequest
} from './error-policy'
import { $t } from '@/locales'
import { BaseResponse } from '@/types'

/** 请求配置常量 */
const REQUEST_TIMEOUT = 10000
const MAX_RETRIES = 1
const RETRY_DELAY = 800
const UNAUTHORIZED_DEBOUNCE_TIME = 3000
/** GET 请求默认缓存时间（毫秒），0 表示不缓存 */
const DEFAULT_CACHE_TTL = 0
/** pending 请求兜底清理时长（毫秒）：比 axios timeout 长 3 倍，防止网络挂死导致相同 key 请求永久 await */
const PENDING_REQUEST_MAX_TTL_MS = 30000

/** 401防抖状态 */
let isUnauthorizedErrorShown = false
let unauthorizedTimer: NodeJS.Timeout | null = null

/** 扩展 AxiosRequestConfig */
interface ExtendedAxiosRequestConfig extends AxiosRequestConfig {
  showErrorMessage?: boolean
  showSuccessMessage?: boolean
  /** 缓存时间（毫秒），仅对 GET 请求生效。设置后相同 URL+params 的请求在 TTL 内返回缓存数据 */
  cacheTtl?: number
  /** 是否跳过请求去重（默认 false，相同 URL 的并发 GET 请求会合并） */
  skipDedupe?: boolean
}

/** 缓存条目 */
interface CacheEntry<T = any> {
  data: T
  expireAt: number
}

/** GET 请求缓存（内存） */
const responseCache = new Map<string, CacheEntry>()

/** 进行中的请求去重（同一 key 的并发请求共享同一个 Promise） */
const pendingRequests = new Map<string, Promise<any>>()

/** 生成请求唯一 key（用于缓存和去重） */
function buildRequestKey(config: AxiosRequestConfig): string {
  const method = (config.method || 'GET').toUpperCase()
  const url = config.url || ''
  const params = config.params ? JSON.stringify(config.params) : ''
  return `${method}:${url}:${params}`
}

/** 判断是否为可缓存的 GET 请求 */
function isCacheable(config: ExtendedAxiosRequestConfig): boolean {
  const method = (config.method || 'GET').toUpperCase()
  return method === 'GET' && (config.cacheTtl ?? DEFAULT_CACHE_TTL) > 0
}

/** 读取缓存 */
function readCache<T>(key: string): T | null {
  const entry = responseCache.get(key)
  if (!entry) return null
  if (Date.now() > entry.expireAt) {
    responseCache.delete(key)
    return null
  }
  return entry.data as T
}

/** 写入缓存 */
function writeCache<T>(key: string, data: T, ttl: number): void {
  responseCache.set(key, { data, expireAt: Date.now() + ttl })
}

/** 清空所有缓存（登出时调用） */
export function clearHttpCache(): void {
  responseCache.clear()
  pendingRequests.clear()
}

let fallbackRequestSequence = 0

function createRequestId(): string {
  const cryptoApi = globalThis.crypto
  if (typeof cryptoApi?.randomUUID === 'function') {
    return `admin-${cryptoApi.randomUUID()}`
  }
  if (typeof cryptoApi?.getRandomValues === 'function') {
    const values = new Uint32Array(2)
    cryptoApi.getRandomValues(values)
    return `admin-${values[0].toString(16).padStart(8, '0')}${values[1].toString(16).padStart(8, '0')}`
  }
  fallbackRequestSequence = (fallbackRequestSequence + 1) % Number.MAX_SAFE_INTEGER
  return `admin-${Date.now().toString(36)}-${fallbackRequestSequence.toString(36)}`
}

function extractAuthorization(headers: unknown): unknown {
  if (!headers || typeof headers !== 'object') return undefined
  const headerContainer = headers as {
    get?: (name: string) => unknown
    authorization?: unknown
    Authorization?: unknown
  }
  return headerContainer.get?.('authorization')
    ?? headerContainer.authorization
    ?? headerContainer.Authorization
}

const { VITE_API_URL, VITE_WITH_CREDENTIALS } = import.meta.env

/** Axios实例 */
const axiosInstance = axios.create({
  timeout: REQUEST_TIMEOUT,
  baseURL: VITE_API_URL,
  withCredentials: VITE_WITH_CREDENTIALS === 'true',
  validateStatus: (status) => status >= 200 && status < 300,
  transformResponse: [
    (data, headers) => {
      const contentType = headers['content-type']
      if (String(contentType || '').includes('application/json')) {
        try {
          return JSON.parse(data)
        } catch {
          return data
        }
      }
      return data
    }
  ]
})

/** 请求拦截器 */
axiosInstance.interceptors.request.use(
  (request: InternalAxiosRequestConfig) => {
    const { accessToken } = useUserStore()
    if (accessToken) request.headers.set('Authorization', accessToken.startsWith('Bearer ') ? accessToken : `Bearer ${accessToken}`)
    request.headers.set('X-Request-Id', createRequestId())

    if (request.data && !(request.data instanceof FormData) && !request.headers['Content-Type']) {
      request.headers.set('Content-Type', 'application/json')
      request.data = JSON.stringify(request.data)
    }

    return request
  },
  (error) => {
    showError(createHttpError($t('httpMsg.requestConfigError'), ApiStatus.error))
    return Promise.reject(error)
  }
)

/** 响应拦截器 */
axiosInstance.interceptors.response.use(
  (response: AxiosResponse<BaseResponse>) => {
    if (!response.data || typeof response.data !== 'object') {
      throw createHttpError('服务响应格式异常，请稍后重试', ApiStatus.badGateway, {
        url: response.config.url,
        method: response.config.method?.toUpperCase(),
        requestId: extractRequestId(response.headers) ?? extractRequestId(response.config.headers)
      })
    }
    const { code, msg, data } = response.data
    const requestId = extractRequestId(response.headers) ?? extractRequestId(response.config.headers)
    if (code === ApiStatus.success) return response
    const errorCode = Number.isInteger(code) ? code : ApiStatus.error
    if (errorCode === ApiStatus.unauthorized) {
      handleUnauthorizedError(
        msg,
        response.config.url,
        requestId,
        extractAuthorization(response.config.headers)
      )
    }
    throw createHttpError(msg, errorCode, {
      data,
      url: response.config.url,
      method: response.config.method?.toUpperCase(),
      requestId
    })
  },
  (error) => {
    if (error.response?.status === ApiStatus.unauthorized) {
      handleUnauthorizedError(
        error.response?.data?.msg,
        error.config?.url,
        extractRequestId(error.response?.headers) ?? extractRequestId(error.config?.headers),
        extractAuthorization(error.config?.headers)
      )
    }
    return handleError(error)
  }
)

/** 判断是否为登录接口请求（登录接口 401 只表示凭证校验失败） */
function isLoginRequest(url?: string): boolean {
  return !!url && url.includes('/auth/login')
}

/** 处理401错误（带防抖） */
function handleUnauthorizedError(
  message?: unknown,
  requestUrl?: string,
  requestId?: string,
  requestAuthorization?: unknown
): never {
  const error = createHttpError(message, ApiStatus.unauthorized, {
    url: requestUrl,
    requestId
  })

  // 登录接口 401 由登录页展示，不能登出任何已建立的会话。
  if (isLoginRequest(requestUrl)) {
    throw error
  }

  const userStore = useUserStore()
  if (!isAuthorizationForCurrentSession(requestAuthorization, userStore.accessToken)) {
    // 旧会话的延迟 401 不得清除用户刚登录获取的新令牌。
    throw error
  }

  if (!isUnauthorizedErrorShown) {
    isUnauthorizedErrorShown = true
    userStore.logOut()

    unauthorizedTimer = setTimeout(resetUnauthorizedError, UNAUTHORIZED_DEBOUNCE_TIME)

    showError(error, true)
    throw error
  }

  throw error
}

/** 重置401防抖状态 */
function resetUnauthorizedError() {
  isUnauthorizedErrorShown = false
  if (unauthorizedTimer) clearTimeout(unauthorizedTimer)
  unauthorizedTimer = null
}

/** 请求重试逻辑 */
async function retryRequest<T>(
  config: ExtendedAxiosRequestConfig,
  retries: number = MAX_RETRIES
): Promise<T> {
  try {
    return await request<T>(config)
  } catch (error) {
    if (
      retries > 0
      && error instanceof HttpError
      && shouldRetryHttpRequest(config.method, error.code)
    ) {
      await delay(RETRY_DELAY)
      return retryRequest<T>(config, retries - 1)
    }
    if (error instanceof HttpError && !error.cancelled && error.code !== ApiStatus.unauthorized) {
      showError(error, config.showErrorMessage !== false)
    }
    throw error
  }
}

/** 延迟函数 */
function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/** 请求函数（带缓存和去重） */
async function request<T = any>(config: ExtendedAxiosRequestConfig): Promise<T> {
  // POST | PUT 参数自动填充
  if (
    ['POST', 'PUT'].includes(config.method?.toUpperCase() || '') &&
    config.params &&
    !config.data
  ) {
    config.data = config.params
    config.params = undefined
  }

  const method = (config.method || 'GET').toUpperCase()
  const requestKey = buildRequestKey(config)

  // 1. 命中缓存直接返回（仅 GET）
  if (isCacheable(config)) {
    const cached = readCache<T>(requestKey)
    if (cached !== null) {
      return cached
    }
  }

  // 2. 并发去重（仅 GET，且未跳过）
  if (method === 'GET' && !config.skipDedupe) {
    const pending = pendingRequests.get(requestKey)
    if (pending) {
      return pending as Promise<T>
    }
  }

  // 3. 实际发起请求
  const promise = (async () => {
    try {
      const res = await axiosInstance.request<BaseResponse<T>>(config)

      // 显示成功消息
      if (config.showSuccessMessage && res.data.msg) {
        const successMessage = selectSafeServerMessage(res.data.msg, '')
        if (successMessage) showSuccess(successMessage)
      }

      const data = res.data.data as T

      // 写入缓存
      if (isCacheable(config)) {
        writeCache(requestKey, data, config.cacheTtl!)
      }

      return data
    } finally {
      // 请求完成（无论成功失败），从 pending 移除
      if (method === 'GET' && !config.skipDedupe) {
        pendingRequests.delete(requestKey)
      }
    }
  })()

  // GET 请求注册到 pending（用于去重）
  if (method === 'GET' && !config.skipDedupe) {
    pendingRequests.set(requestKey, promise)
    // 兜底清理：PENDING_REQUEST_MAX_TTL_MS 后强制从 pending 移除，防止网络挂死导致相同 key 的请求永久 await
    // 正常请求在 finally 块中已删除；这里只处理异常挂死场景
    const pendingCleanupTimer = setTimeout(() => {
      pendingRequests.delete(requestKey)
    }, PENDING_REQUEST_MAX_TTL_MS)
    // promise 完成后清除定时器，避免内存泄漏
    promise.finally(() => clearTimeout(pendingCleanupTimer))
  }

  return promise
}

/** API方法集合 */
const api = {
  get<T>(config: ExtendedAxiosRequestConfig) {
    return retryRequest<T>({ ...config, method: 'GET' })
  },
  post<T>(config: ExtendedAxiosRequestConfig) {
    return retryRequest<T>({ ...config, method: 'POST' })
  },
  put<T>(config: ExtendedAxiosRequestConfig) {
    return retryRequest<T>({ ...config, method: 'PUT' })
  },
  del<T>(config: ExtendedAxiosRequestConfig) {
    return retryRequest<T>({ ...config, method: 'DELETE' })
  },
  request<T>(config: ExtendedAxiosRequestConfig) {
    return retryRequest<T>(config)
  }
}

export default api
