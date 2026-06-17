import React from 'react'

/**
 * Пустое состояние с иконкой, заголовком, подсказкой и опциональным CTA.
 */
function EmptyState({ icon: IconCmp, title, description, action }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-gray-300 bg-white px-6 py-16 text-center">
      {IconCmp && (
        <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-brand-50 text-brand-500">
          <IconCmp size={26} />
        </div>
      )}
      <h3 className="font-heading text-base font-semibold text-gray-800">{title}</h3>
      {description && <p className="mt-1 max-w-sm text-sm text-gray-500">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}

export default EmptyState
