import { createSignal, For } from 'solid-js'
import { A } from '@solidjs/router'
import { describeError, importComic, isNetworkError } from '../api'
import ModelSelect from '../components/ModelSelect'
import type { ImportResult } from '../types'

interface QueueItem {
  id: number
  file: File
  status: 'pending' | 'uploading' | 'done' | 'error'
  result?: ImportResult
  error?: string
}

let nextId = 0

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

const MAX_ATTEMPTS = 3

export default function Import() {
  const [queue, setQueue] = createSignal<QueueItem[]>([])
  const [isDragging, setIsDragging] = createSignal(false)
  const [model, setModel] = createSignal<string | null>(null)
  let draining = false
  let takePhotoInput: HTMLInputElement | undefined

  function addFiles(fileList: FileList | null) {
    if (!fileList || fileList.length === 0) return
    const items: QueueItem[] = Array.from(fileList).map((file) => ({
      id: nextId++,
      file,
      status: 'pending',
    }))
    setQueue((q) => [...q, ...items])
    void drainQueue()
  }

  // Uploads run through one shared loop, not one per addFiles() call - each
  // import triggers a slow server-side pipeline (ImageMagick + a multi-second
  // Claude vision call), so firing off several photos back-to-back must not
  // start several uploads in parallel: on a mobile connection, concurrent
  // multipart uploads racing for bandwidth is a common cause of "failed to
  // fetch". This guard makes sure only one upload is ever in flight, and any
  // photo added mid-drain is picked up by the already-running loop.
  async function drainQueue() {
    if (draining) return
    draining = true
    try {
      for (;;) {
        const next = queue().find((i) => i.status === 'pending')
        if (!next) break
        await uploadWithRetry(next)
      }
    } finally {
      draining = false
    }
  }

  async function uploadWithRetry(item: QueueItem) {
    for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
      setQueue((q) =>
        q.map((i) => (i.id === item.id ? { ...i, status: 'uploading', error: undefined } : i)),
      )
      try {
        const result = await importComic(item.file, model() ?? undefined)
        setQueue((q) => q.map((i) => (i.id === item.id ? { ...i, status: 'done', result } : i)))
        return
      } catch (err) {
        // transient network blips are retried automatically a couple of times
        // before we bother the user - anything else fails immediately, since
        // retrying a real server error just wastes their time
        if (isNetworkError(err) && attempt < MAX_ATTEMPTS) {
          await sleep(1000 * attempt)
          continue
        }
        setQueue((q) =>
          q.map((i) => (i.id === item.id ? { ...i, status: 'error', error: describeError(err) } : i)),
        )
        return
      }
    }
  }

  function retryItem(item: QueueItem) {
    setQueue((q) =>
      q.map((i) => (i.id === item.id ? { ...i, status: 'pending', error: undefined } : i)),
    )
    void drainQueue()
  }

  function handleDrop(e: DragEvent) {
    e.preventDefault()
    setIsDragging(false)
    addFiles(e.dataTransfer?.files ?? null)
  }

  return (
    <div>
      <A href="/">&larr; Back to library</A>
      <h1>Import Comics</h1>

      <label class="model-picker">
        AI model
        <ModelSelect value={model()} onChange={setModel} />
      </label>

      <div
        class="dropzone"
        classList={{ dragging: isDragging() }}
        onDragOver={(e) => {
          e.preventDefault()
          setIsDragging(true)
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
      >
        <p>Drag comic photos here, or</p>
        <div class="file-picker-row">
          <label class="file-picker">
            Take photo
            <input
              ref={takePhotoInput}
              type="file"
              accept="image/*"
              capture="environment"
              onChange={(e) => {
                addFiles(e.currentTarget.files)
                e.currentTarget.value = ''
                // scanning several covers in a row is the common case - jump
                // straight back into the camera instead of making the user
                // tap "Take photo" again after every single shot. The upload
                // itself runs in the background via drainQueue(), so this
                // doesn't wait on it.
                setTimeout(() => takePhotoInput?.click(), 0)
              }}
            />
          </label>
          <label class="file-picker secondary">
            Choose files
            <input
              type="file"
              accept="image/*"
              multiple
              onChange={(e) => {
                addFiles(e.currentTarget.files)
                e.currentTarget.value = ''
              }}
            />
          </label>
        </div>
      </div>

      <ul class="import-queue">
        <For each={[...queue()].reverse()}>
          {(item) => (
            <li class="import-item" classList={{ [`status-${item.status}`]: true }}>
              <span class="import-filename">{item.file.name}</span>
              {item.status === 'pending' && <span class="import-status">Queued</span>}
              {item.status === 'uploading' && <span class="import-status">Processing...</span>}
              {item.status === 'done' && item.result && (
                <span class="import-status">
                  {item.result.status === 'skipped' && 'Already imported'}
                  {item.result.status === 'failed' && (
                    <span class="error">{item.result.error}</span>
                  )}
                  {item.result.status === 'processed' && (
                    <>
                      {item.result.comic?.series ?? 'Unknown'} #{item.result.comic?.issue_number ?? '?'}
                    </>
                  )}
                  {item.result.comic && (
                    <>
                      {' '}
                      <A href={`/comic/${item.result.comic.id}`}>(view)</A>
                    </>
                  )}
                  {item.result.comic && item.result.comic.duplicate_of.length > 0 && (
                    <div class="import-duplicate-warning">
                      Already in catalog:{' '}
                      <For each={item.result.comic.duplicate_of}>
                        {(dup, i) => (
                          <>
                            {i() > 0 && ', '}
                            <A href={`/comic/${dup.id}`}>
                              {dup.series} #{dup.issue_number}
                            </A>
                            {(dup.condition_grade || dup.numeric_grade != null) && (
                              <span>
                                {' '}
                                (
                                {[dup.condition_grade, dup.numeric_grade != null ? dup.numeric_grade.toFixed(1) : null]
                                  .filter(Boolean)
                                  .join(' ')}
                                )
                              </span>
                            )}
                          </>
                        )}
                      </For>
                    </div>
                  )}
                </span>
              )}
              {item.status === 'error' && (
                <span class="import-status error import-error-row">
                  {item.error}
                  <button type="button" class="secondary" onClick={() => retryItem(item)}>
                    Retry
                  </button>
                </span>
              )}
            </li>
          )}
        </For>
      </ul>
    </div>
  )
}
