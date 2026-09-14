import { createResource, For, Show } from 'solid-js'
import { listForSale } from '../api'
import type { PublicComic } from '../types'

export default function ForSale() {
  const [comics] = createResource(listForSale)

  return (
    <div class="for-sale-page">
      <h1>Comics For Sale</h1>
      <Show when={!comics.loading} fallback={<p>Loading...</p>}>
        <Show
          when={comics() && comics()!.length > 0}
          fallback={<p>Nothing listed for sale right now.</p>}
        >
          <div class="grid">
            <For each={comics()}>{(comic) => <ForSaleCard comic={comic} />}</For>
          </div>
        </Show>
      </Show>
    </div>
  )
}

function ForSaleCard(props: { comic: PublicComic }) {
  const c = props.comic
  return (
    <div class="card for-sale-card">
      <Show when={c.image_url}>
        <img src={c.image_url ?? ''} loading="lazy" />
      </Show>
      <div class="card-title">
        {c.series ?? 'Unknown'} #{c.issue_number ?? '?'}
      </div>
      <div class="card-sub">
        {c.year ?? ''} {c.condition_grade ? `· ${c.condition_grade}` : ''}
      </div>
      <Show when={c.asking_price != null}>
        <div class="for-sale-price">${c.asking_price!.toFixed(2)}</div>
      </Show>
      <Show when={c.ebay_listing_url}>
        <a href={c.ebay_listing_url ?? ''} target="_blank" rel="noreferrer" class="ebay-link">
          View on eBay
        </a>
      </Show>
    </div>
  )
}
