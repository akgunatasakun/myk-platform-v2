interface Props {
  ready: boolean
  deferred: boolean
  busy: boolean
  error: string
  onUpdate: () => void
  onDefer: () => void
  onOpen: () => void
}

export default function UpdateNotice({ ready, deferred, busy, error, onUpdate, onDefer, onOpen }: Props) {
  if (!ready) return null
  return <aside className="pwa-update" aria-label="Panel güncellemesi">
    {deferred ? <button type="button" className="btn btn-secondary" onClick={onOpen}>Yeni sürüm hazır</button> : <div className="pwa-update-card" role="status">
      <strong>Yeni sürüm hazır</strong>
      <p>Güncellemeden önce açık panel sekmelerindeki bilgilerinizi kaydedin.</p>
      {error && <p role="alert">{error}</p>}
      <div className="pwa-update-actions">
        <button type="button" className="btn btn-secondary" onClick={onDefer} disabled={busy}>Daha sonra</button>
        <button type="button" className="btn btn-primary" onClick={onUpdate} disabled={busy}>{busy ? 'Güncelleniyor…' : 'Güncelle'}</button>
      </div>
    </div>}
  </aside>
}
