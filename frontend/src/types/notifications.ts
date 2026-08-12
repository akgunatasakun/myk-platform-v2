export interface Notification {
  id: string
  event_type: string
  aggregate_type: string
  aggregate_id: string | null
  payload: Record<string, unknown> | null
  status: string
  acknowledged_at: string | null
  created_at: string
}

export interface UnreadCount {
  count: number
}

// Event type → Türkçe etiket
export const EVENT_LABELS: Record<string, string> = {
  'payment.created':                     'Ödeme kaydedildi',
  'payment.overdue':                     'Vadesi geçen ödeme',
  'application.submitted':               'Yeni üyelik başvurusu',
  'application.approved':                'Başvuru onaylandı',
  'application.rejected':                'Başvuru reddedildi',
  'training.session.created':            'Eğitim oturumu oluşturuldu',
  'training.session.starts_tomorrow':    'Yarın eğitim oturumu var',
  'equipment.maintenance.due':           'Ekipman bakım zamanı',
  'equipment.insurance.expiring_soon':   'Ekipman sigortası yaklaşıyor',
  'athlete.license.expiring_soon':       'Sporcu lisansı yaklaşıyor',
  'athlete.visa.expiring_soon':          'Sporcu vizesi yaklaşıyor',
  'athlete.health_report.expiring_soon': 'Sağlık raporu yaklaşıyor',
}

// Aggregate type → emoji
export const AGGREGATE_EMOJIS: Record<string, string> = {
  payment:               '💳',
  membership_application: '📋',
  training_session:      '🗓️',
  equipment:             '🛟',
  athlete_profile:       '⛵',
}

// Event type → uyarı seviyesi (badge rengi için)
export type Severity = 'info' | 'warning' | 'danger'

export const EVENT_SEVERITY: Record<string, Severity> = {
  'payment.overdue':                     'danger',
  'equipment.maintenance.due':           'warning',
  'equipment.insurance.expiring_soon':   'warning',
  'athlete.license.expiring_soon':       'warning',
  'athlete.visa.expiring_soon':          'warning',
  'athlete.health_report.expiring_soon': 'warning',
  'application.submitted':               'info',
  'application.approved':                'info',
  'application.rejected':                'info',
  'payment.created':                     'info',
  'training.session.created':            'info',
  'training.session.starts_tomorrow':    'info',
}
