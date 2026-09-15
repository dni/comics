import { createSignal, type ParentComponent } from 'solid-js'
import { A } from '@solidjs/router'
import { useAuth } from '../auth/authContext'

const AppShell: ParentComponent = (props) => {
  const auth = useAuth()
  const [menuOpen, setMenuOpen] = createSignal(false)

  function closeMenu() {
    setMenuOpen(false)
  }

  return (
    <div>
      <div class="topbar">
        <A href="/" class="topbar-brand">
          Library
        </A>
        <div class="topbar-spacer" />
        <nav class="topbar-links" classList={{ open: menuOpen() }}>
          <A href="/failed" onClick={closeMenu}>
            Failed imports
          </A>
          <a href="/api/export/csv" onClick={closeMenu}>
            Export CSV
          </a>
          <a href="/api/export/backup" onClick={closeMenu}>
            Download backup
          </a>
          <A href="/for-sale" target="_blank" onClick={closeMenu}>
            Public for-sale page
          </A>
          <button
            type="button"
            class="secondary"
            onClick={() => {
              closeMenu()
              auth.logout()
            }}
          >
            Log out
          </button>
        </nav>
        <button
          type="button"
          class="topbar-burger"
          aria-label="Toggle menu"
          aria-expanded={menuOpen()}
          onClick={() => setMenuOpen((o) => !o)}
        >
          <span />
          <span />
          <span />
        </button>
      </div>
      {props.children}
    </div>
  )
}

export default AppShell
