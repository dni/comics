import { createSignal, Show } from 'solid-js'
import { useRegisterSW } from 'virtual:pwa-register/solid'

export default function UpdatePrompt() {
  const [registerError, setRegisterError] = createSignal<string | null>(null)
  const { needRefresh, offlineReady, updateServiceWorker } = useRegisterSW({
    onRegisterError: (err) => {
      console.error('Service worker registration failed', err)
      setRegisterError(err instanceof Error ? err.message : String(err))
    },
  })
  const [needsRefresh, setNeedsRefresh] = needRefresh
  const [isOfflineReady, setOfflineReady] = offlineReady

  function dismiss() {
    setNeedsRefresh(false)
    setOfflineReady(false)
    setRegisterError(null)
  }

  return (
    <Show when={needsRefresh() || isOfflineReady() || registerError()}>
      <div class="update-toast">
        <Show
          when={!registerError()}
          fallback={
            <span>
              Couldn't set up offline/update support in this browser ({registerError()}). The app
              still works normally, but automatic update prompts won't show here.
            </span>
          }
        >
          <Show
            when={needsRefresh()}
            fallback={<span>App is ready to work offline.</span>}
          >
            <span>
              A new version is available. Refreshing will reload the app and replace the cached
              version — any unsaved edits will be lost.
            </span>
          </Show>
        </Show>
        <div class="update-toast-actions">
          <Show when={needsRefresh()}>
            <button type="button" class="primary" onClick={() => updateServiceWorker(true)}>
              Refresh now
            </button>
          </Show>
          <button type="button" class="secondary" onClick={dismiss}>
            {needsRefresh() ? 'Later' : 'Dismiss'}
          </button>
        </div>
      </div>
    </Show>
  )
}
