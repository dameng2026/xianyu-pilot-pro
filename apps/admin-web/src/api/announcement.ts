import request from '@/utils/http'
import { buildFreshContentListRequest } from './content-config'
import { requireListPayload } from '@/utils/api-payload'

export interface AnnouncementItem {
  id?: number
  title: string
  content: string
  enabled: boolean
  createdAt?: string
  updatedAt?: string
}

/** 配置页保存后需要立刻看到最新结果，这里始终跳过缓存 */
export function getAnnouncementList() {
  return request.get<AnnouncementItem[]>(buildFreshContentListRequest('/admin/announcement/list'))
    .then(value => requireListPayload<AnnouncementItem>(value, '公告列表'))
}

export function saveAnnouncement(data: AnnouncementItem) {
  return request.post<AnnouncementItem>({ url: '/admin/announcement', data, showSuccessMessage: true })
}

export function updateAnnouncement(data: AnnouncementItem) {
  return request.put<AnnouncementItem>({ url: '/admin/announcement', data, showSuccessMessage: true })
}

export function deleteAnnouncement(id: number) {
  return request.del<void>({ url: `/admin/announcement/${id}`, showSuccessMessage: true })
}
