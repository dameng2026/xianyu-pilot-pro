import request from '../utils/request.js'

/**
 * 获取常用发布地址历史
 */
export const getPublishAddressHistory = () => request.get('/publish-address/history')

/**
 * 保存发布地址（记录常用地址）
 * @param {Object} data - { poiName, city, area, detail }
 */
export const savePublishAddress = data => request.post('/publish-address/save', data)