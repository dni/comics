import { createEffect, createResource, For, Show } from 'solid-js'
import { listModels } from '../api'

interface ModelSelectProps {
  value: string | null
  onChange: (model: string) => void
  disabled?: boolean
}

export default function ModelSelect(props: ModelSelectProps) {
  const [models] = createResource(listModels)

  createEffect(() => {
    const m = models()
    if (m && !props.value) props.onChange(m.default)
  })

  return (
    <Show when={models()}>
      {(m) => (
        <select
          class="model-select"
          value={props.value ?? m().default}
          disabled={props.disabled}
          onChange={(e) => props.onChange(e.currentTarget.value)}
        >
          <For each={m().models}>{(model) => <option value={model}>{model}</option>}</For>
        </select>
      )}
    </Show>
  )
}
