import request from '../utils/request.js'

export function getNotificationSettings() { return request.get('/notification-settings') }
export function saveNotificationSettings(data) { return request.post('/notification-settings', data) }
export function getNotifications(params = {}) { return request.get('/notifications', { params }) }
export function markNotificationRead(id) { return request.post(`/notifications/${id}/read`, {}) }
export function testNotification(data = {}) { return request.post('/notifications/test', data) }
export function getNotificationDeliveryLogs(params = {}) { return request.get('/notifications/delivery-logs', { params }) }

/**
 * 查询平台邮件发送能力（设计文档 §9）。
 * 返回 { tencentSesAvailable, smtpEnabled, provider }，不暴露任何凭据。
 */
export function getEmailCapabilities() { return request.get('/notification-settings/email-capabilities') }
