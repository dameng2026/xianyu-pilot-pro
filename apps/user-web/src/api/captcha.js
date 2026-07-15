import request from '../utils/request.js'

export const detectCaptcha = data => request.post('/captcha/detect', data)
export const getCaptchaInstructions = data => request.post('/captcha/instructions', data)
export const autoSolveCaptcha = data => request.post('/captcha/auto-solve', data)
export const handleCaptcha = data => request.post('/captcha/handle', data)
export const getCaptchaRecords = (params = {}) => request.get('/captcha/records', { params })
