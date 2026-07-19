import request from '../utils/request.js'

export const getProfileOverview = () => request.get('/profile/overview')
export const sendProfileCode = data => request.post('/profile/send-code', data)
export const changeProfilePassword = data => request.post('/profile/change-password', data)
export const changeProfilePhone = data => request.post('/profile/change-phone', data)
export const changeProfileEmail = data => request.post('/profile/change-email', data)
export const getTokenLedger = params => request.get('/profile/token-ledger', { params })
export const getTokenTrend = params => request.get('/profile/token-trend', { params })
