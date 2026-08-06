import request from '@/utils/http'
import { buildFreshContentListRequest } from './content-config'
import type { CarouselItem } from './carousel'
import { requireListPayload, requireRecordPayload } from '@/utils/api-payload'

export type OpenSourceHomeCarouselItem = CarouselItem

export interface OpenSourceAnnouncementItem {
  id?: number
  title: string
  content: string
  enabled: boolean
  createdAt?: string
  updatedAt?: string
}

export interface OpenSourceAboutLogSection {
  t?: string
  d?: string
}

export interface OpenSourceAboutLogItem {
  v?: string
  t?: string
  tone?: string
  d?: string
  sections?: OpenSourceAboutLogSection[]
  tags?: string[]
}

export interface OpenSourceAboutSupportItem {
  label?: string
  desc?: string
  icon?: string
  tone?: string
  actionType?: string
  actionValue?: string
  actionMessage?: string
}

export interface OpenSourceAboutCommunityCard {
  label?: string
  title?: string
  desc?: string
  imageUrl?: string
  imageAlt?: string
  placeholderText?: string
  value?: string
  hint?: string
  tone?: string
  actionType?: string
  actionText?: string
  actionValue?: string
  actionMessage?: string
}

export interface OpenSourceAboutLinkItem {
  label?: string
  icon?: string
  actionText?: string
  actionType?: string
  actionValue?: string
  actionMessage?: string
}

export interface OpenSourceAboutContent {
  configurationWarning?: string
  heroTitle: string
  heroBadgeText: string
  heroDescription: string
  serviceStatusText: string
  logs: OpenSourceAboutLogItem[]
  supports: OpenSourceAboutSupportItem[]
  communityCards: OpenSourceAboutCommunityCard[]
  links: OpenSourceAboutLinkItem[]
  legalDocs: {
    termsUrl?: string
    privacyUrl?: string
    supportEmail?: string
  }
}

export function getOpenSourceHomeCarouselList() {
  return request.get<OpenSourceHomeCarouselItem[]>(
    buildFreshContentListRequest('/open-source-admin/home/carousels')
  ).then(value => requireListPayload<OpenSourceHomeCarouselItem>(value, '开源版轮播配置'))
}

export function saveOpenSourceHomeCarousel(data: OpenSourceHomeCarouselItem) {
  return request.post<OpenSourceHomeCarouselItem>({
    url: '/open-source-admin/home/carousels',
    data,
    showSuccessMessage: true
  }).then(value => requireRecordPayload<Record<string, any>>(value, '开源版轮播保存') as OpenSourceHomeCarouselItem)
}

export function updateOpenSourceHomeCarousel(data: OpenSourceHomeCarouselItem) {
  return request.put<OpenSourceHomeCarouselItem>({
    url: '/open-source-admin/home/carousels',
    data,
    showSuccessMessage: true
  }).then(value => requireRecordPayload<Record<string, any>>(value, '开源版轮播更新') as OpenSourceHomeCarouselItem)
}

export function deleteOpenSourceHomeCarousel(id: number) {
  return request.del<void>({
    url: `/open-source-admin/home/carousels/${id}`,
    showSuccessMessage: true
  })
}

export function getOpenSourceAnnouncementList() {
  return request.get<OpenSourceAnnouncementItem[]>(
    buildFreshContentListRequest('/open-source-admin/home/announcements')
  ).then(value => requireListPayload<OpenSourceAnnouncementItem>(value, '开源版公告'))
}

export function saveOpenSourceAnnouncement(data: OpenSourceAnnouncementItem) {
  return request.post<OpenSourceAnnouncementItem>({
    url: '/open-source-admin/home/announcements',
    data,
    showSuccessMessage: true
  })
}

export function updateOpenSourceAnnouncement(data: OpenSourceAnnouncementItem) {
  return request.put<OpenSourceAnnouncementItem>({
    url: '/open-source-admin/home/announcements',
    data,
    showSuccessMessage: true
  })
}

export function deleteOpenSourceAnnouncement(id: number) {
  return request.del<void>({
    url: `/open-source-admin/home/announcements/${id}`,
    showSuccessMessage: true
  })
}

export function getOpenSourceAboutContent() {
  return request.get<OpenSourceAboutContent>({
    url: '/open-source-admin/about',
    cacheTtl: 0,
    skipDedupe: true
  }).then(value => requireRecordPayload<Record<string, any>>(value, '开源版关于页') as OpenSourceAboutContent)
}

export function saveOpenSourceAboutContent(data: OpenSourceAboutContent) {
  return request.post<OpenSourceAboutContent>({
    url: '/open-source-admin/about',
    data,
    showSuccessMessage: true
  }).then(value => requireRecordPayload<Record<string, any>>(value, '开源版关于页保存') as OpenSourceAboutContent)
}

export function uploadOpenSourceContentImage(file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return request.post<{ url: string }>({
    url: '/open-source-admin/media/upload',
    data: formData
  }).then(value => requireRecordPayload<{ url: string }>(value, '开源站内容图片上传'))
}

export function importOpenSourceContentImageFromUrl(url: string) {
  return request.post<{ url: string }>({
    url: '/open-source-admin/media/import-from-url',
    data: { url }
  }).then(value => requireRecordPayload<{ url: string }>(value, '开源站内容图片导入'))
}
