import { createSignal } from 'solid-js'
import { login } from '../api'

export default function Login(props: { onSuccess: () => void }) {
  const [username, setUsername] = createSignal('')
  const [password, setPassword] = createSignal('')
  const [error, setError] = createSignal<string | null>(null)
  const [saving, setSaving] = createSignal(false)

  async function handleSubmit(e: Event) {
    e.preventDefault()
    setError(null)
    setSaving(true)
    try {
      await login(username(), password())
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
        <h1>Log in</h1>
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
            autocomplete="current-password"
            value={password()}
            onInput={(e) => setPassword(e.currentTarget.value)}
            required
          />
        </label>
        <button type="submit" class="primary" disabled={saving()}>
          {saving() ? 'Logging in...' : 'Log in'}
        </button>
        {error() && <p class="error">{error()}</p>}
      </form>
    </div>
  )
}
