// 发布商品页历史位置存取（localStorage，只保留最近一份）
// 用户每次选择完整地址后保存，下次进入页面若没有可恢复的草稿地址则提示是否复用
const LAST_ADDRESS_KEY = 'xianyu_publish_last_address_v1'

export function loadLastPublishAddress() {
  try {
    const raw = localStorage.getItem(LAST_ADDRESS_KEY)
    if (!raw) return null
    const data = JSON.parse(raw)
    if (!data || typeof data !== 'object' || Array.isArray(data)) return null
    return data
  } catch {
    return null
  }
}

export function saveLastPublishAddress(address) {
  try {
    if (!address || typeof address !== 'object') return
    const payload = { ...address, savedAt: Date.now() }
    localStorage.setItem(LAST_ADDRESS_KEY, JSON.stringify(payload))
  } catch {
    // 存储不可用或已满时静默失败，不影响编辑流程
  }
}

export function clearLastPublishAddress() {
  try {
    localStorage.removeItem(LAST_ADDRESS_KEY)
  } catch {
    // 静默
  }
}
