import request from '../utils/request.js'

export const getSetting = settingKey => request.post('/sysSetting/get', { settingKey })
export const listSettings = () => request.post('/sysSetting/list', {})
export const saveSetting = data => request.post('/sysSetting/save', data)
export const deleteSetting = settingKey => request.post('/sysSetting/delete', { settingKey })
export const testEmail = () => request.post('/sysSetting/testEmail', {})
