import React, { createContext, useCallback, useContext, useRef, useState } from 'react'
import { CheckIcon, AlertIcon, CloseIcon } from './icons'
import Button from './Button'

const ToastContext = createContext(null)

const TONE_STYLES = {
  success: { bar: 'bg-emerald-500', icon: <CheckIcon size={16} />, ring: 'text-emerald-500' },
  error: { bar: 'bg-red-500', icon: <AlertIcon size={16} />, ring: 'text-red-500' },
  info: { bar: 'bg-brand-500', icon: <AlertIcon size={16} />, ring: 'text-brand-500' },
}

/**
 * Провайдер уведомлений: всплывающие тосты + промис-based confirm-диалог.
 * Заменяет нативные alert()/confirm().
 */
export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const [confirmState, setConfirmState] = useState(null)
  const idRef = useRef(0)

  const remove = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const push = useCallback((message, tone = 'info', timeout = 3500) => {
    const id = ++idRef.current
    setToasts((prev) => [...prev, { id, message, tone }])
    if (timeout) setTimeout(() => remove(id), timeout)
    return id
  }, [remove])

  const toast = {
    success: (m, t) => push(m, 'success', t),
    error: (m, t) => push(m, 'error', t),
    info: (m, t) => push(m, 'info', t),
  }

  const confirm = useCallback((options) => {
    const opts = typeof options === 'string' ? { message: options } : options
    return new Promise((resolve) => {
      setConfirmState({
        ...opts,
        resolve: (val) => { setConfirmState(null); resolve(val) },
      })
    })
  }, [])

  return (
    <ToastContext.Provider value={{ toast, confirm }}>
      {children}

      {/* Стек тостов */}
      <div className="fixed bottom-5 right-5 z-[60] flex flex-col gap-2">
        {toasts.map((t) => {
          const s = TONE_STYLES[t.tone] || TONE_STYLES.info
          return (
            <div
              key={t.id}
              className="flex w-80 items-start gap-3 overflow-hidden rounded-lg bg-white shadow-card-hover ring-1 ring-black/5 animate-slide-up"
            >
              <span className={`w-1 self-stretch ${s.bar}`} />
              <span className={`mt-3 ${s.ring}`}>{s.icon}</span>
              <p className="flex-1 py-3 pr-2 text-sm text-gray-700">{t.message}</p>
              <button
                onClick={() => remove(t.id)}
                className="mt-2 mr-2 rounded p-1 text-gray-400 hover:bg-gray-100"
                aria-label="Закрыть"
              >
                <CloseIcon size={14} />
              </button>
            </div>
          )
        })}
      </div>

      {/* Confirm-диалог */}
      {confirmState && (
        <div
          className="fixed inset-0 z-[70] flex items-center justify-center bg-black/50 p-4 animate-fade-in"
          onMouseDown={() => confirmState.resolve(false)}
        >
          <div
            className="w-full max-w-sm rounded-xl bg-white p-6 shadow-xl animate-slide-up"
            onMouseDown={(e) => e.stopPropagation()}
          >
            <h3 className="font-heading text-base font-semibold text-gray-800">
              {confirmState.title || 'Подтверждение'}
            </h3>
            <p className="mt-2 text-sm text-gray-600">{confirmState.message}</p>
            <div className="mt-5 flex justify-end gap-2">
              <Button variant="secondary" size="sm" onClick={() => confirmState.resolve(false)}>
                {confirmState.cancelText || 'Отмена'}
              </Button>
              <Button
                variant={confirmState.danger ? 'danger' : 'primary'}
                size="sm"
                onClick={() => confirmState.resolve(true)}
              >
                {confirmState.confirmText || 'Подтвердить'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx.toast
}

export function useConfirm() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useConfirm must be used within ToastProvider')
  return ctx.confirm
}
