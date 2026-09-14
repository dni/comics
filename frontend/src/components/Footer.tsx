export default function Footer() {
  const version = import.meta.env.VITE_APP_VERSION || 'dev'
  return (
    <footer class="app-footer">
      <span>Comic Library {version}</span>
    </footer>
  )
}
