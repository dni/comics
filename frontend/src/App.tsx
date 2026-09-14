import { Route, Router } from '@solidjs/router'
import { AuthProvider } from './auth/authContext'
import RequireAuth from './auth/RequireAuth'
import AppShell from './components/AppShell'
import UpdatePrompt from './components/UpdatePrompt'
import Library from './routes/Library'
import ComicDetail from './routes/ComicDetail'
import Import from './routes/Import'
import ForSale from './routes/ForSale'
import FailedImports from './routes/FailedImports'

function ProtectedLibrary() {
  return (
    <RequireAuth>
      <AppShell>
        <Library />
      </AppShell>
    </RequireAuth>
  )
}

function ProtectedComicDetail() {
  return (
    <RequireAuth>
      <AppShell>
        <ComicDetail />
      </AppShell>
    </RequireAuth>
  )
}

function ProtectedImport() {
  return (
    <RequireAuth>
      <AppShell>
        <Import />
      </AppShell>
    </RequireAuth>
  )
}

function ProtectedFailedImports() {
  return (
    <RequireAuth>
      <AppShell>
        <FailedImports />
      </AppShell>
    </RequireAuth>
  )
}

function App() {
  return (
    <AuthProvider>
      <UpdatePrompt />
      <Router>
        <Route path="/for-sale" component={ForSale} />
        <Route path="/" component={ProtectedLibrary} />
        <Route path="/comic/:id" component={ProtectedComicDetail} />
        <Route path="/import" component={ProtectedImport} />
        <Route path="/failed" component={ProtectedFailedImports} />
      </Router>
    </AuthProvider>
  )
}

export default App
