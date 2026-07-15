import request from '@/utils/http'
import { buildFreshContentListRequest } from './content-config'
import { requireListPayload, requireRecordPayload } from '@/utils/api-payload'

export interface CarouselItem {
  id?: number
  title?: string
  description?: string
  imageUrl: string
  linkUrl: string
  sourceType?: 'upload' | 'url'
  coverItems?: CarouselCoverItem[]
  sortOrder: number
  enabled: boolean
  createdAt?: string
  updatedAt?: string
}

export interface CarouselCoverItem {
  id?: string
  title?: string
  description?: string
  imageUrl: string
  linkUrl: string
  sourceType?: 'upload' | 'url'
  sortOrder?: number
  enabled?: boolean
}

/** 配置页保存后需要立刻看到最新结果，这里始终跳过缓存 */
export function getCarouselList() {
  return request.get<CarouselItem[]>(buildFreshContentListRequest('/admin/carousel/list'))
    .then(value => requireListPayload<CarouselItem>(value, '轮播配置'))
}

export function saveCarousel(data: CarouselItem) {
  return request.post<CarouselItem>({ url: '/admin/carousel', data, showSuccessMessage: true })
    .then(value => requireRecordPayload<Record<string, any>>(value, '轮播配置保存') as CarouselItem)
}

export function updateCarousel(data: CarouselItem) {
  return request.put<CarouselItem>({ url: '/admin/carousel', data, showSuccessMessage: true })
    .then(value => requireRecordPayload<Record<string, any>>(value, '轮播配置更新') as CarouselItem)
}

export function deleteCarousel(id: number) {
  return request.del<void>({ url: `/admin/carousel/${id}`, showSuccessMessage: true })
}

export function uploadCarouselImage(file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return request.post<{ url: string }>({
    url: '/admin/carousel/upload',
    data: formData,
    headers: { 'Content-Type': 'multipart/form-data' }
  }).then(value => requireRecordPayload<{ url: string }>(value, '图片上传'))
}

export function uploadCarouselImageFromUrl(url: string) {
  return request.post<{ url: string }>({
    url: '/admin/carousel/upload-from-url',
    data: { url }
  }).then(value => requireRecordPayload<{ url: string }>(value, '图片导入'))
}
