import request from '@/utils/http'
import { requireListPayload, requirePagePayload, requireRecordPayload } from '@/utils/api-payload'

/** 商品类型：文本商品 / 卡密商品 */
export type MallProductType = 'text' | 'card'

/** 商城商品 */
export interface MallProduct {
  id?: number
  /** 商品类型（前端表单字段，向后兼容） */
  type: MallProductType
  /** 商品类型（后端返回/接收字段，与 type 等价） */
  productType?: MallProductType
  title: string
  subtitle?: string
  content?: string
  /** 商品文案（供 AI 改写板块使用，非面向用户展示） */
  copy?: string
  deliveryContent?: string
  price: number
  coverUrl?: string
  category?: string
  categoryId?: number
  /** 卡密商品库存数量 */
  stock?: number
  enabled?: boolean
  createdAt?: string
  updatedAt?: string
}

/** 商品列表查询参数 */
export interface MallProductQuery {
  type?: MallProductType
  keyword?: string
  page?: number
  size?: number
}

/** 商品分页结果 */
export interface MallProductPage {
  records: MallProduct[]
  total: number
  current?: number
  size?: number
}

/** 卡密条目 */
export interface CardKeyItem {
  id: number
  productId: number
  content: string
  status?: string
  usedAt?: string
  createdAt?: string
}

/** 卡密分页结果 */
export interface CardKeyPage {
  records: CardKeyItem[]
  total: number
  current?: number
  size?: number
}

/** 商城分类 */
export interface MallCategory {
  id: number
  name: string
}

/** 闲鱼分类树节点（与前台发布商品页面一致，支持 label/title 两种字段名） */
export interface MallCategoryNode {
  id: string | number
  label?: string
  title?: string
  children?: MallCategoryNode[]
}

/** 闲鱼分类树（automation-service /api/xianyu/categories 返回结构） */
export interface MallCategoryTree {
  cation?: MallCategoryNode[]
  categories?: MallCategoryNode[]
}

/** 商城 FAQ */
export interface MallFaq {
  id?: number
  question: string
  answer: string
  sortOrder: number
  enabled: boolean
  createdAt?: string
  updatedAt?: string
}

/** 商品列表（分页 + 筛选） */
export function getMallProducts(params: MallProductQuery) {
  return request.get<MallProductPage>({ url: '/mall/products', params, skipDedupe: true })
    .then(value => requirePagePayload<MallProduct>(value, '商城商品列表') as MallProductPage)
}

/** 商品详情 */
export function getMallProduct(id: number) {
  return request.get<MallProduct>({ url: `/mall/products/${id}`, skipDedupe: true })
    .then(value => requireRecordPayload<Record<string, any>>(value, '商城商品详情') as MallProduct)
}

/** 新增商品 */
export function createMallProduct(data: Partial<MallProduct>) {
  return request.post<MallProduct>({ url: '/mall/products', data, showSuccessMessage: true })
    .then(value => requireRecordPayload<Record<string, any>>(value, '商城商品新增') as MallProduct)
}

/** 更新商品 */
export function updateMallProduct(id: number, data: Partial<MallProduct>) {
  return request.put<MallProduct>({ url: `/mall/products/${id}`, data, showSuccessMessage: true })
    .then(value => requireRecordPayload<Record<string, any>>(value, '商城商品更新') as MallProduct)
}

/** 删除商品 */
export function deleteMallProduct(id: number) {
  return request.del<void>({ url: `/mall/products/${id}`, showSuccessMessage: true })
}

/** 批量导入卡密（每行一条） */
export function importCardKeys(productId: number, cards: string) {
  return request.post<{ count: number }>({
    url: `/mall/products/${productId}/card-keys`,
    data: { cards },
    showSuccessMessage: true
  })
}

/** 卡密列表（分页） */
export function getCardKeys(productId: number, params: { page?: number; size?: number }) {
  return request.get<CardKeyPage>({ url: `/mall/products/${productId}/card-keys`, params, skipDedupe: true })
    .then(value => requirePagePayload<CardKeyItem>(value, '卡密列表') as CardKeyPage)
}

/** 刷新商品分类缓存 */
export function refreshCategories() {
  return request.post<{ count?: number }>({ url: '/mall/categories/refresh', showSuccessMessage: true })
}

/**
 * 获取闲鱼商品分类树（与前台发布商品页面使用同一分类源）。
 * 用于后台货源商城新增商品弹窗中手动选择分类。
 */
export function getMallCategoryTree() {
  return request.get<MallCategoryTree>({ url: '/mall/category-tree', skipDedupe: true })
    .then(value => requireRecordPayload<Record<string, any>>(value, '商品分类树') as MallCategoryTree)
}

/** 上传商品封面图（文件上传） */
export function uploadMallImage(file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return request.post<{ url: string }>({
    url: '/admin/carousel/upload',
    data: formData
  }).then(value => requireRecordPayload<{ url: string }>(value, '商品封面图上传'))
}

/** 通过URL导入商品封面图（下载保存到本地，避免外链失效） */
export function uploadMallImageFromUrl(url: string) {
  return request.post<{ url: string }>({
    url: '/admin/carousel/upload-from-url',
    data: { url }
  }).then(value => requireRecordPayload<{ url: string }>(value, '商品封面图导入'))
}

/** FAQ 列表 */
export function getMallFaqs() {
  return request.get<MallFaq[]>({ url: '/mall/faqs', skipDedupe: true })
    .then(value => requireListPayload<MallFaq>(value, '商城FAQ列表'))
}

/** 新增 FAQ */
export function createMallFaq(data: Partial<MallFaq>) {
  return request.post<MallFaq>({ url: '/mall/faqs', data, showSuccessMessage: true })
}

/** 更新 FAQ */
export function updateMallFaq(id: number, data: Partial<MallFaq>) {
  return request.put<MallFaq>({ url: `/mall/faqs/${id}`, data, showSuccessMessage: true })
}

/** 删除 FAQ */
export function deleteMallFaq(id: number) {
  return request.del<void>({ url: `/mall/faqs/${id}`, showSuccessMessage: true })
}
