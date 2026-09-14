import { createResource, createSignal, For, Show } from 'solid-js'
import { A } from '@solidjs/router'
import { listComics } from '../api'
import type { Comic } from '../types'

const SORT_OPTIONS: { value: string; label: string }[] = [
  { value: 'updated_at', label: 'Last updated' },
  { value: 'series', label: 'Series' },
  { value: 'issue_number', label: 'Issue' },
  { value: 'year', label: 'Year' },
  { value: 'confidence', label: 'Confidence' },
  { value: 'imported_at', label: 'Imported' },
]

export default function Library() {
  const [query, setQuery] = createSignal('')
  const [sort, setSort] = createSignal('updated_at')
  const [order, setOrder] = createSignal<'asc' | 'desc'>('desc')
  const [confidence, setConfidence] = createSignal('')

  const [comics] = createResource(
    () => ({ q: query(), sort: sort(), order: order(), confidence: confidence() }),
    (params) => listComics(params),
  )

  return (
    <div>
      <div class="page-header">
        <h1>Comic Library</h1>
        <A href="/import" class="import-link">
          + Import comics
        </A>
      </div>
      <div class="toolbar">
        <input
          type="text"
          placeholder="Search series, issue, publisher..."
          value={query()}
          onInput={(e) => setQuery(e.currentTarget.value)}
        />
        <select value={sort()} onChange={(e) => setSort(e.currentTarget.value)}>
          <For each={SORT_OPTIONS}>{(opt) => <option value={opt.value}>{opt.label}</option>}</For>
        </select>
        <select value={order()} onChange={(e) => setOrder(e.currentTarget.value as 'asc' | 'desc')}>
          <option value="asc">Asc</option>
          <option value="desc">Desc</option>
        </select>
        <select value={confidence()} onChange={(e) => setConfidence(e.currentTarget.value)}>
          <option value="">All confidence</option>
          <option value="high">High confidence</option>
          <option value="medium">Medium confidence</option>
          <option value="low">Low confidence</option>
        </select>
      </div>

      <Show when={!comics.loading} fallback={<p>Loading...</p>}>
        <Show when={!comics.error} fallback={<p class="error">Failed to load comics.</p>}>
          <p class="count">{comics()?.length ?? 0} comic(s)</p>
          <div class="grid">
            <For each={comics()}>{(comic) => <ComicCard comic={comic} />}</For>
          </div>
        </Show>
      </Show>
    </div>
  )
}

function ComicCard(props: { comic: Comic }) {
  return (
    <A href={`/comic/${props.comic.id}`} class="card">
      <Show when={props.comic.image_url}>
        <img src={props.comic.image_url ?? ''} loading="lazy" />
      </Show>
      <div class="card-title">
        {props.comic.series ?? 'Unknown Series'} #{props.comic.issue_number ?? '?'}
      </div>
      <div class="card-sub">
        {props.comic.year ?? ''} {props.comic.confidence ? `· ${props.comic.confidence}` : ''}
      </div>
      <Show when={props.comic.numeric_grade != null}>
        <div class="card-grade-badge">{props.comic.numeric_grade!.toFixed(1)}</div>
      </Show>
    </A>
  )
}
