import { clearAuth, getToken } from '../utils/auth.js'

// AI 接口默认超时时间（非流式接口）
const AI_TIMEOUT_MS = 60000

function aiFetch(path, data, signal) {
  return fetch(`/ai${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${getToken()}`
    },
    body: JSON.stringify(data || {}),
    signal
  })
}

/**
 * 统一处理 401 响应：清除 token 并派发登录过期事件
 */
function handleAuthError() {
  clearAuth()
  window.dispatchEvent(new CustomEvent('xya-auth-expired', { detail: { message: '登录已过期，请重新登录' } }))
}

/**
 * 非流式接口辅助函数：
 * - 增加超时控制（AbortController）
 * - 校验 response.ok
 * - 401 时触发登出
 * - 解析 JSON 响应
 */
async function aiFetchJson(path, data) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), AI_TIMEOUT_MS)
  try {
    const res = await aiFetch(path, data, controller.signal)
    if (res.status === 401) {
      handleAuthError()
      throw new Error('登录已过期，请重新登录')
    }
    if (!res.ok) {
      // 尝试解析错误响应体
      let errMsg = `请求失败（HTTP ${res.status}）`
      try {
        const body = await res.json()
        errMsg = body?.msg || body?.message || errMsg
      } catch { /* 响应体非 JSON，使用默认错误信息 */ }
      throw new Error(errMsg)
    }
    return await res.json()
  } catch (e) {
    if (e?.name === 'AbortError') {
      throw new Error('AI 请求超时，请稍后重试', { cause: e })
    }
    throw e
  } finally {
    clearTimeout(timer)
  }
}

export const chatStream = (data, signal) => aiFetch('/chat', data, signal)
export const chatTestStream = (data, signal) => aiFetch('/chatTest', data, signal)
export const chatOnce = data => aiFetchJson('/chatOnce', data)
export const aiStatus = data => aiFetchJson('/status', data)
export const aiModels = data => aiFetchJson('/models', data)
export const aiTest = data => aiFetchJson('/test', data)
export const putNewData = data => aiFetchJson('/putNewData', data)
export const queryRagData = data => aiFetchJson('/queryRAGData', data)
export const deleteRagData = data => aiFetchJson('/deleteRAGData', data)
export const saveFixedMaterial = data => aiFetchJson('/saveFixedMaterial', data)
export const getFixedMaterial = data => aiFetchJson('/getFixedMaterial', data)
export const syncDetailToFixedMaterial = data => aiFetchJson('/syncDetailToFixedMaterial', data)
