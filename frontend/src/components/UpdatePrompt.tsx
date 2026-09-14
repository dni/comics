import { Show } from 'solid-js'
import { useRegisterSW } from 'virtual:pwa-register/solid'

export default function UpdatePrompt() {
  const { needRefresh, offlineReady, updateServiceWorker } = useRegisterSW({
    onRegisterError: (err) => console.error('Service worker registration failed', err),
  })
  const [needsRefresh, setNeedsRefresh] = needRefresh
  const [isOfflineReady, setOfflineReady] = offlineReady

  function dismiss() {
    setNeedsRefresh(false)
    setOfflineReady(false)
  }

  return (
    <Show when={needsRefresh() || isOfflineReady()}>
      <div class="update-toast">
        <Show
          when={needsRefresh()}
          fallback={<span>App is ready to work offline.</span>}
        >
          <span>
            A new version is available. Refreshing will reload the app and replace the cached
            version — any unsaved edits will be lost.
          </span>
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
