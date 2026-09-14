interface ConfirmModalProps {
  title: string
  message: string
  confirmLabel?: string
  confirming?: boolean
  onConfirm: () => void
  onCancel: () => void
}

export default function ConfirmModal(props: ConfirmModalProps) {
  return (
    <div class="modal-overlay" onClick={props.onCancel}>
      <div class="modal-content confirm-modal" onClick={(e) => e.stopPropagation()}>
        <h3>{props.title}</h3>
        <p>{props.message}</p>
        <div class="confirm-modal-actions">
          <button type="button" class="secondary" onClick={props.onCancel} disabled={props.confirming}>
            Cancel
          </button>
          <button type="button" class="danger" onClick={props.onConfirm} disabled={props.confirming}>
            {props.confirming ? 'Working...' : (props.confirmLabel ?? 'Confirm')}
          </button>
        </div>
      </div>
    </div>
  )
}
