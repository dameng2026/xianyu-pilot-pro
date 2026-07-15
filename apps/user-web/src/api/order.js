import request from '../utils/request.js'

export const listOrders = data => request.post('/order/list', data)
export const confirmShipment = data => request.post('/order/confirmShipment', data)
export const batchRefreshOrders = data => request.post('/order/batchRefresh', data, { timeout: 300000 })
export const syncSoldOrders = data => request.post('/order/syncSoldOrders', data, { timeout: 300000 })
