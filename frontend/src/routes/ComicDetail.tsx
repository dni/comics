import { createResource, createSignal, For, Show, createEffect } from 'solid-js'
import { A, useParams, useNavigate } from '@solidjs/router'
import { getComic, updateComic, uploadComicImage, reclassifyComic, deleteComic } from '../api'
import type { Comic, ComicUpdate } from '../types'
import CropModal, { type CropSuggestion } from '../components/CropModal'
import Lightbox from '../components/Lightbox'
import ConfirmModal from '../components/ConfirmModal'

function suggestionFrom(c: Comic): CropSuggestion | null {
  if (
    c.suggested_rotation_degrees == null ||
    c.suggested_crop_left == null ||
    c.suggested_crop_top == null ||
    c.suggested_crop_width == null ||
    c.suggested_crop_height == null
  ) {
    return null
  }
  return {
    rotation: c.suggested_rotation_degrees,
    left: c.suggested_crop_left,
    top: c.suggested_crop_top,
    width: c.suggested_crop_width,
    height: c.suggested_crop_height,
  }
}

function ebaySoldSearchUrl(c: Comic): string {
  const query = [c.series, c.issue_number ? `#${c.issue_number}` : null, c.year ? String(c.year) : null]
    .filter(Boolean)
    .join(' ')
  const params = new URLSearchParams({ _nkw: query || 'comic book', LH_Sold: '1', LH_Complete: '1' })
  return `https://www.ebay.com/sch/i.html?${params.toString()}`
}

function gradeLabel(c: { condition_grade: string | null; numeric_grade: number | null }): string | null {
  if (c.numeric_grade != null && c.condition_grade) return `${c.condition_grade} ${c.numeric_grade.toFixed(1)}`
  if (c.numeric_grade != null) return c.numeric_grade.toFixed(1)
  return c.condition_grade
}

function suggestedListingTitle(c: Comic): string {
  return [
    c.series,
    c.issue_number ? `#${c.issue_number}` : null,
    c.year ? `(${c.year})` : null,
    c.publisher,
    gradeLabel(c),
  ]
    .filter(Boolean)
    .join(' ')
}

function suggestedListingDescription(c: Comic): string {
  const lines: string[] = []
  if (c.series) {
    lines.push(`${c.series}${c.issue_number ? ` #${c.issue_number}` : ''}${c.year ? ` (${c.year})` : ''}`)
  }
  if (c.publisher) lines.push(`Publisher: ${c.publisher}`)
  if (c.language) lines.push(`Language: ${c.language}`)
  if (gradeLabel(c)) lines.push(`Condition: ${gradeLabel(c)}`)
  if (c.notes) lines.push(`Notes: ${c.notes}`)
  return lines.join('\n')
}

export default function ComicDetail() {
  const params = useParams()
  const navigate = useNavigate()
  const comicId = () => Number(params.id)

  const [comic, { refetch }] = createResource(comicId, getComic)
  const [form, setForm] = createSignal<ComicUpdate>({})
  const [saving, setSaving] = createSignal(false)
  const [saveError, setSaveError] = createSignal<string | null>(null)
  const [savedAt, setSavedAt] = createSignal<number | null>(null)

  const [fullscreen, setFullscreen] = createSignal(false)

  const [cropping, setCropping] = createSignal(false)
  const [cropError, setCropError] = createSignal<string | null>(null)
  const [cropSaving, setCropSaving] = createSignal(false)

  const [reclassifying, setReclassifying] = createSignal(false)
  const [reclassifyError, setReclassifyError] = createSignal<string | null>(null)

  const [confirmingDelete, setConfirmingDelete] = createSignal(false)
  const [deleting, setDeleting] = createSignal(false)
  const [deleteError, setDeleteError] = createSignal<string | null>(null)

  createEffect(() => {
    const c = comic()
    if (c) setForm(fieldsFrom(c))
  })

  function fieldsFrom(c: Comic): ComicUpdate {
    return {
      series: c.series,
      issue_number: c.issue_number,
      year: c.year,
      publisher: c.publisher,
      language: c.language,
      condition_grade: c.condition_grade,
      numeric_grade: c.numeric_grade,
      confidence: c.confidence,
      notes: c.notes,
      storage_location: c.storage_location,
      for_sale: c.for_sale,
      asking_price: c.asking_price,
      ebay_listing_url: c.ebay_listing_url,
      ebay_listing_status: c.ebay_listing_status,
    }
  }

  function setField<K extends keyof ComicUpdate>(key: K, value: ComicUpdate[K]) {
    setForm((f) => ({ ...f, [key]: value }))
  }

  async function handleSubmit(e: Event) {
    e.preventDefault()
    setSaving(true)
    setSaveError(null)
    try {
      await updateComic(comicId(), form())
      await refetch()
      setSavedAt(Date.now())
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : String(err))
    } finally {
      setSaving(false)
    }
  }

  async function handleApplyCrop(blob: Blob) {
    setCropSaving(true)
    setCropError(null)
    try {
      await uploadComicImage(comicId(), blob)
      await refetch()
      setCropping(false)
    } catch (err) {
      setCropError(err instanceof Error ? err.message : String(err))
    } finally {
      setCropSaving(false)
    }
  }

  function copy(text: string) {
    void navigator.clipboard.writeText(text)
  }

  async function handleReclassify() {
    setReclassifying(true)
    setReclassifyError(null)
    try {
      await reclassifyComic(comicId())
      await refetch()
    } catch (err) {
      setReclassifyError(err instanceof Error ? err.message : String(err))
    } finally {
      setReclassifying(false)
    }
  }

  async function handleDelete() {
    setDeleting(true)
    setDeleteError(null)
    try {
      await deleteComic(comicId())
      navigate('/')
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : String(err))
      setDeleting(false)
      setConfirmingDelete(false)
    }
  }

  return (
    <div>
      <A href="/">&larr; Back to library</A>
      <Show when={comic()} fallback={<p>Loading...</p>}>
        {(c) => (
          <>
            <Show when={c().duplicate_of.length > 0}>
              <div class="duplicate-warning">
                Same series &amp; issue already in your catalog — could be a duplicate scan, or
                just another copy you own:
                <ul class="duplicate-list">
                  <For each={c().duplicate_of}>
                    {(dup) => (
                      <li>
                        <A href={`/comic/${dup.id}`}>
                          {dup.series} #{dup.issue_number}
                          {dup.year ? ` (${dup.year})` : ''}
                        </A>
                        {dup.publisher && <span> · {dup.publisher}</span>}
                        {gradeLabel(dup) && <span> · Grade: {gradeLabel(dup)}</span>}
                      </li>
                    )}
                  </For>
                </ul>
              </div>
            </Show>
          <div class="detail">
            <Show when={c().image_url}>
              <div class="detail-image-column">
                <img
                  src={c().image_url ?? ''}
                  class="detail-image detail-image-clickable"
                  onClick={() => setFullscreen(true)}
                />
                <button type="button" class="secondary" onClick={() => setCropping(true)}>
                  Crop / Rotate
                </button>
                <button type="button" class="secondary" onClick={handleReclassify} disabled={reclassifying()}>
                  {reclassifying() ? 'Reclassifying...' : 'Reclassify with AI'}
                </button>
                <Show when={reclassifyError()}>
                  <p class="error">{reclassifyError()}</p>
                </Show>
                <button type="button" class="danger" onClick={() => setConfirmingDelete(true)}>
                  Delete
                </button>
                <Show when={deleteError()}>
                  <p class="error">{deleteError()}</p>
                </Show>
              </div>
            </Show>
          <div class="detail-right-column">
            <form class="detail-form" onSubmit={handleSubmit}>
              <div class="detail-form-header">
                <Show when={saveError()}>
                  <p class="error">{saveError()}</p>
                </Show>
                <Show when={savedAt() && !saving()}>
                  <p class="saved">Saved.</p>
                </Show>
                <button type="submit" disabled={saving()}>
                  {saving() ? 'Saving...' : 'Save'}
                </button>
              </div>
              <label>
                Series
                <input
                  type="text"
                  value={form().series ?? ''}
                  onInput={(e) => setField('series', e.currentTarget.value || null)}
                />
              </label>
              <label>
                Issue #
                <input
                  type="text"
                  value={form().issue_number ?? ''}
                  onInput={(e) => setField('issue_number', e.currentTarget.value || null)}
                />
              </label>
              <label>
                Year
                <input
                  type="number"
                  value={form().year ?? ''}
                  onInput={(e) =>
                    setField('year', e.currentTarget.value ? Number(e.currentTarget.value) : null)
                  }
                />
              </label>
              <label>
                Publisher
                <input
                  type="text"
                  value={form().publisher ?? ''}
                  onInput={(e) => setField('publisher', e.currentTarget.value || null)}
                />
              </label>
              <label>
                Language
                <input
                  type="text"
                  value={form().language ?? ''}
                  onInput={(e) => setField('language', e.currentTarget.value || null)}
                />
              </label>
              <label>
                Condition
                <input
                  type="text"
                  value={form().condition_grade ?? ''}
                  onInput={(e) => setField('condition_grade', e.currentTarget.value || null)}
                />
              </label>
              <label>
                Numeric grade (0.5–10.0)
                <input
                  type="number"
                  step="0.1"
                  min="0.5"
                  max="10"
                  placeholder="e.g. 8.0"
                  value={form().numeric_grade ?? ''}
                  onInput={(e) =>
                    setField('numeric_grade', e.currentTarget.value ? Number(e.currentTarget.value) : null)
                  }
                />
              </label>
              <label>
                Confidence
                <select
                  value={form().confidence ?? ''}
                  onChange={(e) => setField('confidence', e.currentTarget.value || null)}
                >
                  <option value="">-</option>
                  <option value="high">high</option>
                  <option value="medium">medium</option>
                  <option value="low">low</option>
                </select>
              </label>
              <label>
                Storage location
                <input
                  type="text"
                  placeholder="e.g. Longbox 3, Row B"
                  value={form().storage_location ?? ''}
                  onInput={(e) => setField('storage_location', e.currentTarget.value || null)}
                />
              </label>
              <label>
                Notes
                <textarea
                  value={form().notes ?? ''}
                  onInput={(e) => setField('notes', e.currentTarget.value || null)}
                />
              </label>

              <div class="ebay-actions">
                <h3>eBay</h3>
                <a href={ebaySoldSearchUrl(c())} target="_blank" rel="noreferrer" class="secondary-link">
                  Check sold listings on eBay &rarr;
                </a>

                <p class="suggested-listing-label">Suggested listing title</p>
                <div class="copyable">
                  <input type="text" readonly value={suggestedListingTitle(c())} />
                  <button type="button" onClick={() => copy(suggestedListingTitle(c()))}>
                    Copy
                  </button>
                </div>

                <p class="suggested-listing-label">Suggested description</p>
                <div class="copyable">
                  <textarea readonly value={suggestedListingDescription(c())} />
                  <button type="button" onClick={() => copy(suggestedListingDescription(c()))}>
                    Copy
                  </button>
                </div>

                <a href="https://www.ebay.com/sl/sell" target="_blank" rel="noreferrer" class="secondary-link">
                  Open eBay to list this item &rarr;
                </a>
              </div>

              <fieldset class="for-sale-fieldset">
                <legend>For sale</legend>
                <label class="checkbox-label">
                  <input
                    type="checkbox"
                    checked={form().for_sale ?? false}
                    onChange={(e) => setField('for_sale', e.currentTarget.checked)}
                  />
                  List on public for-sale page
                </label>
                <label>
                  Asking price (USD)
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    value={form().asking_price ?? ''}
                    onInput={(e) =>
                      setField('asking_price', e.currentTarget.value ? Number(e.currentTarget.value) : null)
                    }
                  />
                </label>
                <label>
                  eBay listing status
                  <select
                    value={form().ebay_listing_status ?? ''}
                    onChange={(e) => setField('ebay_listing_status', e.currentTarget.value || null)}
                  >
                    <option value="">Not listed</option>
                    <option value="draft">Draft</option>
                    <option value="listed">Listed</option>
                    <option value="sold">Sold</option>
                  </select>
                </label>
                <label>
                  eBay listing URL
                  <input
                    type="url"
                    placeholder="https://www.ebay.com/itm/..."
                    value={form().ebay_listing_url ?? ''}
                    onInput={(e) => setField('ebay_listing_url', e.currentTarget.value || null)}
                  />
                </label>
              </fieldset>
            </form>

            <p class="meta">
              Imported {c().imported_at} &middot; original file: {c().original_filename}
            </p>
          </div>

            <Show when={fullscreen() && c().image_url}>
              <Lightbox
                imageUrl={c().image_url ?? ''}
                alt={`${c().series ?? 'Unknown'} #${c().issue_number ?? '?'}`}
                onClose={() => setFullscreen(false)}
              />
            </Show>

            <Show when={confirmingDelete()}>
              <ConfirmModal
                title="Delete this comic?"
                message={`This permanently deletes ${c().series ?? 'this comic'} #${c().issue_number ?? '?'} and its image. This cannot be undone.`}
                confirmLabel="Delete"
                confirming={deleting()}
                onConfirm={handleDelete}
                onCancel={() => setConfirmingDelete(false)}
              />
            </Show>

            <Show when={cropping() && c().image_url}>
              <CropModal
                imageUrl={c().image_url ?? ''}
                suggestion={suggestionFrom(c())}
                onCancel={() => setCropping(false)}
                onApply={handleApplyCrop}
              />
            </Show>
            <Show when={cropSaving()}>
              <p class="saving-overlay">Saving crop...</p>
            </Show>
            <Show when={cropError()}>
              <p class="error">{cropError()}</p>
            </Show>
          </div>
          </>
        )}
      </Show>
    </div>
  )
}
