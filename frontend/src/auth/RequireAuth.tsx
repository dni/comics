import { Show, type ParentComponent } from 'solid-js'
import { useAuth } from './authContext'
import Setup from '../routes/Setup'
import Login from '../routes/Login'

const RequireAuth: ParentComponent = (props) => {
  const auth = useAuth()

  return (
    <Show when={auth.state() === 'authenticated'} fallback={<Gate />}>
      {props.children}
    </Show>
  )
}

function Gate() {
  const auth = useAuth()

  return (
    <Show when={auth.state() !== 'loading'} fallback={<p>Loading...</p>}>
      <Show
        when={auth.state() === 'needs-setup'}
        fallback={<Login onSuccess={() => auth.refresh()} />}
      >
        <Setup onSuccess={() => auth.refresh()} />
      </Show>
    </Show>
  )
}

export default RequireAuth
