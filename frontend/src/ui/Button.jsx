import React from 'react'

const VARIANTS = {
  primary: 'bg-brand-500 text-white border border-transparent hover:bg-brand-600 active:bg-brand-700 shadow-sm',
  secondary: 'bg-white text-gray-700 border border-gray-300 hover:border-brand-400 hover:text-brand-600',
  ghost: 'bg-transparent text-gray-600 border border-transparent hover:bg-gray-100',
  danger: 'bg-white text-red-600 border border-gray-300 hover:border-red-400 hover:bg-red-50',
  success: 'bg-emerald-500 text-white border border-transparent hover:bg-emerald-600 shadow-sm',
}

const SIZES = {
  sm: 'h-8 px-3 text-xs gap-1.5',
  md: 'h-9 px-4 text-sm gap-2',
  lg: 'h-11 px-5 text-sm gap-2',
}

/**
 * Унифицированная кнопка дизайн-системы.
 * variant: primary | secondary | ghost | danger | success
 * size: sm | md | lg
 */
function Button({
  variant = 'primary',
  size = 'md',
  icon: IconCmp,
  uppercase = false,
  className = '',
  disabled,
  children,
  ...props
}) {
  return (
    <button
      disabled={disabled}
      className={[
        'inline-flex items-center justify-center rounded-md font-heading font-semibold',
        'transition-colors duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300',
        'disabled:opacity-50 disabled:cursor-not-allowed disabled:pointer-events-none',
        uppercase ? 'uppercase tracking-wide' : '',
        VARIANTS[variant],
        SIZES[size],
        className,
      ].join(' ')}
      {...props}
    >
      {IconCmp && <IconCmp size={size === 'sm' ? 14 : 16} />}
      {children}
    </button>
  )
}

export default Button
