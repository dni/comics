import { createSignal, onCleanup, onMount } from 'solid-js'
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

  const [rotation, setRotation] = createSignal(0)

  function applySuggestion() {
    if (!cropper || !props.suggestion) return
    const { naturalWidth, naturalHeight } = cropper.getImageData()
    const { rotation: rot, left, top, width, height } = props.suggestion

    // Claude measures left/top/width/height as fractions of the image's bounding
    // box AFTER rotating by `rot` (see vision.py's system prompt) - not the
    // original, unrotated naturalWidth/naturalHeight. Rotating a WxH rectangle by
    // an angle grows its bounding box to roughly W*|cos| + H*|sin| by
    // W*|sin| + H*|cos|, so for any non-zero rotation those two frames have
    // different dimensions. Cropper's setData x/y/width/height are documented as
    // "rotate the image, then crop" (i.e. also in the rotated frame), so we must
    // scale by the rotated bounding box, not the original naturalWidth/Height,
    // or the crop box lands in the wrong place whenever a rotation is suggested.
    const radians = (rot * Math.PI) / 180
    const cos = Math.abs(Math.cos(radians))
    const sin = Math.abs(Math.sin(radians))
    const rotatedWidth = naturalWidth * cos + naturalHeight * sin
    const rotatedHeight = naturalWidth * sin + naturalHeight * cos

    cropper.setData({
      rotate: rot,
      x: left * rotatedWidth,
      y: top * rotatedHeight,
      width: width * rotatedWidth,
      height: height * rotatedHeight,
    })
    setRotation(rot)
  }

  function syncRotation() {
    if (!cropper) return
    setRotation(cropper.getData().rotate)
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
      crop: () => syncRotation(),
    })
  })

  onCleanup(() => {
    cropper?.destroy()
  })

  function rotate(deg: number) {
    cropper?.rotate(deg)
    syncRotation()
  }

  function rotateTo(deg: number) {
    cropper?.rotateTo(deg)
    setRotation(deg)
  }

  function reset() {
    cropper?.reset()
    setRotation(0)
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
        <div class="cropper-rotate-row">
          <button type="button" onClick={() => rotate(-90)}>
            ↺ Rotate left
          </button>
          <input
            type="range"
            min="-180"
            max="180"
            step="1"
            value={rotation()}
            onInput={(e) => rotateTo(Number(e.currentTarget.value))}
            class="cropper-rotate-slider"
          />
          <input
            type="number"
            min="-180"
            max="180"
            step="1"
            value={Math.round(rotation())}
            onInput={(e) => rotateTo(Number(e.currentTarget.value) || 0)}
            class="cropper-rotate-degrees"
          />
          <span class="cropper-rotate-unit">&deg;</span>
          <button type="button" onClick={() => rotate(90)}>
            ↻ Rotate right
          </button>
        </div>
        <div class="cropper-toolbar">
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
