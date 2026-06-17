import React from 'react'

const TONES = {
  default: 'text-gray-400 hover:text-brand-600 hover:bg-brand-50',
  active: 'text-brand-500 hover:bg-brand-50',
  danger: 'text-gray-400 hover:text-red-600 hover:bg-red-50',
}

/**
 * Квадратная иконочная кнопка. Передавайте компонент иконки через `icon`.
 */
function IconButton({ icon: IconCmp, label, tone = 'default', size = 32, iconSize = 16, className = '', ...props }) {
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      className={[
        'inline-flex items-center justify-center rounded-md transition-colors duration-150',
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300',
        TONES[tone],
        className,
      ].join(' ')}
      style={{ width: size, height: size }}
      {...props}
    >
      <IconCmp size={iconSize} />
    </button>
  )
}

export default IconButton
