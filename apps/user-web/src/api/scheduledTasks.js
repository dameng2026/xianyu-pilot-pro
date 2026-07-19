import request from '../utils/request.js'
import { pageParams } from '../utils/apiData.js'

export function getScheduledTasks(params = {}) {
  return request({ url: '/scheduled-tasks', method: 'get', params: pageParams(params) })
}
export function createScheduledTask(data) {
  return request({ url: '/scheduled-tasks', method: 'post', data })
}
export function updateScheduledTask(id, data) {
  return request({ url: `/scheduled-tasks/${id}`, method: 'put', data })
}
export function deleteScheduledTask(id) {
  return request({ url: `/scheduled-tasks/${id}`, method: 'delete' })
}
export function runScheduledTask(id) {
  return request({ url: `/scheduled-tasks/${id}/run`, method: 'post' })
}
export function setScheduledTaskEnabled(id, enabled) {
  return request({ url: `/scheduled-tasks/${id}/enabled`, method: 'patch', data: { enabled: enabled ? 1 : 0 } })
}
