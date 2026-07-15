import request from '../utils/request.js'

export const listAiProviders = () => request.post('/aiProvider/list', {})
export const listAiProvidersByType = type => request.post('/aiProvider/listByType', { type })
export const saveAiProvider = data => request.post('/aiProvider/save', data)
export const deleteAiProvider = id => request.post('/aiProvider/delete', { id })
export const activateAiProvider = id => request.post('/aiProvider/activate', { id })
export const testAiProvider = data => request.post('/aiProvider/test', data)
export const getAiProviderModels = data => request.post('/aiProvider/models', data)
export const getAiProviderStatus = () => request.get('/ai-provider/status')
export const suggestCategoryByAi = data => request.post('/ai-provider/category-suggest', data)
