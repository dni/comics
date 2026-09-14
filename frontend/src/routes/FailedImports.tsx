import { createResource, createSignal, For, Show } from 'solid-js'
import { A } from '@solidjs/router'
import { listFailed, retryFailed } from '../api'
import ModelSelect from '../components/ModelSelect'
import type { ImportResult } from '../types'

export default function FailedImports() {
  const [failed, { refetch }] = createResource(listFailed)
  const [retrying, setRetrying] = createSignal<number | null>(null)
  const [results, setResults] = createSignal<Record<number, ImportResult>>({})
  const [model, setModel] = createSignal<string | null>(null)

  async function handleRetry(id: number) {
    setRetrying(id)
    try {
      const result = await retryFailed(id, model() ?? undefined)
      setResults((r) => ({ ...r, [id]: result }))
      if (result.status === 'processed') {
        await refetch()
      }
    } catch (err) {
      setResults((r) => ({
        ...r,
        [id]: {
          status: 'failed',
          filename: '',
          comic: null,
          error: err instanceof Error ? err.message : String(err),
        },
      }))
    } finally {
      setRetrying(null)
    }
  }

  return (
    <div>
      <A href="/">&larr; Back to library</A>
      <h1>Failed Imports</h1>
      <label class="model-picker">
        AI model for retries
        <ModelSelect value={model()} onChange={setModel} />
      </label>
      <Show when={!failed.loading} fallback={<p>Loading...</p>}>
        <Show when={failed() && failed()!.length > 0} fallback={<p>No failed imports. 🎉</p>}>
          <ul class="failed-list">
            <For each={failed()}>
              {(item) => {
                const result = () => results()[item.id]
                return (
                  <li class="failed-item">
                    <div class="failed-item-main">
                      <span class="failed-filename">{item.original_filename}</span>
                      <span class="failed-error">{item.error_message}</span>
                    </div>
                    <div class="failed-item-actions">
                      <button
                        type="button"
                        class="secondary"
                        disabled={retrying() === item.id}
                        onClick={() => handleRetry(item.id)}
                      >
                        {retrying() === item.id ? 'Retrying...' : 'Retry'}
                      </button>
                      <Show when={result()}>
                        <Show when={result()!.status === 'processed'}>
                          <span class="saved">
                            Success —{' '}
                            <A href={`/comic/${result()!.comic?.id}`}>
                              {result()!.comic?.series} #{result()!.comic?.issue_number}
                            </A>
                          </span>
                        </Show>
                        <Show when={result()!.status === 'failed'}>
                          <span class="error">{result()!.error}</span>
                        </Show>
                      </Show>
                    </div>
                  </li>
                )
              }}
            </For>
          </ul>
        </Show>
      </Show>
    </div>
  )
}
