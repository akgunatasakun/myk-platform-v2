// UI işlem kontrolleri backend yetkilerini izler; asıl yetki denetimi sunucudadır.
const TRAINING_MANAGERS = new Set(['super_admin', 'kulup_yonetici', 'sportif_direktor', 'basantrenor'])
const ACCOUNT_MANAGERS = new Set(['super_admin', 'kulup_yonetici', 'genel_sekreter'])
const PERSON_MANAGERS = new Set(['super_admin', 'kulup_yonetici'])
export const canManageTraining = (role?: string) => TRAINING_MANAGERS.has(role ?? '')
export const canManageAccounts = (role?: string) => ACCOUNT_MANAGERS.has(role ?? '')
export const canManagePersons = (role?: string) => PERSON_MANAGERS.has(role ?? '')
