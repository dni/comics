import { createSignal, onCleanup, onMount } from 'solid-js'

interface LightboxProps {
  imageUrl: string
  alt?: string
  onClose: () => void
}

const MIN_SCALE = 1
const MAX_SCALE = 4
const CLICK_ZOOM_SCALE = 2.5
const DRAG_THRESHOLD = 5

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value))
}

export default function Lightbox(props: LightboxProps) {
  let imgRef: HTMLImageElement | undefined
  // static (untransformed) screen center of the image - captured once the
  // image has loaded and laid out, while scale/pan are still identity.
  // transforms don't affect layout, so this stays valid for the lightbox's
  // whole lifetime and anchors the zoom-toward-cursor/click math below.
  let center = { x: 0, y: 0 }

  const [scale, setScale] = createSignal(1)
  const [panX, setPanX] = createSignal(0)
  const [panY, setPanY] = createSignal(0)

  let dragging = false
  let dragMoved = false
  let dragStart = { x: 0, y: 0, panX: 0, panY: 0 }

  function zoomToward(clientX: number, clientY: number, nextScale: number) {
    const s0 = scale()
    const s1 = clamp(nextScale, MIN_SCALE, MAX_SCALE)
    const qx = clientX - center.x
    const qy = clientY - center.y

    if (s1 <= MIN_SCALE) {
      setScale(1)
      setPanX(0)
      setPanY(0)
      return
    }

    // keep the image point currently under (clientX, clientY) fixed on screen
    const dx = (qx - panX()) / s0
    const dy = (qy - panY()) / s0
    setScale(s1)
    setPanX(qx - s1 * dx)
    setPanY(qy - s1 * dy)
  }

  function handleWheel(e: WheelEvent) {
    e.preventDefault()
    const factor = e.deltaY < 0 ? 1.2 : 1 / 1.2
    zoomToward(e.clientX, e.clientY, scale() * factor)
  }

  function handleImageClick(e: MouseEvent) {
    e.stopPropagation()
    if (dragMoved) {
      dragMoved = false
      return
    }
    zoomToward(e.clientX, e.clientY, scale() > 1 ? 1 : CLICK_ZOOM_SCALE)
  }

  function handlePointerDown(e: PointerEvent) {
    if (scale() <= 1) return
    dragging = true
    dragMoved = false
    dragStart = { x: e.clientX, y: e.clientY, panX: panX(), panY: panY() }
    imgRef?.setPointerCapture(e.pointerId)
  }

  function handlePointerMove(e: PointerEvent) {
    if (!dragging) return
    const dx = e.clientX - dragStart.x
    const dy = e.clientY - dragStart.y
    if (Math.abs(dx) > DRAG_THRESHOLD || Math.abs(dy) > DRAG_THRESHOLD) dragMoved = true
    setPanX(dragStart.panX + dx)
    setPanY(dragStart.panY + dy)
  }

  function handlePointerUp() {
    dragging = false
  }

  function handleImageLoad() {
    if (!imgRef) return
    const rect = imgRef.getBoundingClientRect()
    center = { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 }
  }

  function zoomIn(e: MouseEvent) {
    e.stopPropagation()
    zoomToward(center.x, center.y, scale() * 1.5)
  }

  function zoomOut(e: MouseEvent) {
    e.stopPropagation()
    zoomToward(center.x, center.y, scale() / 1.5)
  }

  function handleKeyDown(e: KeyboardEvent) {
    if (e.key === 'Escape') props.onClose()
  }

  onMount(() => {
    document.addEventListener('keydown', handleKeyDown)
  })
  onCleanup(() => {
    document.removeEventListener('keydown', handleKeyDown)
  })

  return (
    <div class="lightbox-overlay" onClick={props.onClose} onWheel={handleWheel}>
      <div class="lightbox-toolbar" onClick={(e) => e.stopPropagation()}>
        <button type="button" onClick={zoomOut} disabled={scale() <= MIN_SCALE} aria-label="Zoom out">
          −
        </button>
        <span class="lightbox-zoom-level">{Math.round(scale() * 100)}%</span>
        <button type="button" onClick={zoomIn} disabled={scale() >= MAX_SCALE} aria-label="Zoom in">
          +
        </button>
        <button type="button" onClick={props.onClose} aria-label="Close">
          ✕
        </button>
      </div>
      <img
        ref={imgRef}
        src={props.imageUrl}
        alt={props.alt ?? ''}
        class="lightbox-image"
        classList={{ 'lightbox-image-zoomed': scale() > 1 }}
        style={{ transform: `translate(${panX()}px, ${panY()}px) scale(${scale()})` }}
        onLoad={handleImageLoad}
        onClick={handleImageClick}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerLeave={handlePointerUp}
      />
    </div>
  )
}
