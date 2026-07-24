import request from '../utils/request'

/**
 * 查询维护模式状态。
 * 后端返回 { code, msg, data: { enabled, message, until } }。
 * 失败降级为未维护，避免后端故障锁死前台。
 * @returns {Promise<{enabled: boolean, message: string|null, until: string|null}>}
 */
export async function getMaintenanceStatus() {
  try {
    const res = await request.get('/maintenance/status')
    const data = res?.data
    if (data && typeof data === 'object') {
      return {
        enabled: data.enabled === true,
        message: data.message || null,
        until: data.until || null
      }
    }
    return { enabled: false, message: null, until: null }
  } catch {
    // 后端不可达（部署重启期间）：降级为不显示，不阻塞用户
    return { enabled: false, message: null, until: null }
  }
}
