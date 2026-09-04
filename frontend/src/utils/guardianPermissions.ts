const GUARDIAN_MANAGERS = new Set([
  'super_admin', 'kulup_yonetici',
])

export function canManageGuardians(role?: string | null): boolean {
  return role ? GUARDIAN_MANAGERS.has(role) : false
}
