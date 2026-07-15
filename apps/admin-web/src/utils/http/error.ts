/**
 * HTTP 错误处理模块
 *
 * 提供统一的 HTTP 请求错误处理机制
 *
 * ## 主要功能
 *
 * - 自定义 HttpError 错误类，封装错误信息、状态码、时间戳等
 * - 错误拦截和转换，将 Axios 错误转换为标准的 HttpError
 * - 错误消息国际化处理，根据状态码返回对应的多语言错误提示
 * - 错误日志记录，便于问题追踪和调试
 * - 错误和成功消息的统一展示
 * - 类型守卫函数，用于判断错误类型
 *
 * ## 使用场景
 *
 * - HTTP 请求拦截器中统一处理错误
 * - 业务代码中捕获和处理特定错误
 * - 错误日志收集和上报
 *
 * @module utils/http/error
 * @author Art Design Pro Team
 */
import { AxiosError } from 'axios'
import { ApiStatus } from './status'
import { $t } from '@/locales'
import {
  formatHttpErrorDisplay,
  getHttpStatusMessageKey,
  normalizeRequestId,
  selectSafeServerMessage
} from './error-policy'

// 错误响应接口
export interface ErrorResponse {
  /** 错误状态码 */
  code?: number
  /** 错误消息 */
  msg?: unknown
  /** 错误附加数据 */
  data?: unknown
}

// 错误日志数据接口
export interface ErrorLogData {
  /** 错误状态码 */
  code: number
  /** 错误消息 */
  message: string
  /** 错误附加数据 */
  data?: unknown
  /** 错误发生时间戳 */
  timestamp: string
  /** 请求 URL */
  url?: string
  /** 请求方法 */
  method?: string
  /** 服务端关联请求 ID */
  requestId?: string
  /** 错误堆栈信息 */
  stack?: string
}

export interface SafeErrorLogData {
  code: number
  timestamp: string
  url?: string
  method?: string
  requestId?: string
}

function sanitizeLogUrl(value?: string): string | undefined {
  if (!value) return undefined
  try {
    const url = new URL(value, 'https://admin.invalid')
    return url.pathname.slice(0, 512)
  } catch {
    return value.split(/[?#]/, 1)[0]?.slice(0, 512)
  }
}

// 自定义 HttpError 类
export class HttpError extends Error {
  public readonly code: number
  public readonly data?: unknown
  public readonly timestamp: string
  public readonly url?: string
  public readonly method?: string
  public readonly requestId?: string
  public readonly cancelled: boolean

  constructor(
    message: string,
    code: number,
    options?: {
      cancelled?: boolean
      data?: unknown
      url?: string
      method?: string
      requestId?: string
    }
  ) {
    super(message)
    this.name = 'HttpError'
    this.code = code
    this.data = options?.data
    this.timestamp = new Date().toISOString()
    this.url = options?.url
    this.method = options?.method
    this.requestId = options?.requestId
    this.cancelled = options?.cancelled === true
  }

  public get displayMessage(): string {
    return formatHttpErrorDisplay(this.message, this.requestId)
  }

  public toLogData(): ErrorLogData {
    return {
      code: this.code,
      message: this.message,
      data: this.data,
      timestamp: this.timestamp,
      url: this.url,
      method: this.method,
      requestId: this.requestId,
      stack: this.stack
    }
  }

  public toSafeLogData(): SafeErrorLogData {
    return {
      code: this.code,
      timestamp: this.timestamp,
      url: sanitizeLogUrl(this.url),
      method: this.method,
      requestId: this.requestId
    }
  }
}

/**
 * 获取错误消息
 * @param status 错误状态码
 * @returns 错误消息
 */
const getErrorMessage = (status: number): string => {
  return $t(getHttpStatusMessageKey(status))
}

function readHeader(headers: unknown, name: string): unknown {
  if (!headers || typeof headers !== 'object') return undefined

  const headerContainer = headers as {
    get?: (headerName: string) => unknown
    [key: string]: unknown
  }
  return headerContainer.get?.(name)
    ?? headerContainer[name]
    ?? headerContainer[name.toLowerCase()]
    ?? headerContainer[name.toUpperCase()]
}

export function extractRequestId(headers: unknown): string | undefined {
  return normalizeRequestId(readHeader(headers, 'x-request-id'))
}

export function createHttpError(
  message: unknown,
  code: number,
  options?: {
    cancelled?: boolean
    data?: unknown
    url?: string
    method?: string
    requestId?: string
  }
): HttpError {
  return new HttpError(selectSafeServerMessage(message, getErrorMessage(code)), code, options)
}

/**
 * 处理错误
 * @param error 错误对象
 * @returns 错误对象
 */
export function handleError(error: AxiosError<ErrorResponse>): never {
  const requestConfig = error.config
  const requestId = extractRequestId(error.response?.headers) ?? extractRequestId(requestConfig?.headers)

  // 处理取消的请求
  if (error.code === 'ERR_CANCELED') {
    throw new HttpError($t('httpMsg.requestCancelled'), ApiStatus.error, {
      cancelled: true,
      url: requestConfig?.url,
      method: requestConfig?.method?.toUpperCase(),
      requestId
    })
  }

  const statusCode = error.response?.status

  // 处理网络错误
  if (!error.response) {
    throw new HttpError($t('httpMsg.networkError'), ApiStatus.error, {
      url: requestConfig?.url,
      method: requestConfig?.method?.toUpperCase(),
      requestId
    })
  }

  // 处理 HTTP 状态码错误
  const code = statusCode || ApiStatus.error
  throw createHttpError(error.response.data?.msg, code, {
    data: error.response.data,
    url: requestConfig?.url,
    method: requestConfig?.method?.toUpperCase(),
    requestId
  })
}

/**
 * 显示错误消息
 * @param error 错误对象
 * @param showMessage 是否显示错误消息
 */
export function showError(error: HttpError, showMessage: boolean = true): void {
  if (showMessage) {
    ElMessage.error(error.displayMessage)
  }
  // 记录错误日志
  console.error('[HTTP Error]', error.toSafeLogData())
}

/**
 * 显示成功消息
 * @param message 成功消息
 * @param showMessage 是否显示消息
 */
export function showSuccess(message: string, showMessage: boolean = true): void {
  if (showMessage) {
    ElMessage.success(message)
  }
}

/**
 * 判断是否为 HttpError 类型
 * @param error 错误对象
 * @returns 是否为 HttpError 类型
 */
export const isHttpError = (error: unknown): error is HttpError => {
  return error instanceof HttpError
}
