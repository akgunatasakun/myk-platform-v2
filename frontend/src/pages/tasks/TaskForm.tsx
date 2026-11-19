import { useEffect, useState } from 'react'
import { tasksApi, TASK_PRIORITIES, TASK_STATUSES } from '@/api/tasks'
import type { Task, TaskAssignee, TaskInput } from '@/api/tasks'

export default function TaskForm({ task, onClose, onSaved }: { task: Task | null; onClose: () => void; onSaved: () => void }) {
  const [form, setForm] = useState<TaskInput>(task ?? { title: '', description: '', assigned_person_id: null, due_date: null, priority: 'normal', status: 'acik' })
  const [people, setPeople] = useState<TaskAssignee[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [attempt, setAttempt] = useState(0)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setLoadError(false)
    tasksApi.assignees().then(({ data }) => { if (!cancelled) setPeople(data) })
      .catch(() => { if (!cancelled) setLoadError(true) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [attempt])
  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setError('')
    setSaving(true)
    // Görev nesnesinin salt okunur alanlarını API'ye göndermeyin.
    const data: TaskInput = { title: form.title.trim(), description: form.description?.trim() || null, assigned_person_id: form.assigned_person_id, due_date: form.due_date, priority: form.priority, status: form.status }
    try {
      if (task) await tasksApi.update(task.id, data)
      else await tasksApi.create(data)
      onSaved()
    } catch { setError('Görev kaydedilemedi. Sorumlu kaydının aktif olduğunu kontrol edip tekrar deneyin.') }
    finally { setSaving(false) }
  }
  const unavailable = form.assigned_person_id && !people.some((p) => p.id === form.assigned_person_id)
  return <div className="modal-overlay"><div className="modal" role="dialog" aria-modal="true" aria-labelledby="task-form-title" style={{ maxWidth: 600 }}>
    <div className="modal-header"><h2 id="task-form-title">{task ? 'Görevi Düzenle' : 'Yeni Görev'}</h2><button type="button" className="btn btn-ghost" onClick={onClose} disabled={saving} aria-label="Kapat">×</button></div>
    <form onSubmit={submit}>
      <div className="modal-body">
        {error && <p role="alert" className="text-danger">{error}</p>}
        <div className="form-group"><label className="form-label" htmlFor="task-title">Başlık *</label><input autoFocus id="task-title" className="form-input" required maxLength={200} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></div>
        <div className="form-group"><label className="form-label" htmlFor="task-description">Açıklama</label><textarea id="task-description" className="form-input" rows={4} maxLength={10000} value={form.description ?? ''} onChange={(e) => setForm({ ...form, description: e.target.value })} /></div>
        <div className="form-group"><label className="form-label" htmlFor="task-assignee">Sorumlu</label>
          <select id="task-assignee" className="form-select" disabled={loading || loadError} value={form.assigned_person_id ?? ''} onChange={(e) => setForm({ ...form, assigned_person_id: e.target.value || null })}>
            <option value="">Atanmamış</option>{unavailable && <option value={form.assigned_person_id!}>{task?.assigned_person_name ?? 'Önceki sorumlu'} (aktif değil)</option>}{people.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
          {loading && <p role="status">Sorumlu listesi yükleniyor…</p>}
          {loadError && <p role="alert">Sorumlu listesi yüklenemedi. <button type="button" className="btn btn-ghost" onClick={() => setAttempt((n) => n + 1)}>Tekrar Dene</button></p>}
          {!loading && !loadError && <small>Aktif antrenör ve personel kayıtları arasından seçin.</small>}
        </div>
        <div className="form-group"><label className="form-label" htmlFor="task-due">Son Tarih</label><input id="task-due" type="date" className="form-input" value={form.due_date ?? ''} onChange={(e) => setForm({ ...form, due_date: e.target.value || null })} /></div>
        <div className="form-row">
          <div className="form-group"><label className="form-label" htmlFor="task-priority">Öncelik</label><select id="task-priority" className="form-select" value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value as TaskInput['priority'] })}>{Object.entries(TASK_PRIORITIES).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></div>
          <div className="form-group"><label className="form-label" htmlFor="task-status">Durum</label><select id="task-status" className="form-select" value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value as TaskInput['status'] })}>{Object.entries(TASK_STATUSES).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></div>
        </div>
      </div>
      <div className="modal-footer"><button type="button" className="btn btn-ghost" disabled={saving} onClick={onClose}>Vazgeç</button><button className="btn btn-primary" disabled={saving || loading || loadError || !form.title.trim()}>{saving ? 'Kaydediliyor…' : 'Kaydet'}</button></div>
    </form>
  </div></div>
}
