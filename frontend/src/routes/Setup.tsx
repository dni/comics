import { createSignal } from 'solid-js'
import { setupAdmin } from '../api'

export default function Setup(props: { onSuccess: () => void }) {
  const [username, setUsername] = createSignal('')
  const [password, setPassword] = createSignal('')
  const [confirmPassword, setConfirmPassword] = createSignal('')
  const [error, setError] = createSignal<string | null>(null)
  const [saving, setSaving] = createSignal(false)

  async function handleSubmit(e: Event) {
    e.preventDefault()
    setError(null)
    if (password() !== confirmPassword()) {
      setError('Passwords do not match.')
      return
    }
    setSaving(true)
    try {
      await setupAdmin(username(), password())
      props.onSuccess()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div class="auth-page">
      <form class="auth-form" onSubmit={handleSubmit}>
        <h1>Set up your comic library</h1>
        <p class="auth-hint">
          Create the admin account for this app. This only happens once, on first launch.
        </p>
        <label>
          Username
          <input
            type="text"
            autocomplete="username"
            value={username()}
            onInput={(e) => setUsername(e.currentTarget.value)}
            required
          />
        </label>
        <label>
          Password
          <input
            type="password"
            autocomplete="new-password"
            value={password()}
            onInput={(e) => setPassword(e.currentTarget.value)}
            required
            minLength={8}
          />
        </label>
        <label>
          Confirm password
          <input
            type="password"
            autocomplete="new-password"
            value={confirmPassword()}
            onInput={(e) => setConfirmPassword(e.currentTarget.value)}
            required
            minLength={8}
          />
        </label>
        <button type="submit" class="primary" disabled={saving()}>
          {saving() ? 'Creating...' : 'Create account'}
        </button>
        {error() && <p class="error">{error()}</p>}
      </form>
    </div>
  )
}
