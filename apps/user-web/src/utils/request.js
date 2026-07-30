import axios from 'axios'
import { clearAuth, getToken } from './auth.js'
import { httpErrorMessage } from './httpErrorMessage.js'
import { isInBrowseMode, notifyLevelBlocked, isInPreviewMode, notifyPreviewBlocked } from '../composables/featureGuard.js'

// 写操作 HTTP 方法集合：浏览模式（等级不足）下拦截这些方法，只允许 GET 查询
const WRITE_METHODS = new Set(['post', 'put', 'delete', 'patch'])

function emit(name, detail) {
  window.dispatchEvent(new CustomEvent(name, { detail }))
}

let fallbackRequestSequence = 0

function createRequestId() {
  const cryptoApi = globalThis.crypto
  if (typeof cryptoApi?.randomUUID === 'function') {
    return `web-${cryptoApi.randomUUID()}`
  }
  if (typeof cryptoApi?.getRandomValues === 'function') {
    const values = new Uint32Array(2)
    cryptoApi.getRandomValues(values)
    return `web-${values[0].toString(16).padStart(8, '0')}${values[1].toString(16).padStart(8, '0')}`
  }
  fallbackRequestSequence = (fallbackRequestSequence + 1) % Number.MAX_SAFE_INTEGER
  return `web-${Date.now().toString(36)}-${fallbackRequestSequence.toString(36)}`
}

function messageWithRequestId(message, requestId) {
  return requestId ? `${message}（错误编号：${requestId}）` : message
}

function createStructuredError(message, requestId, extra = {}) {
  return {
    ...extra,
    message: messageWithRequestId(message, requestId),
    requestId,
  }
}

const request = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' }
})

request.interceptors.request.use(config => {
  const token = getToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  if (!config.headers['X-Request-Id']) config.headers['X-Request-Id'] = createRequestId()

  if (config.data instanceof FormData) {
    delete config.headers['Content-Type']
  }

  // 限制模式拦截写操作：浏览模式（等级不足）或预览模式（管理员限制）下，
  // 用户可查看页面内容，但不能发送写业务请求。弹窗关闭后再 reject，避免弹窗与页面内错误提示同时出现
  const method = (config.method || 'get').toLowerCase()
  if (WRITE_METHODS.has(method)) {
    if (isInBrowseMode()) {
      return notifyLevelBlocked().then(() => Promise.reject({
        featureBlocked: true,
        message: '等级不足，无法使用此功能',
        code: 'FEATURE_BLOCKED'
      }))
    }
    if (isInPreviewMode()) {
      return notifyPreviewBlocked().then(() => Promise.reject({
        featureBlocked: true,
        message: '预览模式，无法执行业务操作',
        code: 'FEATURE_PREVIEW_BLOCKED'
      }))
    }
  }

  return config
})

request.interceptors.response.use(
  response => {
    const res = response.data
    const url = response.config?.url || ''
    const requestId = response.headers?.['x-request-id'] || response.config?.headers?.['X-Request-Id'] || res?.data?.requestId || res?.requestId

    if (!res || typeof res !== 'object' || !Object.prototype.hasOwnProperty.call(res, 'code')) {
      return res
    }

    if (res.code === 401) {
      clearAuth()
      emit('xya-auth-expired', { url, message: res.msg || '登录已过期，请重新登录' })
      return Promise.reject(createStructuredError(res.msg || '登录已过期，请重新登录', requestId, {
        code: 401,
        data: res.data,
        raw: res,
      }))
    }

    if (res.code === 1001) {
      emit('xya-captcha-required', res.data)
      // 自动触发滑块求解（带冷却去重，不影响原 reject）
      // 受 auto-slider-solve 功能开关控制：关闭时不触发自动求解
      try {
        const captchaData = res.data || {}
        const accountId = captchaData.accountId || captchaData.account_id
        if (accountId) {
          import('../api/feature-switch.js').then(({ getFeatureStatus }) => {
            return getFeatureStatus('auto-slider-solve')
          }).then(status => {
            if (!status?.allowed) {
              // 自动求解被开关拦截，静默跳过（不弹窗，不打扰用户）
              return
            }
            import('../composables/useCaptchaSolver.js').then(({ useCaptchaSolver }) => {
              useCaptchaSolver().autoSolveIfNeeded(accountId)
            })
          }).catch(() => { /* 查询失败不影响错误传递 */ })
        }
      } catch { /* 自动求解失败不影响错误传递 */ }
      return Promise.reject(createStructuredError(res.msg || '需要滑块验证', requestId, {
        type: 'captcha',
        data: res.data,
        raw: res,
      }))
    }

    if (res.code !== 200 && res.code !== 0) {
      console.warn('[REQ] business request rejected', { code: res.code, requestId })
      return Promise.reject(createStructuredError(res.msg || '请求失败', requestId, {
        code: res.code,
        data: res.data,
        raw: res,
      }))
    }

    const nested = res.data
    if (nested && typeof nested === 'object' && Object.prototype.hasOwnProperty.call(nested, 'code')) {
      const nestedCode = Number(nested.code)
      if (nestedCode !== 200 && nestedCode !== 0) {
        return Promise.reject(createStructuredError(nested.msg || nested.message || res.msg || '请求失败', requestId, {
          code: nestedCode,
          data: nested.data,
          raw: nested,
        }))
      }
    }

    return res
  },
  error => {
    const status = error?.response?.status
    const requestId = error?.response?.headers?.['x-request-id'] || error?.config?.headers?.['X-Request-Id'] || error?.response?.data?.requestId
    let responseBody = error?.response?.data

    // Blob 响应需要异步解析为文本后尝试 JSON.parse，以提取后端返回的中文错误信息
    const isBlobResponse = responseBody instanceof Blob
    const parseBlobError = async () => {
      if (!isBlobResponse) return null
      try {
        const text = await responseBody.text()
        return JSON.parse(text)
      } catch {
        return null
      }
    }

    // 超时错误使用中文提示
    if (error?.code === 'ECONNABORTED' || /timeout/i.test(error?.message || '')) {
      return Promise.reject(createStructuredError('请求超时，请稍后重试', requestId, {
        code: 'TIMEOUT',
        status,
        timeout: true,
      }))
    }

    // 网络错误（服务不可达）
    if (error?.code === 'ERR_NETWORK' || (!status && /network/i.test(error?.message || ''))) {
      return Promise.reject(createStructuredError('网络连接失败，请检查网络或服务状态', requestId, {
        code: 'NETWORK_ERROR',
        status,
      }))
    }

    return parseBlobError().then(parsedBody => {
      const body = parsedBody || responseBody
      const publicMessage = httpErrorMessage(status, body)

      if (status === 401) {
        const authError = createStructuredError(publicMessage, requestId, {
          code: 401,
          data: body?.data,
          raw: body,
          status,
        })
        clearAuth()
        emit('xya-auth-expired', { message: authError.message })
        return Promise.reject(authError)
      }

      if (status === 403) {
        return Promise.reject(createStructuredError(publicMessage, requestId, {
          code: 403,
          data: body?.data,
          raw: body,
          status,
          forbidden: true,
        }))
      }

      if (status >= 500) {
        return Promise.reject(createStructuredError(publicMessage, requestId, {
          code: status,
          data: body?.data,
          raw: body,
          status,
          serverError: true,
        }))
      }

      return Promise.reject(createStructuredError(publicMessage, requestId, {
        code: body?.code || status,
        data: body?.data,
        raw: body,
        status,
      }))
    })
  }
)

export default request
