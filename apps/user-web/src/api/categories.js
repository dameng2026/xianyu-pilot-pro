import request from '../utils/request.js'

/**
 * 获取完整分类树
 * 从后端 API 获取，确保包含通过自动分类新增的分类
 */
export const fetchCategories = () => request.get('/xianyu/categories')

/**
 * 手动同步分类候选到分类树
 * @param {Array} candidates - 自动分类返回的候选列表
 */
export const syncCategories = candidates => request.post('/xianyu/categories/sync', { candidates })