import { createContext, createSignal, onMount, useContext, type ParentComponent } from 'solid-js'
import { getAuthStatus, getMe, logout as apiLogout } from '../api'

export type AuthState = 'loading' | 'needs-setup' | 'needs-login' | 'authenticated'

interface AuthContextValue {
  state: () => AuthState
  username: () => string | null
  refresh: () => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue>()

export const AuthProvider: ParentComponent = (props) => {
  const [state, setState] = createSignal<AuthState>('loading')
  const [username, setUsername] = createSignal<string | null>(null)

  async function refresh() {
    setState('loading')
    try {
      const status = await getAuthStatus()
      if (!status.has_admin) {
        setState('needs-setup')
        return
      }
    } catch {
      setState('needs-login')
      return
    }
    try {
      const me = await getMe()
      setUsername(me.username)
      setState('authenticated')
    } catch {
      setUsername(null)
      setState('needs-login')
    }
  }

  async function logout() {
    await apiLogout()
    setUsername(null)
    setState('needs-login')
  }

  onMount(refresh)

  return <AuthContext.Provider value={{ state, username, refresh, logout }}>{props.children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
