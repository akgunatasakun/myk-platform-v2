import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { tasksApi, taskIsOverdue, TASK_ROLES, TASK_PRIORITIES } from '@/api/tasks'
import type { TaskList } from '@/api/tasks'

export default function TaskSummary() {
  const { user } = useAuth()
  const allowed = TASK_ROLES.includes(user?.role ?? '')
  const [data, setData] = useState<TaskList | null>(null)
  const [error, setError] = useState(false)
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    if (!allowed) return
    let cancelled = false
    setData(null); setError(false)
    tasksApi.list({ open_only: true, limit: 5 }).then(({ data: result }) => { if (!cancelled) setData(result) })
      .catch(() => { if (!cancelled) setError(true) })
    return () => { cancelled = true }
  }, [allowed, attempt])
  if (!allowed) return null
  return <section className="card" style={{ marginBottom: 20 }} aria-label="Açık görevler">
    <div className="card-header">Açık Görevler{data && ` (${data.total})`}</div>
    <div className="card-body">
      {error ? <div role="alert">Görevler yüklenemedi. <button className="btn btn-ghost" onClick={() => setAttempt((n) => n + 1)}>Tekrar Dene</button></div> : !data ? <p role="status">Görevler yükleniyor…</p> : !data.total ? <p>Açık görev bulunmuyor.</p> : data.items.map((task) => <div key={task.id} style={{ marginBottom: 12, overflowWrap: 'anywhere' }}>
        <strong>{task.title}</strong>{taskIsOverdue(task) && <span className="badge badge-danger"> Gecikti</span>}
        <div style={{ fontSize: 13 }}>{task.assigned_person_name ?? 'Atanmamış'} · {TASK_PRIORITIES[task.priority]} · {task.due_date ? new Date(`${task.due_date}T00:00:00`).toLocaleDateString('tr-TR') : 'Son tarih belirlenmedi'}</div>
      </div>)}
      <Link to="/gorevler?view=open">Görevleri aç</Link>
    </div>
  </section>
}
