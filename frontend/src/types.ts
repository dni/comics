export interface DuplicateRef {
  id: number
  series: string | null
  issue_number: string | null
  year: number | null
  publisher: string | null
  condition_grade: string | null
  numeric_grade: number | null
}

export interface Comic {
  id: number
  series: string | null
  issue_number: string | null
  year: number | null
  publisher: string | null
  language: string | null
  condition_grade: string | null
  numeric_grade: number | null
  confidence: string | null
  notes: string | null
  storage_location: string | null
  suggested_rotation_degrees: number | null
  suggested_crop_left: number | null
  suggested_crop_top: number | null
  suggested_crop_width: number | null
  suggested_crop_height: number | null
  for_sale: boolean
  asking_price: number | null
  ebay_listing_url: string | null
  ebay_listing_status: string | null
  duplicate_of: DuplicateRef[]
  image_url: string | null
  original_filename: string
  imported_at: string
}

export interface FailedComic {
  id: number
  original_filename: string
  original_path: string
  error_message: string | null
  updated_at: string
}

export interface ComicUpdate {
  series?: string | null
  issue_number?: string | null
  year?: number | null
  publisher?: string | null
  language?: string | null
  condition_grade?: string | null
  numeric_grade?: number | null
  confidence?: string | null
  notes?: string | null
  storage_location?: string | null
  for_sale?: boolean | null
  asking_price?: number | null
  ebay_listing_url?: string | null
  ebay_listing_status?: string | null
}

export type ImportStatus = 'processed' | 'skipped' | 'failed'

export interface ImportResult {
  status: ImportStatus
  filename: string
  comic: Comic | null
  error: string | null
}

export interface PublicComic {
  id: number
  series: string | null
  issue_number: string | null
  year: number | null
  publisher: string | null
  condition_grade: string | null
  numeric_grade: number | null
  asking_price: number | null
  ebay_listing_url: string | null
  image_url: string | null
}

export interface AuthStatus {
  has_admin: boolean
}

export interface ModelsInfo {
  models: string[]
  default: string
}

export interface Me {
  username: string
}
