import { createSignal, For } from 'solid-js'
import { A } from '@solidjs/router'
import { importComic } from '../api'
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

export default function Import() {
  const [queue, setQueue] = createSignal<QueueItem[]>([])
  const [isDragging, setIsDragging] = createSignal(false)
  const [model, setModel] = createSignal<string | null>(null)

  function addFiles(fileList: FileList | null) {
    if (!fileList || fileList.length === 0) return
    const items: QueueItem[] = Array.from(fileList).map((file) => ({
      id: nextId++,
      file,
      status: 'pending',
    }))
    setQueue((q) => [...q, ...items])
    void processQueue(items)
  }

  async function processQueue(items: QueueItem[]) {
    for (const item of items) {
      setQueue((q) => q.map((i) => (i.id === item.id ? { ...i, status: 'uploading' } : i)))
      try {
        const result = await importComic(item.file, model() ?? undefined)
        setQueue((q) => q.map((i) => (i.id === item.id ? { ...i, status: 'done', result } : i)))
      } catch (err) {
        setQueue((q) =>
          q.map((i) =>
            i.id === item.id
              ? { ...i, status: 'error', error: err instanceof Error ? err.message : String(err) }
              : i,
          ),
        )
      }
    }
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
              type="file"
              accept="image/*"
              capture="environment"
              onChange={(e) => {
                addFiles(e.currentTarget.files)
                e.currentTarget.value = ''
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
        <For each={queue()}>
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
              {item.status === 'error' && <span class="import-status error">{item.error}</span>}
            </li>
          )}
        </For>
      </ul>
    </div>
  )
}
