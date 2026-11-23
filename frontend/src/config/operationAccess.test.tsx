import { describe, expect, it, vi } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import type { ReactNode } from 'react'
import { canManageAccounts, canManagePersons, canManageTraining, canManagePayments, canCreateAthletes, canAssignGuardians } from './operationAccess'
import PersonGuardiansSection from '@/pages/persons/PersonGuardiansSection'
import AthleteRegistrationModal from '@/pages/athletes/AthleteRegistrationModal'
import AthletesPage from '@/pages/athletes/AthletesPage'
import PersonFormModal from '@/pages/persons/PersonFormModal'
import TrainingPage from '@/pages/training/TrainingPage'

let currentRole = 'antrenor'
vi.mock('@/hooks/useAuth', () => ({ useAuth: () => ({ user: { role: currentRole } }) }))
vi.mock('react-router-dom', () => ({ useNavigate: () => vi.fn() }))
vi.mock('@/components/layout/AppShell', () => ({ default: ({ children }: { children: ReactNode }) => children }))

const roles = ['super_admin', 'kulup_yonetici', 'genel_sekreter', 'baskan', 'yk_uyesi', 'muhasebe', 'sportif_direktor', 'basantrenor', 'antrenor', 'personel', 'saglik_sorumlusu', 'guvenlik_operasyon', 'veli', 'sporcu', 'uye', 'misafir', 'unknown', '']
describe('Operation controls follow backend write permissions', () => {
  it.each(roles)('checks actions for %s', (role) => {
    currentRole = role
    expect(renderToStaticMarkup(<PersonGuardiansSection personId="athlete-test" />).includes('+ Veli Ekle')).toBe(['super_admin', 'kulup_yonetici', 'antrenor', 'basantrenor'].includes(role))
    expect(canAssignGuardians(role)).toBe(['super_admin', 'kulup_yonetici', 'antrenor', 'basantrenor'].includes(role))
    expect(canCreateAthletes(role)).toBe(['super_admin', 'kulup_yonetici', 'antrenor', 'basantrenor'].includes(role))
    expect(renderToStaticMarkup(<AthletesPage />).includes('+ Yeni Sporcu')).toBe(['super_admin', 'kulup_yonetici', 'antrenor', 'basantrenor'].includes(currentRole))
    expect(canManageTraining(role)).toBe(['super_admin', 'kulup_yonetici', 'sportif_direktor', 'basantrenor'].includes(role))
    expect(canManageAccounts(role)).toBe(['super_admin', 'kulup_yonetici', 'genel_sekreter'].includes(role))
    expect(canManagePayments(role)).toBe(['super_admin', 'kulup_yonetici', 'muhasebe'].includes(role))
    expect(canManagePersons(role)).toBe(['super_admin', 'kulup_yonetici'].includes(role))
  })
  it.each(['antrenor', 'baskan', 'yk_uyesi', 'muhasebe', 'sporcu', 'veli', 'unknown', ''])('does not render create-course control for %s', (role) => {
    currentRole = role
    expect(renderToStaticMarkup(<TrainingPage />)).not.toContain('+ Yeni Eğitim')
  })
  it.each(['super_admin', 'kulup_yonetici', 'sportif_direktor', 'basantrenor'])('keeps create-course control for %s', (role) => {
    currentRole = role
    expect(renderToStaticMarkup(<TrainingPage />)).toContain('+ Yeni Eğitim')
  })
  it('fails closed while the account has not loaded', () => {
    expect(canManagePayments()).toBe(false)
    expect(canManageTraining()).toBe(false)
    expect(canManageAccounts()).toBe(false)
    expect(canManagePersons()).toBe(false)
  })
})

it('limits the coach creation form to athlete kind without account creation', () => {
  const html = renderToStaticMarkup(<PersonFormModal isOpen={true} onClose={() => {}} onSaved={() => {}} forcedRole="sporcu" athleteOnly />)
  expect(html).not.toContain('Panel hesabı oluştur')
  expect(html).not.toContain('>Üye<')
  expect(html).not.toContain('>Antrenör<')
  expect(html).toContain('disabled=""')
})

it('limits new guardian form to guardian kind without creating an account', () => {
  const html = renderToStaticMarkup(<PersonFormModal isOpen={true} onClose={() => {}} onSaved={() => {}} forcedRole="veli" guardianOnly />)
  expect(html).not.toContain('Panel hesabı oluştur')
  expect(html).not.toContain('>Sporcu<')
  expect(html).not.toContain('>Antrenör<')
  expect(html).toContain('disabled=""')
})

it('offers optional guardian choices inside the new athlete form without account creation', () => {
  const html = renderToStaticMarkup(<AthleteRegistrationModal isOpen={true} onClose={() => {}} onSaved={() => {}} />)
  expect(html).toContain('Veli Bilgileri (isteğe bağlı)')
  expect(html).toContain('Şimdilik veli ekleme')
  expect(html).toContain('Mevcut veliyi seç')
  expect(html).toContain('Yeni veli oluştur')
  expect(html).not.toContain('Panel hesabı oluştur')
})
