export function selectCurrentAnnouncement(items, dismissedIds = []) {
  const enabledAnnouncements = Array.isArray(items)
    ? items.filter(item => item?.enabled)
    : []

  return enabledAnnouncements.find(item => !dismissedIds.includes(item.id)) || null
}

export function getAnnouncementFirstLine(announcement) {
  if (!announcement?.content) return ''
  return String(announcement.content).split('\n')[0] || ''
}
