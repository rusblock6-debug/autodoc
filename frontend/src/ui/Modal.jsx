import React, { useEffect } from 'react'
import { CloseIcon } from './icons'
import IconButton from './IconButton'

/**
 * Базовое модальное окно с оверлеем, закрытием по Esc и клику по фону.
 */
function Modal({ open, onClose, title, children, footer, maxWidth = '560px' }) {
  useEffect(() => {
    if (!open) return
    const onKey = (e) => { if (e.key === 'Escape') onClose?.() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 animate-fade-in"
      onMouseDown={onClose}
    >
      <div
        className="flex max-h-[90vh] w-full flex-col overflow-hidden rounded-xl bg-white shadow-xl animate-slide-up"
        style={{ maxWidth }}
        onMouseDown={(e) => e.stopPropagation()}
      >
        {title && (
          <div className="flex items-center justify-between border-b border-gray-200 px-5 py-4">
            <h2 className="font-heading text-base font-semibold text-gray-800">{title}</h2>
            <IconButton icon={CloseIcon} label="Закрыть" onClick={onClose} />
          </div>
        )}
        <div className="flex-1 overflow-y-auto px-5 py-5">{children}</div>
        {footer && (
          <div className="flex justify-end gap-2 border-t border-gray-200 px-5 py-4">{footer}</div>
        )}
      </div>
    </div>
  )
}

export default Modal
