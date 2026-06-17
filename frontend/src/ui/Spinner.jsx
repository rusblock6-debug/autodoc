import React from 'react'

function Spinner({ size = 24, className = '' }) {
  return (
    <span
      role="status"
      aria-label="Загрузка"
      className={['inline-block rounded-full border-2 border-gray-200 border-t-brand-500 animate-spin', className].join(' ')}
      style={{ width: size, height: size }}
    />
  )
}

export function PageSpinner({ label }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-20 text-gray-400">
      <Spinner size={28} />
      {label && <span className="text-sm">{label}</span>}
    </div>
  )
}

export default Spinner
