import type { CarouselCoverItem, CarouselItem } from '../../../api/carousel'

export interface UnifiedCarouselConfig extends CarouselItem {
  coverItems: CarouselCoverItem[]
  legacyItemCount: number
  legacyItemIds: number[]
}

export function createEmptyCarouselCover(order = 0): CarouselCoverItem {
  return {
    id: `cover-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`,
    title: '',
    description: '',
    imageUrl: '',
    linkUrl: '',
    sourceType: 'upload',
    sortOrder: order,
    enabled: true
  }
}

export function normalizeCoverItems(row?: Partial<CarouselItem>): CarouselCoverItem[] {
  const source = Array.isArray(row?.coverItems) && row?.coverItems?.length
    ? row.coverItems
    : [{
        imageUrl: row?.imageUrl || '',
        linkUrl: row?.linkUrl || '',
        title: row?.title || '',
        description: row?.description || '',
        sourceType: row?.sourceType || 'upload',
        sortOrder: 0,
        enabled: row?.enabled ?? true
      }]

  const normalized = source
    .map((item, index) => ({
      ...createEmptyCarouselCover(index),
      ...item,
      id: item.id || `cover-${Date.now().toString(36)}-${index}`,
      sourceType: item.sourceType || 'upload',
      sortOrder: item.sortOrder ?? index,
      enabled: item.enabled ?? true
    }))
    .filter(item => item.imageUrl || item.title || item.description || item.linkUrl)

  return normalized.length ? normalized : [createEmptyCarouselCover(0)]
}

export function buildUnifiedCarouselConfig(items: CarouselItem[]): UnifiedCarouselConfig {
  const sortedItems = [...items].sort((a, b) => (a.sortOrder ?? 0) - (b.sortOrder ?? 0))
  const primaryItem = sortedItems[0]

  const mergedCoverItems = sortedItems
    .flatMap((item, itemIndex) => {
      const sortedCovers = normalizeCoverItems(item)
        .slice()
        .sort((a, b) => (a.sortOrder ?? 0) - (b.sortOrder ?? 0))

      return sortedCovers.map((cover, coverIndex) => ({
        ...cover,
        enabled: cover.enabled ?? item.enabled ?? true,
        sortOrder: itemIndex * 1000 + coverIndex
      }))
    })
    .sort((a, b) => (a.sortOrder ?? 0) - (b.sortOrder ?? 0))
    .map((cover, index) => ({
      ...cover,
      sortOrder: index
    }))

  if (!primaryItem) {
    return {
      id: undefined,
      title: '首页轮播',
      description: '用于前台首页顶部轮播展示',
      imageUrl: '',
      linkUrl: '',
      sourceType: 'upload',
      coverItems: [createEmptyCarouselCover(0)],
      sortOrder: 0,
      enabled: true,
      legacyItemCount: 0,
      legacyItemIds: []
    }
  }

  return {
    id: primaryItem.id,
    title: primaryItem.title || '首页轮播',
    description: primaryItem.description || '用于前台首页顶部轮播展示',
    imageUrl: primaryItem.imageUrl || '',
    linkUrl: primaryItem.linkUrl || '',
    sourceType: primaryItem.sourceType || 'upload',
    coverItems: mergedCoverItems.length ? mergedCoverItems : [createEmptyCarouselCover(0)],
    sortOrder: primaryItem.sortOrder ?? 0,
    enabled: primaryItem.enabled ?? true,
    createdAt: primaryItem.createdAt,
    updatedAt: primaryItem.updatedAt,
    legacyItemCount: sortedItems.length,
    legacyItemIds: sortedItems.map(item => item.id).filter((id): id is number => typeof id === 'number')
  }
}

export function buildCarouselSavePlan(form: UnifiedCarouselConfig) {
  const coverItems = (form.coverItems || [])
    .map((item, index) => ({
      ...item,
      title: item.title?.trim?.() || '',
      description: item.description?.trim?.() || '',
      imageUrl: item.imageUrl?.trim?.() || '',
      linkUrl: item.linkUrl?.trim?.() || '',
      sourceType: item.sourceType || 'upload',
      sortOrder: index,
      enabled: item.enabled ?? true
    }))
    .filter(item => item.imageUrl)

  const primaryCover = coverItems[0] || createEmptyCarouselCover(0)

  return {
    payload: {
      ...(form.id ? { id: form.id } : {}),
      title: form.title?.trim?.() || '',
      description: form.description?.trim?.() || '',
      imageUrl: primaryCover.imageUrl,
      linkUrl: primaryCover.linkUrl,
      sourceType: primaryCover.sourceType || 'upload',
      coverItems,
      sortOrder: form.sortOrder ?? 0,
      enabled: form.enabled ?? true
    } satisfies CarouselItem,
    deleteIds: (form.legacyItemIds || []).filter(id => id !== form.id)
  }
}
