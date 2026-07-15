import request from '../utils/request.js'

export const getDataPanelStats = data => request.post('/data-panel/stats', data || {})
export const getDataPanelTrend = () => request.post('/data-panel/trend', {})
