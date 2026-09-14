import { onCleanup, onMount } from 'solid-js'
import Cropper from 'cropperjs'
import 'cropperjs/dist/cropper.css'

export interface CropSuggestion {
  rotation: number
  left: number
  top: number
  width: number
  height: number
}

interface CropModalProps {
  imageUrl: string
  suggestion?: CropSuggestion | null
  onCancel: () => void
  onApply: (blob: Blob) => void
}

export default function CropModal(props: CropModalProps) {
  let imgRef: HTMLImageElement | undefined
  let cropper: Cropper | undefined

  function applySuggestion() {
    if (!cropper || !props.suggestion) return
    const { naturalWidth, naturalHeight } = cropper.getImageData()
    const { rotation, left, top, width, height } = props.suggestion
    cropper.setData({
      rotate: rotation,
      x: left * naturalWidth,
      y: top * naturalHeight,
      width: width * naturalWidth,
      height: height * naturalHeight,
    })
  }

  onMount(() => {
    if (!imgRef) return
    cropper = new Cropper(imgRef, {
      viewMode: 1,
      dragMode: 'move',
      autoCropArea: 1,
      rotatable: true,
      scalable: false,
      zoomable: true,
      responsive: true,
      background: false,
      ready: () => applySuggestion(),
    })
  })

  onCleanup(() => {
    cropper?.destroy()
  })

  function rotate(deg: number) {
    cropper?.rotate(deg)
  }

  function reset() {
    cropper?.reset()
  }

  function apply() {
    const canvas = cropper?.getCroppedCanvas({ imageSmoothingQuality: 'high' })
    if (!canvas) return
    canvas.toBlob(
      (blob) => {
        if (blob) props.onApply(blob)
      },
      'image/jpeg',
      0.92,
    )
  }

  return (
    <div class="modal-overlay" onClick={props.onCancel}>
      <div class="modal-content" onClick={(e) => e.stopPropagation()}>
        {props.suggestion && (
          <p class="crop-hint">Pre-filled with Claude's suggested crop — adjust as needed.</p>
        )}
        <div class="cropper-viewport">
          <img ref={imgRef} src={props.imageUrl} crossorigin="anonymous" />
        </div>
        <div class="cropper-toolbar">
          <button type="button" onClick={() => rotate(-90)}>
            ↺ Rotate left
          </button>
          <button type="button" onClick={() => rotate(90)}>
            ↻ Rotate right
          </button>
          {props.suggestion && (
            <button type="button" onClick={applySuggestion}>
              Use suggestion
            </button>
          )}
          <button type="button" onClick={reset}>
            Reset
          </button>
          <div class="cropper-toolbar-spacer" />
          <button type="button" class="secondary" onClick={props.onCancel}>
            Cancel
          </button>
          <button type="button" class="primary" onClick={apply}>
            Apply crop
          </button>
        </div>
      </div>
    </div>
  )
}
