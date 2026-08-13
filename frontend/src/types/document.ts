export type DocumentType =
  | 'prosedur'
  | 'talimati'
  | 'form'
  | 'el_kitabi'
  | 'egitim_materyali'
  | 'operasyonel'
  | 'sporcu_belgesi'
  | 'ekipman_belgesi'
  | 'diger'

export type ContentStatus =
  | 'tamamlandi'
  | 'taslak'
  | 'eksik'
  | 'placeholder'
  | 'bilinmiyor'

export type RevisionStatus =
  | 'taslak'
  | 'incelemede'
  | 'onaylandi'
  | 'yayinda'
  | 'arsivlendi'
  | 'bloke'

export type FileRole =
  | 'source'
  | 'published'
  | 'attachment'
  | 'signed'
  | 'rendered'
  | 'other'

export interface DocumentCategory {
  id: string
  code: string
  name: string
  sort_order: number
  is_active: boolean
}

export interface DocumentRevisionFile {
  id: string
  revision_id: string
  file_role: FileRole
  original_filename: string
  mime_type: string
  file_size: number
  sha256: string
  storage_key: string
  is_primary: boolean
  created_at: string
}

export interface DocumentRevision {
  id: string
  document_id: string
  revision_code: string
  revision_no?: number
  status: RevisionStatus
  is_current: boolean
  files: DocumentRevisionFile[]
  created_at: string
  updated_at: string
}

export interface Document {
  id: string
  club_id: string
  code: string
  title: string
  document_type: DocumentType
  content_status: ContentStatus
  category_id?: string
  owner_type?: string
  owner_id?: string
  current_revision_id?: string
  is_active: boolean
  is_deleted: boolean
  revisions?: DocumentRevision[]
  created_at: string
  updated_at: string
}

export interface DocumentCreate {
  code: string
  title: string
  document_type: DocumentType
  content_status?: ContentStatus
  category_id?: string
  owner_type?: string
  owner_id?: string
}

export interface RevisionCreate {
  revision_code: string
  status?: RevisionStatus
  description?: string
  source?: string
  manifest_row_id?: string
  is_current?: boolean
}
