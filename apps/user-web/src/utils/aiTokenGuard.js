import { getTokenBalance } from '../api/quickReply.js'

/**
 * 通用模型调用前的 Token 余额校验。
 *
 * 通用模型统一按次计费（默认 0.03 元/次，兑换比例 100 时扣 3 Token）。
 * 单次调用场景：余额 < 单次扣费数（perCallTokens）时拦截并提示充值。
 *
 * 提示策略：
 * 1. 派发全局 xya-toast 事件 → App.vue 渲染顶部红色错误提示条
 * 2. 派发全局 xya-open-payment 事件 → App.vue 打开 Token 充值 modal，引导用户直接充值
 *
 * @param {Object} [opts]
 * @param {number} [opts.requiredTokens] 需要的 Token 数（默认单次扣费 perCallTokens，工作流批量场景传入总数）
 * @param {string} [opts.sceneName] 场景名称（如「内容润色」「工作流」），用于提示文案
 * @returns {Promise<boolean>} true 表示余额充足可以继续调用；false 表示余额不足已拦截
 */
export async function ensureAiTokenBalance(opts = {}) {
  const requiredTokens = Number(opts.requiredTokens) > 0 ? Number(opts.requiredTokens) : null
  const sceneName = opts.sceneName || ''
  try {
    const res = await getTokenBalance()
    const data = res?.data || {}
    const balance = Number(data.balance ?? data.tokenBalance ?? 0)
    const perCallTokens = Number(data.perCallTokens ?? 3)
    const perCallPrice = Number(data.perCallPrice ?? 0.03)
    const tokenExchangeRate = Number(data.tokenExchangeRate ?? 100)

    if (!Number.isFinite(balance) || balance <= 0) {
      notifyRecharge({
        sceneName,
        requiredTokens: requiredTokens ?? perCallTokens,
        balance: 0,
        perCallTokens,
        perCallPrice,
      })
      return false
    }

    // 单次调用 / 批量调用统一校验：余额是否 >= 需要的 Token 数
    const need = requiredTokens ?? perCallTokens
    if (balance < need) {
      notifyRecharge({
        sceneName,
        requiredTokens: need,
        balance,
        perCallTokens,
        perCallPrice,
      })
      return false
    }
    return true
  } catch (_e) {
    // 余额查询失败时不阻断前端调用，由后端 precheck（402）兜底拦截
    return true
  }
}

/**
 * 获取当前用户的 Token 余额与单次扣费信息。
 * 不抛异常，失败时返回默认值，调用方自行决定如何处理。
 */
export async function fetchTokenBalance() {
  try {
    const res = await getTokenBalance()
    const data = res?.data || {}
    return {
      ok: true,
      balance: Number(data.balance ?? data.tokenBalance ?? 0),
      perCallTokens: Number(data.perCallTokens ?? 3),
      perCallPrice: Number(data.perCallPrice ?? 0.03),
      tokenExchangeRate: Number(data.tokenExchangeRate ?? 100),
    }
  } catch (_e) {
    return {
      ok: false,
      balance: 0,
      perCallTokens: 3,
      perCallPrice: 0.03,
      tokenExchangeRate: 100,
    }
  }
}

function notifyRecharge({ sceneName, requiredTokens, balance, perCallTokens, perCallPrice }) {
  if (typeof window === 'undefined' || !window.dispatchEvent) return

  const sceneText = sceneName ? `「${sceneName}」` : '该功能'
  const message = balance <= 0
    ? `Token 余额为 0，无法使用${sceneText}。本次需要 ${requiredTokens} Token，请先充值`
    : `Token 余额不足，无法使用${sceneText}。本次需要 ${requiredTokens} Token，当前余额 ${balance} Token，请先充值`

  // 1. 顶部错误提示条（由 App.vue 的 xya-toast 监听器渲染为 global-notice error 样式）
  window.dispatchEvent(new CustomEvent('xya-toast', {
    detail: {
      message,
      isError: true
    }
  }))

  // 2. 自动弹出充值 modal，引导用户直接充值（由 App.vue 的 xya-open-payment 监听器打开 PaymentModal）
  window.dispatchEvent(new CustomEvent('xya-open-payment', {
    detail: {
      source: 'ai_token_guard',
      reason: balance <= 0 ? 'insufficient_balance' : 'low_balance',
      requiredTokens,
      balance,
      perCallTokens,
      perCallPrice,
    }
  }))

  // 3. 兼容使用 $message 的页面（如工作流页）——若该页面注入了 window.$message，则额外弹一条提示
  if (window.$message?.error) {
    window.$message.error(message)
  }
}
