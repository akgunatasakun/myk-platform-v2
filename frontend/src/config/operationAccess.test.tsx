import { describe, expect, it, vi } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import type { ReactNode } from 'react'
import { canManageAccounts, canManagePersons, canManageTraining } from './operationAccess'
import TrainingPage from '@/pages/training/TrainingPage'

let currentRole = 'antrenor'
vi.mock('@/hooks/useAuth', () => ({ useAuth: () => ({ user: { role: currentRole } }) }))
vi.mock('react-router-dom', () => ({ useNavigate: () => vi.fn() }))
vi.mock('@/components/layout/AppShell', () => ({ default: ({ children }: { children: ReactNode }) => children }))

const roles = ['super_admin', 'kulup_yonetici', 'genel_sekreter', 'baskan', 'yk_uyesi', 'muhasebe', 'sportif_direktor', 'basantrenor', 'antrenor', 'personel', 'saglik_sorumlusu', 'guvenlik_operasyon', 'veli', 'sporcu', 'uye', 'misafir', 'unknown', '']
describe('Operation controls follow backend write permissions', () => {
  it.each(roles)('checks actions for %s', (role) => {
    expect(canManageTraining(role)).toBe(['super_admin', 'kulup_yonetici', 'sportif_direktor', 'basantrenor'].includes(role))
    expect(canManageAccounts(role)).toBe(['super_admin', 'kulup_yonetici', 'genel_sekreter'].includes(role))
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
    expect(canManageTraining()).toBe(false)
    expect(canManageAccounts()).toBe(false)
    expect(canManagePersons()).toBe(false)
  })
})
