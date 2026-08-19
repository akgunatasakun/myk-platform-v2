/**
 * API istek sabitleri — tüm frontend bileşenlerinde bu değerler kullanılır.
 *
 * Backend /persons endpoint'i le=1000 ile yapılandırılmıştır.
 * Dropdown listeleri için bu limit yeterlidir; sayfalama gereken
 * tam listeler için ayrıca skip/limit parametresi gönderilir.
 */

/** Kişi seçim dropdown'larında kullanılan maksimum kayıt sayısı. */
export const PERSON_LIST_LIMIT = 500
