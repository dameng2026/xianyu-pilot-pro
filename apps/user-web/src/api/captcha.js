import request from '../utils/request.js'

// 滑块求解涉及 Playwright 浏览器操作 + 多场景重试（加载转圈/点击重试/下载失败刷新），需 180 秒超时
const SOLVE_TIMEOUT = 180000

export const detectCaptcha = data => request.post('/captcha/detect', data)
export const getCaptchaInstructions = data => request.post('/captcha/instructions', data)
export const autoSolveCaptcha = data => request.post('/captcha/auto-solve', data, { timeout: SOLVE_TIMEOUT })
export const handleCaptcha = data => request.post('/captcha/handle', data, { timeout: SOLVE_TIMEOUT })
export const getCaptchaRecords = (params = {}) => request.get('/captcha/records', { params })

/**
 * 获取"用户不在场时"滑块自动求解成功摘要（仅好消息）。
 * 仅统计自动触发场景（ws_connect/cookie_keepalive/token_refresh）且成功的次数，
 * 不返回失败/总数。用于首页惊喜提示弹窗。
 * @param {Object} params - { since: ISO时间字符串，上次访问时间 }
 */
export const getCaptchaSilentSummary = (params = {}) => request.get('/captcha/silent-summary', { params })
