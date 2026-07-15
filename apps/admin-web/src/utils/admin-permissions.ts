export type AdminButtonPermission = 'view' | 'export' | 'add' | 'edit' | 'delete'

export interface AdminButtonCapabilities {
  canView: boolean
  canExport: boolean
  canAdd: boolean
  canEdit: boolean
  canDelete: boolean
}

const KNOWN_PERMISSIONS = new Set<AdminButtonPermission>([
  'view',
  'export',
  'add',
  'edit',
  'delete'
])

function normalizeAdminButtonPermissions(buttons: unknown): Set<AdminButtonPermission> {
  if (!Array.isArray(buttons)) return new Set()

  return new Set(
    buttons.filter(
      (button): button is AdminButtonPermission =>
        typeof button === 'string' && KNOWN_PERMISSIONS.has(button as AdminButtonPermission)
    )
  )
}

export function getAdminButtonCapabilities(buttons: unknown): AdminButtonCapabilities {
  const permissions = normalizeAdminButtonPermissions(buttons)

  return {
    canView: permissions.has('view'),
    canExport: permissions.has('export'),
    canAdd: permissions.has('add'),
    canEdit: permissions.has('edit'),
    canDelete: permissions.has('delete')
  }
}
