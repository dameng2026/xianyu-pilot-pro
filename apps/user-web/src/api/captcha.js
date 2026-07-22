import request from '../utils/request.js'

// 入队后立即返回排队信息（不再等待求解完成），30 秒超时足够
const HANDLE_TIMEOUT = 30000

export const detectCaptcha = data => request.post('/captcha/detect', data)
export const getCaptchaInstructions = data => request.post('/captcha/instructions', data)
export const autoSolveCaptcha = data => request.post('/captcha/auto-solve', data, { timeout: HANDLE_TIMEOUT })
export const handleCaptcha = data => request.post('/captcha/handle', data, { timeout: HANDLE_TIMEOUT })
export const getCaptchaRecords = (params = {}) => request.get('/captcha/records', { params })

/**
 * 查询滑块求解任务的排队位置（前端轮询用）。
 * @param {Object} params - { recordId?: number, accountId?: number }
 */
export const getCaptchaQueuePosition = (params = {}) => request.get('/captcha/queue-position', { params })

/**
 * 获取"用户不在场时"滑块自动求解成功摘要（仅好消息）。
 * 仅统计自动触发场景（ws_connect/cookie_keepalive/token_refresh）且成功的次数，
 * 不返回失败/总数。用于首页惊喜提示弹窗。
 * @param {Object} params - { since: ISO时间字符串，上次访问时间 }
 */
export const getCaptchaSilentSummary = (params = {}) => request.get('/captcha/silent-summary', { params })
