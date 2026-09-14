import type { ParentComponent } from 'solid-js'
import { A } from '@solidjs/router'
import { useAuth } from '../auth/authContext'

const AppShell: ParentComponent = (props) => {
  const auth = useAuth()

  return (
    <div>
      <div class="topbar">
        <span class="topbar-user">{auth.username()}</span>
        <div class="topbar-spacer" />
        <A href="/failed">Failed imports</A>
        <a href="/api/export/csv">Export CSV</a>
        <a href="/api/export/backup">Download backup</a>
        <A href="/for-sale" target="_blank">
          Public for-sale page
        </A>
        <button type="button" class="secondary" onClick={() => auth.logout()}>
          Log out
        </button>
      </div>
      {props.children}
    </div>
  )
}

export default AppShell
