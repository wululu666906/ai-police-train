export interface StudentImportSummary {
  total: number
  new_students: number
  matched: number
  new_classes: number
  skipped: number
  errors: number
  ready: number
  synced: number
  created_classes?: number
}

export interface StudentImportItem {
  id: number
  row_number: number
  student_no: string
  matched_user_id: number | null
  is_new: boolean
  data: {
    student_no?: string
    real_name?: string
    gender?: string
    unit?: string
    department?: string
    class_name?: string
    source_kind?: 'roster' | 'orphan_photo'
  }
  source_kind: 'roster' | 'orphan_photo'
  errors: string[]
  warnings: string[]
  has_photo: boolean
  photo_url: string | null
  replace_face: boolean
  replace_class: boolean
  status: 'pending' | 'error' | 'synced' | 'failed'
  result?: Record<string, unknown> | null
}

export interface StudentImportBatch {
  batch_id: string
  source_mode: 'zip' | 'files'
  source_name?: string | null
  status: string
  summary: StudentImportSummary
  items: StudentImportItem[]
}
