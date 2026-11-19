import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import AppShell from '@/components/layout/AppShell'
import { useAuth } from '@/hooks/useAuth'
import { tasksApi, taskIsOverdue, TASK_MANAGERS, TASK_READ_ALL, TASK_STATUSES, TASK_PRIORITIES } from '@/api/tasks'
import type { Task, TaskAssignee, TaskParams, TaskStatus } from '@/api/tasks'
import TaskForm from './TaskForm'

function csvCell(value: string): string {
  // Excel formül yorumlamasını engelle; Türkçe karakterler UTF-8 BOM ile korunur.
  const safe = /^[=+\-@\t\r\n]/.test(value) ? `'${value}` : value
  return `"${safe.replace(/"/g, '""')}"`
}
export default function TasksPage() {
  const { user } = useAuth()
  const canManage = TASK_MANAGERS.includes(user?.role ?? '')
  const readAll = TASK_READ_ALL.includes(user?.role ?? '')
  const [searchParams, setSearchParams] = useSearchParams()
  const view = ['open', 'overdue', 'all'].includes(searchParams.get('view') ?? '') ? searchParams.get('view')! : 'open'
  const [search, setSearch] = useState('')
  const [priority, setPriority] = useState('')
  const [status, setStatus] = useState('')
  const [assignee, setAssignee] = useState('')
  const [people, setPeople] = useState<TaskAssignee[]>([])
  const [peopleError, setPeopleError] = useState(false)
  const [peopleAttempt, setPeopleAttempt] = useState(0)
  useEffect(() => {
    if (!canManage) return
    let cancelled = false
    setPeopleError(false)
    tasksApi.assignees().then(({ data }) => { if (!cancelled) setPeople(data) })
      .catch(() => { if (!cancelled) setPeopleError(true) })
    return () => { cancelled = true }
  }, [canManage, peopleAttempt])
  const [skip, setSkip] = useState(0)
  const [items, setItems] = useState<Task[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)
  const [editing, setEditing] = useState<Task | null | undefined>(undefined)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')
  const params: TaskParams = { assigned_person_id: assignee || undefined, search: search || undefined, priority: priority as TaskParams['priority'] || undefined, status: status as TaskParams['status'] || undefined, open_only: view === 'open', overdue_only: view === 'overdue' }
  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')
    tasksApi.list({ assigned_person_id: assignee || undefined, search: search || undefined, priority: priority as TaskParams['priority'] || undefined, status: status as TaskParams['status'] || undefined, open_only: view === 'open', overdue_only: view === 'overdue', skip, limit: 20 })
      .then(({ data }) => {
        if (cancelled) return
        if (skip && skip >= data.total) { setSkip(Math.max(0, Math.floor((data.total - 1) / 20) * 20)); return }
        setItems(data.items); setTotal(data.total)
      })
      .catch(() => { if (!cancelled) setError('Görevler yüklenemedi. Tekrar deneyin.') })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [search, priority, status, view, skip, attempt, assignee])
  async function changeStatus(task: Task, next: TaskStatus) {
    setBusy(true); setNotice('')
    try { await tasksApi.update(task.id, { status: next }); setAttempt((n) => n + 1); setNotice('Görev durumu güncellendi.') }
    catch { setNotice('Görev durumu güncellenemedi. Tekrar deneyin.') }
    finally { setBusy(false) }
  }
  async function remove(task: Task) {
    if (!window.confirm(`“${task.title}” görevi silinsin mi?`)) return
    setBusy(true); setNotice('')
    try { await tasksApi.delete(task.id); setAttempt((n) => n + 1); setNotice('Görev silindi.') }
    catch { setNotice('Görev silinemedi. Tekrar deneyin.') }
    finally { setBusy(false) }
  }
  async function exportCsv() {
    setBusy(true); setNotice('')
    try {
      const tasks = await tasksApi.listAll(params)
      const rows = [['Başlık', 'Açıklama', 'Sorumlu', 'Son Tarih', 'Öncelik', 'Durum'], ...tasks.map((t) => [t.title, t.description ?? '', t.assigned_person_name ?? '', t.due_date ?? '', TASK_PRIORITIES[t.priority], TASK_STATUSES[t.status]])]
      const blob = new Blob(['\uFEFF' + rows.map((row) => row.map(csvCell).join(';')).join('\r\n')], { type: 'text/csv;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a'); link.href = url; link.download = 'myk-gorevler.csv'; link.click(); URL.revokeObjectURL(url)
      setNotice(`${tasks.length} görev dışa aktarıldı.`)
    } catch { setNotice('Dışa aktarma tamamlanamadı. Tekrar deneyin.') }
    finally { setBusy(false) }
  }
  return <AppShell title="Görevler">
    <div className="page-header"><div><h1 className="page-title">Görevler</h1><p>{readAll ? 'Kulüp görevleri, sorumlular ve son tarihler' : 'Size atanan görevler ve son tarihleri'}</p></div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}><button className="btn btn-ghost" disabled={busy || loading || !!error} onClick={exportCsv}>CSV İndir</button>{canManage && <button className="btn btn-primary" onClick={() => setEditing(null)}>Yeni Görev</button>}</div>
    </div>
    <div className="filter-bar" style={{ flexWrap: 'wrap', gap: 10 }}>
      <input className="form-input" style={{ maxWidth: 280 }} aria-label="Görev ara" placeholder="Başlık veya açıklama ara…" value={search} onChange={(e) => { setSearch(e.target.value); setSkip(0) }} />
      <select className="form-select" aria-label="Görev görünümü" value={view} onChange={(e) => { setSearchParams({ view: e.target.value }); setSkip(0); setStatus('') }}><option value="open">Açık Görevler</option><option value="overdue">Geciken Görevler</option><option value="all">Tüm Görevler</option></select>
      <select className="form-select" aria-label="Öncelik filtresi" value={priority} onChange={(e) => { setPriority(e.target.value); setSkip(0) }}><option value="">Tüm Öncelikler</option>{Object.entries(TASK_PRIORITIES).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select>
      <select className="form-select" aria-label="Durum filtresi" value={status} onChange={(e) => { setStatus(e.target.value); setSkip(0) }}><option value="">Tüm Durumlar</option>{Object.entries(TASK_STATUSES).filter(([key]) => view === 'all' || ['acik', 'devam_ediyor'].includes(key)).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select>
      {canManage && <select className="form-select" aria-label="Sorumlu filtresi" value={assignee} onChange={(e) => { setAssignee(e.target.value); setSkip(0) }}><option value="">Tüm Sorumlular</option>{people.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select>}
    </div>
    {peopleError && <p role="alert">Sorumlu filtresi yüklenemedi. <button className="btn btn-ghost" onClick={() => setPeopleAttempt((n) => n + 1)}>Tekrar Dene</button></p>}
    {notice && <p role="status">{notice}</p>}
    {loading ? <p role="status">Görevler yükleniyor…</p> : error ? <div role="alert"><p>{error}</p><button className="btn btn-ghost" onClick={() => setAttempt((n) => n + 1)}>Tekrar Dene</button></div> : <>
      <p role="status">{total} görev{total > 0 && ` · ${skip + 1}–${Math.min(skip + 20, total)} arası gösteriliyor`}</p>
      {!items.length ? <div className="card"><div className="card-body">Bu filtrelere uygun görev yok.{canManage && ' Yeni Görev düğmesiyle görev ekleyebilirsiniz.'}</div></div> : <div className="task-grid">{items.map((task) => <article key={task.id} className="card">
        <div className="card-body">
          <h2 style={{ fontSize: 18, overflowWrap: 'anywhere' }}>{task.title}</h2>
          {task.description && <p style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{task.description}</p>}
          <p><strong>Sorumlu:</strong> {task.assigned_person_name ?? 'Atanmamış'}</p>
          <p><strong>Son tarih:</strong> {task.due_date ? new Date(`${task.due_date}T00:00:00`).toLocaleDateString('tr-TR') : 'Belirlenmedi'} {taskIsOverdue(task) && <span className="badge badge-danger">Gecikti</span>}</p>
          <p><strong>Öncelik:</strong> {TASK_PRIORITIES[task.priority]} · {TASK_STATUSES[task.status]}</p>
          {(canManage || !readAll) && <label className="form-label">Durum güncelle<select className="form-select" aria-label={`${task.title} durumu`} value={task.status} disabled={busy} onChange={(e) => changeStatus(task, e.target.value as TaskStatus)}>{Object.entries(TASK_STATUSES).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>}
          {canManage && <div style={{ display: 'flex', gap: 8, marginTop: 12 }}><button className="btn btn-ghost" disabled={busy} onClick={() => setEditing(task)}>Düzenle</button><button className="btn btn-ghost" disabled={busy} onClick={() => remove(task)}>Sil</button></div>}
        </div>
      </article>)}</div>}
      {total > 20 && <div style={{ display: 'flex', gap: 16, alignItems: 'center', marginTop: 20 }}><button className="btn btn-ghost" disabled={!skip} onClick={() => setSkip((n) => Math.max(0, n - 20))}>← Önceki</button><span>{Math.floor(skip / 20) + 1} / {Math.ceil(total / 20)}</span><button className="btn btn-ghost" disabled={skip + 20 >= total} onClick={() => setSkip((n) => n + 20)}>Sonraki →</button></div>}
    </>}
    {editing !== undefined && <TaskForm task={editing} onClose={() => setEditing(undefined)} onSaved={() => { setEditing(undefined); setAttempt((n) => n + 1); setNotice('Görev kaydedildi.') }} />}
  </AppShell>
}
