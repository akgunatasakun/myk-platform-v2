/**
 * Operasyonel Takvim sayfası — Sprint 12
 *
 * Eğitim oturumları, ödeme vadeleri, ekipman bakım/sigorta ve sporcu
 * belgelerini tek takvimde birleştirir.
 *
 * - Aylık grid navigasyonu (önceki/sonraki ay)
 * - Gün hücrelerine kategori rengi ile nokta
 * - Gün seçilince alt listede o güne ait etkinlikler
 * - Seçim yoksa tüm ay etkinlikleri
 */
import { useEffect, useState, useCallback, useMemo } from 'react'
import AppShell from '@/components/layout/AppShell'
import { fetchCalendarEvents } from '@/api/calendar'
import type { CalendarEvent, CalendarCategory, CalendarSeverity } from '@/types/calendar'

// ── Sabitler ──────────────────────────────────────────────────────────────────

const CATEGORY_COLORS: Record<CalendarCategory, string> = {
  training:  '#3b82f6',  // mavi
  payment:   '#f59e0b',  // amber
  equipment: '#8b5cf6',  // mor
  athlete:   '#10b981',  // yeşil
}

const CATEGORY_LABELS: Record<CalendarCategory, string> = {
  training:  '⛵ Eğitim',
  payment:   '💳 Ödeme',
  equipment: '🔧 Ekipman',
  athlete:   '🏅 Sporcu',
}

const SEVERITY_COLORS: Record<CalendarSeverity, string> = {
  info:     '#3b82f6',
  warning:  '#f59e0b',
  critical: '#ef4444',
}

const SOURCE_LABELS: Record<string, string> = {
  training_session:      'Eğitim Oturumu',
  payment:               'Ödeme Vadesi',
  equipment_maintenance: 'Ekipman Bakım',
  equipment_insurance:   'Ekipman Sigorta',
  athlete_license:       'Lisans Sonu',
  athlete_visa:          'Vize Sonu',
  athlete_health:        'Sağlık Raporu Sonu',
}

const WEEKDAYS = ['Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt', 'Paz']

const MONTHS = [
  'Ocak','Şubat','Mart','Nisan','Mayıs','Haziran',
  'Temmuz','Ağustos','Eylül','Ekim','Kasım','Aralık',
]

// ── Yardımcılar ───────────────────────────────────────────────────────────────

function toYMD(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function parseYMD(s: string): Date {
  const [y, m, d] = s.split('-').map(Number)
  return new Date(y, m - 1, d)
}

function formatDate(dateStr: string): string {
  const d = parseYMD(dateStr)
  return d.toLocaleDateString('tr-TR', { day: 'numeric', month: 'long', year: 'numeric' })
}

// ISO haftası: Pazartesi=0
function dayOfWeekMon(d: Date): number {
  return (d.getDay() + 6) % 7
}

// ── Bileşenler ────────────────────────────────────────────────────────────────

function SeverityBadge({ severity }: { severity: CalendarSeverity }) {
  const labels: Record<CalendarSeverity, string> = {
    info: 'Bilgi',
    warning: 'Uyarı',
    critical: 'Kritik',
  }
  return (
    <span style={{
      fontSize: 11,
      fontWeight: 600,
      padding: '2px 7px',
      borderRadius: 4,
      backgroundColor: SEVERITY_COLORS[severity] + '22',
      color: SEVERITY_COLORS[severity],
      border: `1px solid ${SEVERITY_COLORS[severity]}44`,
    }}>
      {labels[severity]}
    </span>
  )
}

function EventRow({ ev }: { ev: CalendarEvent }) {
  const catColor = CATEGORY_COLORS[ev.category]
  return (
    <div style={{
      display: 'flex',
      alignItems: 'flex-start',
      gap: 12,
      padding: '10px 14px',
      borderLeft: `4px solid ${SEVERITY_COLORS[ev.severity]}`,
      backgroundColor: '#fff',
      borderRadius: 6,
      marginBottom: 8,
      boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
    }}>
      {/* Kategori nokta */}
      <div style={{
        width: 10,
        height: 10,
        borderRadius: '50%',
        backgroundColor: catColor,
        flexShrink: 0,
        marginTop: 4,
      }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontWeight: 600,
          fontSize: 14,
          color: '#111827',
          marginBottom: 2,
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}>
          {ev.title}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 12, color: '#6b7280' }}>
            {SOURCE_LABELS[ev.source_type] ?? ev.source_type}
          </span>
          {ev.detail && (
            <span style={{ fontSize: 12, color: '#9ca3af' }}>· {ev.detail}</span>
          )}
          <SeverityBadge severity={ev.severity} />
        </div>
      </div>
      <div style={{
        fontSize: 12,
        color: '#6b7280',
        flexShrink: 0,
        paddingTop: 2,
      }}>
        {formatDate(ev.date)}
      </div>
    </div>
  )
}

// ── Ana bileşen ───────────────────────────────────────────────────────────────

export default function CalendarPage() {
  const today = new Date()
  const [year, setYear] = useState(today.getFullYear())
  const [month, setMonth] = useState(today.getMonth()) // 0-indexed
  const [selectedDay, setSelectedDay] = useState<string | null>(null)
  const [events, setEvents] = useState<CalendarEvent[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Ay değişince seçim sıfırlanır
  const prevMonth = useCallback(() => {
    setSelectedDay(null)
    if (month === 0) { setYear(y => y - 1); setMonth(11) }
    else setMonth(m => m - 1)
  }, [month])

  const nextMonth = useCallback(() => {
    setSelectedDay(null)
    if (month === 11) { setYear(y => y + 1); setMonth(0) }
    else setMonth(m => m + 1)
  }, [month])

  // Ay ilk/son günü
  const dateFrom = useMemo(() => toYMD(new Date(year, month, 1)), [year, month])
  const dateTo = useMemo(() => toYMD(new Date(year, month + 1, 0)), [year, month])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchCalendarEvents(dateFrom, dateTo)
      setEvents(data.events)
    } catch {
      setError('Takvim verisi yüklenemedi.')
    } finally {
      setLoading(false)
    }
  }, [dateFrom, dateTo])

  useEffect(() => { load() }, [load])

  // Gün → etkinlik haritası
  const eventsByDay = useMemo(() => {
    const map: Record<string, CalendarEvent[]> = {}
    for (const ev of events) {
      if (!map[ev.date]) map[ev.date] = []
      map[ev.date].push(ev)
    }
    return map
  }, [events])

  // Seçili gün veya tüm ay etkinlikleri
  const displayedEvents = useMemo(() => {
    if (selectedDay) return eventsByDay[selectedDay] ?? []
    return events
  }, [selectedDay, eventsByDay, events])

  // Ay grid oluştur
  const gridDays = useMemo(() => {
    const firstDay = new Date(year, month, 1)
    const lastDay = new Date(year, month + 1, 0)
    const offset = dayOfWeekMon(firstDay) // Pazartesi başlangıçlı
    const cells: (number | null)[] = []
    for (let i = 0; i < offset; i++) cells.push(null)
    for (let d = 1; d <= lastDay.getDate(); d++) cells.push(d)
    // 7'nin katına tamamla
    while (cells.length % 7 !== 0) cells.push(null)
    return cells
  }, [year, month])

  const todayStr = toYMD(today)

  // Kategori filtresi
  const [activeCategories, setActiveCategories] = useState<Set<CalendarCategory>>(
    new Set(['training', 'payment', 'equipment', 'athlete'])
  )
  const toggleCategory = (cat: CalendarCategory) => {
    setActiveCategories(prev => {
      const next = new Set(prev)
      if (next.has(cat)) { if (next.size > 1) next.delete(cat) }
      else next.add(cat)
      return next
    })
  }
  const filteredEvents = displayedEvents.filter(e => activeCategories.has(e.category))

  return (
    <AppShell>
      <div style={{ maxWidth: 1100, margin: '0 auto', padding: '24px 16px' }}>
        {/* Başlık */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: '#111827', margin: 0 }}>
            📅 Operasyonel Takvim
          </h1>
          <button
            onClick={load}
            style={{
              padding: '6px 14px',
              borderRadius: 6,
              border: '1px solid #d1d5db',
              background: '#fff',
              cursor: 'pointer',
              fontSize: 13,
              color: '#374151',
            }}
          >
            ↻ Yenile
          </button>
        </div>

        {/* Kategori filtreleri */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
          {(Object.entries(CATEGORY_LABELS) as [CalendarCategory, string][]).map(([cat, label]) => {
            const active = activeCategories.has(cat)
            return (
              <button
                key={cat}
                onClick={() => toggleCategory(cat)}
                style={{
                  padding: '5px 12px',
                  borderRadius: 20,
                  border: `2px solid ${CATEGORY_COLORS[cat]}`,
                  background: active ? CATEGORY_COLORS[cat] : '#fff',
                  color: active ? '#fff' : CATEGORY_COLORS[cat],
                  cursor: 'pointer',
                  fontSize: 13,
                  fontWeight: 500,
                  transition: 'all 0.15s',
                }}
              >
                {label}
              </button>
            )
          })}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '340px 1fr', gap: 24, alignItems: 'start' }}>

          {/* ── Sol: Aylık grid ── */}
          <div style={{
            background: '#fff',
            borderRadius: 10,
            border: '1px solid #e5e7eb',
            overflow: 'hidden',
          }}>
            {/* Ay navigasyonu */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '14px 16px',
              borderBottom: '1px solid #f3f4f6',
              background: '#f9fafb',
            }}>
              <button
                onClick={prevMonth}
                style={{ border: 'none', background: 'none', cursor: 'pointer', fontSize: 18, color: '#374151', padding: '0 6px' }}
              >‹</button>
              <span style={{ fontWeight: 700, fontSize: 15, color: '#111827' }}>
                {MONTHS[month]} {year}
              </span>
              <button
                onClick={nextMonth}
                style={{ border: 'none', background: 'none', cursor: 'pointer', fontSize: 18, color: '#374151', padding: '0 6px' }}
              >›</button>
            </div>

            {/* Haftanın günleri */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7,1fr)' }}>
              {WEEKDAYS.map(w => (
                <div key={w} style={{
                  textAlign: 'center',
                  fontSize: 11,
                  fontWeight: 600,
                  color: '#9ca3af',
                  padding: '8px 0 6px',
                  borderBottom: '1px solid #f3f4f6',
                }}>
                  {w}
                </div>
              ))}
            </div>

            {/* Gün hücreleri */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7,1fr)' }}>
              {gridDays.map((d, i) => {
                if (d === null) {
                  return <div key={`e${i}`} style={{ padding: '6px', minHeight: 44 }} />
                }
                const dayStr = toYMD(new Date(year, month, d))
                const dayEvs = (eventsByDay[dayStr] ?? []).filter(e => activeCategories.has(e.category))
                const isToday = dayStr === todayStr
                const isSelected = dayStr === selectedDay

                return (
                  <div
                    key={dayStr}
                    onClick={() => setSelectedDay(isSelected ? null : dayStr)}
                    style={{
                      padding: '6px 4px',
                      minHeight: 44,
                      cursor: dayEvs.length > 0 || !isToday ? 'pointer' : 'default',
                      borderRadius: 6,
                      margin: 2,
                      background: isSelected
                        ? '#eff6ff'
                        : isToday
                        ? '#fef3c7'
                        : 'transparent',
                      border: isSelected ? '2px solid #3b82f6' : '2px solid transparent',
                      transition: 'background 0.1s',
                    }}
                  >
                    <div style={{
                      textAlign: 'center',
                      fontSize: 13,
                      fontWeight: isToday ? 700 : 400,
                      color: isToday ? '#b45309' : '#374151',
                      marginBottom: 3,
                    }}>
                      {d}
                    </div>
                    {/* Etkinlik noktaları (maks 4) */}
                    <div style={{ display: 'flex', justifyContent: 'center', gap: 2, flexWrap: 'wrap' }}>
                      {dayEvs.slice(0, 4).map((ev, j) => (
                        <div
                          key={j}
                          style={{
                            width: 6,
                            height: 6,
                            borderRadius: '50%',
                            backgroundColor: SEVERITY_COLORS[ev.severity],
                            flexShrink: 0,
                          }}
                          title={ev.title}
                        />
                      ))}
                    </div>
                  </div>
                )
              })}
            </div>

            {/* Toplam sayaç */}
            <div style={{
              padding: '10px 16px',
              borderTop: '1px solid #f3f4f6',
              fontSize: 12,
              color: '#6b7280',
              textAlign: 'center',
            }}>
              {loading
                ? 'Yükleniyor…'
                : `Bu ay ${events.filter(e => activeCategories.has(e.category)).length} etkinlik`
              }
            </div>
          </div>

          {/* ── Sağ: Etkinlik listesi ── */}
          <div>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: 14,
            }}>
              <h2 style={{ fontSize: 16, fontWeight: 600, color: '#111827', margin: 0 }}>
                {selectedDay
                  ? formatDate(selectedDay)
                  : `${MONTHS[month]} ${year} — Tüm Etkinlikler`
                }
              </h2>
              {selectedDay && (
                <button
                  onClick={() => setSelectedDay(null)}
                  style={{
                    fontSize: 12,
                    color: '#6b7280',
                    border: 'none',
                    background: 'none',
                    cursor: 'pointer',
                    padding: '4px 8px',
                  }}
                >
                  ✕ Seçimi kaldır
                </button>
              )}
            </div>

            {error && (
              <div style={{
                padding: '12px 16px',
                background: '#fef2f2',
                border: '1px solid #fecaca',
                borderRadius: 8,
                color: '#dc2626',
                fontSize: 14,
                marginBottom: 12,
              }}>
                {error}
              </div>
            )}

            {!loading && filteredEvents.length === 0 && (
              <div style={{
                padding: '32px',
                textAlign: 'center',
                color: '#9ca3af',
                background: '#fff',
                borderRadius: 10,
                border: '1px solid #e5e7eb',
              }}>
                {selectedDay
                  ? 'Bu gün için etkinlik yok.'
                  : 'Bu ay için etkinlik bulunamadı.'
                }
              </div>
            )}

            {filteredEvents.map(ev => (
              <EventRow key={ev.id} ev={ev} />
            ))}

            {loading && (
              <div style={{ textAlign: 'center', padding: 32, color: '#9ca3af' }}>
                Yükleniyor…
              </div>
            )}
          </div>
        </div>

        {/* Renk açıklama */}
        <div style={{
          marginTop: 24,
          display: 'flex',
          gap: 20,
          flexWrap: 'wrap',
          fontSize: 12,
          color: '#6b7280',
        }}>
          {(Object.entries(SEVERITY_COLORS) as [CalendarSeverity, string][]).map(([sev, col]) => (
            <div key={sev} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              <div style={{ width: 10, height: 10, borderRadius: '50%', backgroundColor: col }} />
              {{info:'Bilgi',warning:'Uyarı',critical:'Kritik'}[sev]}
            </div>
          ))}
        </div>
      </div>
    </AppShell>
  )
}
