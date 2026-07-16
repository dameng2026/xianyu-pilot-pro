import request from '../utils/request.js'

/**
 * 读取数据同步配置。
 * @returns {Promise} 配置对象（targetBaseUrl, targetUsername, targetToken, ...）
 */
export function getDataSyncConfig() {
  return request.get('/data-sync/config')
}

/**
 * 保存数据同步配置。
 * @param {Object} config 配置对象
 */
export function saveDataSyncConfig(config) {
  return request.post('/data-sync/config', config)
}

/**
 * 测试与线上接收端的连通性（不传输数据）。
 * @param {Object} [config] 可选配置覆盖（targetBaseUrl, targetToken）
 */
export function pingDataSyncRemote(config) {
  return request.post('/data-sync/ping', config || {})
}

/**
 * 执行同步推送（本地 → 线上）。
 * @param {Object} [config] 可选配置覆盖
 */
export function executeDataSync(config) {
  return request.post('/data-sync/execute', config || {}, { timeout: 180000 })
}
