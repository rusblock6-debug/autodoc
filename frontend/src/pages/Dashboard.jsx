import React, { useState, useEffect, useMemo } from 'react'
import { useNavigate, useOutletContext } from 'react-router-dom'
import { guidesApi, exportApi, storageApi } from '../services/api'
import {
  Button, IconButton, PageSpinner, EmptyState,
  StarIcon, EditIcon, CopyIcon, TrashIcon, DownloadIcon, PlayIcon, FileIcon,
  GridIcon, ListIcon,
  useToast, useConfirm,
} from '../ui'

const ORDER_KEY = 'autodoc:guide-order'
const VIEW_KEY = 'autodoc:view-mode'

const loadView = () => {
  try { return localStorage.getItem(VIEW_KEY) === 'list' ? 'list' : 'grid' } catch { return 'grid' }
}

// Сохранённый пользователем порядок (localStorage) — пока на бэке нет reorder-эндпоинта.
const loadOrder = () => {
  try { return JSON.parse(localStorage.getItem(ORDER_KEY)) || [] } catch { return [] }
}
const saveOrder = (ids) => {
  try { localStorage.setItem(ORDER_KEY, JSON.stringify(ids)) } catch {}
}

// Применяет сохранённый порядок к списку гайдов (новые — в начало).
const applyOrder = (list) => {
  const order = loadOrder()
  if (!order.length) return list
  const pos = new Map(order.map((id, i) => [id, i]))
  return [...list].sort((a, b) => {
    const pa = pos.has(a.id) ? pos.get(a.id) : -1
    const pb = pos.has(b.id) ? pos.get(b.id) : -1
    return pa - pb
  })
}

const STATUS_BADGE = {
  draft: { label: 'Черновик', cls: 'bg-gray-100 text-gray-600' },
  ready: { label: 'Готов', cls: 'bg-emerald-50 text-emerald-600' },
  processing: { label: 'Обработка', cls: 'bg-brand-50 text-brand-600' },
  completed: { label: 'Готов', cls: 'bg-emerald-50 text-emerald-600' },
}

function Dashboard() {
  const { guides: contextGuides, fetchGuides } = useOutletContext() || {}
  const navigate = useNavigate()
  const toast = useToast()
  const confirm = useConfirm()

  const [guides, setGuides] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('all') // all | favorites | drafts
  const [view, setView] = useState(loadView) // grid | list
  const [draggedId, setDraggedId] = useState(null)
  const [dragOverId, setDragOverId] = useState(null)

  useEffect(() => {
    if (contextGuides) {
      setGuides(applyOrder(contextGuides))
      setLoading(false)
    } else {
      loadGuides()
    }
  }, [contextGuides])

  const loadGuides = async () => {
    try {
      const response = await guidesApi.getAll()
      setGuides(applyOrder(response.items || response || []))
    } catch {
      toast.error('Не удалось загрузить руководства')
    } finally {
      setLoading(false)
    }
  }

  const refresh = () => (fetchGuides ? fetchGuides() : loadGuides())

  const changeView = (mode) => {
    setView(mode)
    try { localStorage.setItem(VIEW_KEY, mode) } catch {}
  }

  const handleDelete = async (guide, e) => {
    e?.preventDefault(); e?.stopPropagation()
    const ok = await confirm({
      title: 'Удалить руководство',
      message: `«${guide.title}» будет удалено безвозвратно.`,
      danger: true, confirmText: 'Удалить',
    })
    if (!ok) return
    try {
      await guidesApi.delete(guide.id)
      toast.success('Руководство удалено')
      refresh()
    } catch {
      toast.error('Не удалось удалить')
    }
  }

  const handleDuplicate = async (guide, e) => {
    e?.preventDefault(); e?.stopPropagation()
    try {
      await guidesApi.create({ title: `${guide.title} (копия)`, language: guide.language || 'ru' })
      toast.success('Создана копия')
      refresh()
    } catch {
      toast.error('Не удалось дублировать')
    }
  }

  const handleToggleFavorite = async (guide, e) => {
    e?.preventDefault(); e?.stopPropagation()
    // Оптимистичное обновление
    setGuides(prev => prev.map(g => g.id === guide.id ? { ...g, is_favorite: !g.is_favorite } : g))
    try {
      await guidesApi.update(guide.id, { is_favorite: !guide.is_favorite })
    } catch {
      toast.error('Не удалось обновить избранное')
      refresh()
    }
  }

  const handleExport = async (guide, format, e) => {
    e?.preventDefault(); e?.stopPropagation()
    try {
      const blob = format === 'pdf' ? await exportApi.pdf(guide.id) : await exportApi.json(guide.id)
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${guide.title}.${format}`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch {
      toast.error(`Ошибка экспорта в ${format.toUpperCase()}`)
    }
  }

  // --- Drag & drop (порядок хранится в localStorage) ---
  const handleDrop = (targetId) => {
    setDragOverId(null)
    if (!draggedId || !targetId || draggedId === targetId) { setDraggedId(null); return }
    const di = guides.findIndex(g => g.id === draggedId)
    const ti = guides.findIndex(g => g.id === targetId)
    if (di === -1 || ti === -1) { setDraggedId(null); return }
    const next = [...guides]
    const [moved] = next.splice(di, 1)
    next.splice(ti, 0, moved)
    setGuides(next)
    saveOrder(next.map(g => g.id))
    setDraggedId(null)
  }

  const filtered = useMemo(() => {
    let list = guides
    if (filter === 'favorites') list = list.filter(g => g.is_favorite)
    if (filter === 'drafts') list = list.filter(g => g.status === 'draft')
    if (search.trim()) {
      const q = search.trim().toLowerCase()
      list = list.filter(g => g.title?.toLowerCase().includes(q))
    }
    return list
  }, [guides, filter, search])

  if (loading) return <PageSpinner label="Загрузка руководств…" />

  const tabs = [
    { key: 'all', label: 'Все', count: guides.length },
    { key: 'favorites', label: 'Избранное', count: guides.filter(g => g.is_favorite).length },
    { key: 'drafts', label: 'Черновики', count: guides.filter(g => g.status === 'draft').length },
  ]

  return (
    <div className="mx-auto max-w-6xl px-8 py-7">
      {/* Header */}
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="font-heading text-xl font-semibold text-gray-800">Руководства</h1>
          <p className="mt-0.5 text-sm text-gray-400">{guides.length} документов</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Поиск…"
              className="h-9 w-64 rounded-lg border border-gray-300 bg-white pl-9 pr-3 text-sm text-gray-700 outline-none transition-colors placeholder:text-gray-400 focus:border-brand-400"
            />
            <svg className="pointer-events-none absolute left-3 top-2.5 text-gray-400" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
          </div>

          {/* Переключатель вида: плитка / список */}
          <div className="flex h-9 items-center rounded-lg border border-gray-300 bg-white p-0.5">
            <button
              onClick={() => changeView('grid')}
              title="Плиткой"
              aria-label="Плиткой"
              aria-pressed={view === 'grid'}
              className={[
                'flex h-8 w-8 items-center justify-center rounded-md transition-colors',
                view === 'grid' ? 'bg-brand-50 text-brand-600' : 'text-gray-400 hover:text-gray-600',
              ].join(' ')}
            >
              <GridIcon size={16} />
            </button>
            <button
              onClick={() => changeView('list')}
              title="Списком"
              aria-label="Списком"
              aria-pressed={view === 'list'}
              className={[
                'flex h-8 w-8 items-center justify-center rounded-md transition-colors',
                view === 'list' ? 'bg-brand-50 text-brand-600' : 'text-gray-400 hover:text-gray-600',
              ].join(' ')}
            >
              <ListIcon size={16} />
            </button>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="mb-5 flex gap-1 border-b border-gray-200">
        {tabs.map(t => (
          <button
            key={t.key}
            onClick={() => setFilter(t.key)}
            className={[
              'relative -mb-px px-3 py-2 text-sm font-medium transition-colors',
              filter === t.key
                ? 'border-b-2 border-brand-500 text-brand-600'
                : 'border-b-2 border-transparent text-gray-500 hover:text-gray-700',
            ].join(' ')}
          >
            {t.label}
            <span className="ml-1.5 rounded-full bg-gray-100 px-1.5 py-0.5 text-xs text-gray-500">{t.count}</span>
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <EmptyState
          icon={FileIcon}
          title={search || filter !== 'all' ? 'Ничего не найдено' : 'Пока нет руководств'}
          description={
            search || filter !== 'all'
              ? 'Измените запрос или фильтр.'
              : 'Начните запись через расширение Chrome — гайд появится здесь автоматически.'
          }
        />
      ) : (
        (() => {
          const itemProps = (guide) => ({
            guide,
            onOpen: () => navigate(`/guide/${guide.uuid}/edit`),
            onToggleFavorite: (e) => handleToggleFavorite(guide, e),
            onDuplicate: (e) => handleDuplicate(guide, e),
            onDelete: (e) => handleDelete(guide, e),
            onExport: (fmt, e) => handleExport(guide, fmt, e),
            draggable: filter === 'all' && !search,
            isDragging: draggedId === guide.id,
            isDragOver: dragOverId === guide.id,
            onDragStart: () => setDraggedId(guide.id),
            onDragOver: (e) => { e.preventDefault(); if (guide.id !== draggedId) setDragOverId(guide.id) },
            onDragLeave: () => setDragOverId(null),
            onDrop: (e) => { e.preventDefault(); handleDrop(guide.id) },
            onDragEnd: () => { setDraggedId(null); setDragOverId(null) },
          })

          return view === 'list' ? (
            <div className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-card">
              {filtered.map((guide) => (
                <GuideRow key={guide.id || guide.uuid} {...itemProps(guide)} />
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {filtered.map((guide) => (
                <GuideCard key={guide.id || guide.uuid} {...itemProps(guide)} />
              ))}
            </div>
          )
        })()
      )}
    </div>
  )
}

function GuideCard({
  guide, onOpen, onToggleFavorite, onDuplicate, onDelete, onExport,
  draggable, isDragging, isDragOver, ...dnd
}) {
  const badge = STATUS_BADGE[guide.status] || STATUS_BADGE.draft
  const thumbUrl = guide.thumbnail ? storageApi.getScreenshotUrl(guide.thumbnail) : null

  return (
    <div
      draggable={draggable}
      {...dnd}
      onClick={onOpen}
      className={[
        'group relative cursor-pointer overflow-hidden rounded-xl border bg-white shadow-card transition-all duration-150',
        'hover:-translate-y-0.5 hover:shadow-card-hover',
        isDragOver ? 'border-brand-400 ring-2 ring-brand-200' : 'border-gray-200',
        isDragging ? 'opacity-50' : '',
      ].join(' ')}
    >
      {/* Thumbnail */}
      <div className="relative aspect-video w-full overflow-hidden bg-gray-100">
        {thumbUrl ? (
          <img src={thumbUrl} alt="" className="h-full w-full object-cover" draggable={false} />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-gray-300">
            <FileIcon size={40} />
          </div>
        )}
        {/* Play overlay */}
        <div className="absolute inset-0 flex items-center justify-center bg-black/0 transition-colors group-hover:bg-black/20">
          <span className="flex h-11 w-11 scale-90 items-center justify-center rounded-full bg-white/90 text-brand-600 opacity-0 shadow-md transition-all group-hover:scale-100 group-hover:opacity-100">
            <PlayIcon size={18} />
          </span>
        </div>
        {/* Favorite */}
        <button
          onClick={onToggleFavorite}
          aria-label={guide.is_favorite ? 'Убрать из избранного' : 'В избранное'}
          className={[
            'absolute right-2 top-2 flex h-8 w-8 items-center justify-center rounded-full backdrop-blur transition-colors',
            guide.is_favorite ? 'bg-white/90 text-brand-500' : 'bg-black/30 text-white hover:bg-black/50',
          ].join(' ')}
        >
          <StarIcon size={16} filled={guide.is_favorite} />
        </button>
        {/* Step count */}
        {guide.step_count > 0 && (
          <span className="absolute bottom-2 left-2 rounded-md bg-black/60 px-2 py-0.5 text-xs font-medium text-white">
            {guide.step_count} шагов
          </span>
        )}
      </div>

      {/* Body */}
      <div className="p-4">
        <div className="flex items-start justify-between gap-2">
          <h3 className="line-clamp-2 font-heading text-sm font-semibold text-gray-800">{guide.title}</h3>
          <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${badge.cls}`}>{badge.label}</span>
        </div>
        <p className="mt-1 text-xs text-gray-400">
          {guide.created_at ? new Date(guide.created_at).toLocaleDateString('ru-RU') : ''}
        </p>

        {/* Actions */}
        <div className="mt-3 flex items-center justify-between border-t border-gray-100 pt-3">
          <Button variant="secondary" size="sm" icon={EditIcon} onClick={onOpen}>
            Открыть
          </Button>
          <div className="flex items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
            <IconButton icon={CopyIcon} label="Дублировать" size={30} iconSize={15} onClick={onDuplicate} />
            <IconButton icon={DownloadIcon} label="Скачать PDF" size={30} iconSize={15} onClick={(e) => onExport('pdf', e)} />
            <IconButton icon={FileIcon} label="Скачать JSON" size={30} iconSize={15} onClick={(e) => onExport('json', e)} />
            <IconButton icon={TrashIcon} label="Удалить" tone="danger" size={30} iconSize={15} onClick={onDelete} />
          </div>
        </div>
      </div>
    </div>
  )
}

function GuideRow({
  guide, onOpen, onToggleFavorite, onDuplicate, onDelete, onExport,
  draggable, isDragging, isDragOver, ...dnd
}) {
  const badge = STATUS_BADGE[guide.status] || STATUS_BADGE.draft
  const thumbUrl = guide.thumbnail ? storageApi.getScreenshotUrl(guide.thumbnail) : null

  return (
    <div
      draggable={draggable}
      {...dnd}
      onClick={onOpen}
      className={[
        'group flex cursor-pointer items-center gap-4 border-b border-gray-100 px-4 py-3 transition-colors last:border-b-0',
        isDragOver ? 'bg-brand-50' : 'hover:bg-gray-50',
        isDragging ? 'opacity-50' : '',
      ].join(' ')}
    >
      {/* Thumbnail */}
      <div className="relative h-12 w-20 shrink-0 overflow-hidden rounded-md bg-gray-100">
        {thumbUrl ? (
          <img src={thumbUrl} alt="" className="h-full w-full object-cover" draggable={false} />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-gray-300">
            <FileIcon size={20} />
          </div>
        )}
      </div>

      {/* Title + meta */}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <h3 className="truncate font-heading text-sm font-semibold text-gray-800">{guide.title}</h3>
          <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${badge.cls}`}>{badge.label}</span>
        </div>
        <p className="mt-0.5 text-xs text-gray-400">
          {guide.created_at ? new Date(guide.created_at).toLocaleDateString('ru-RU') : ''}
          {guide.step_count > 0 && <span> · {guide.step_count} шагов</span>}
        </p>
      </div>

      {/* Actions — всегда видимы в списке, чуть ярче при наведении на строку */}
      <div className="flex shrink-0 items-center gap-0.5 opacity-70 transition-opacity group-hover:opacity-100">
        <IconButton
          icon={(p) => <StarIcon {...p} filled={guide.is_favorite} />}
          label={guide.is_favorite ? 'Убрать из избранного' : 'В избранное'}
          tone={guide.is_favorite ? 'active' : 'default'}
          size={32} iconSize={16}
          onClick={onToggleFavorite}
        />
        <IconButton icon={CopyIcon} label="Дублировать" size={32} iconSize={15} onClick={onDuplicate} />
        <IconButton icon={DownloadIcon} label="Скачать PDF" size={32} iconSize={15} onClick={(e) => onExport('pdf', e)} />
        <IconButton icon={FileIcon} label="Скачать JSON" size={32} iconSize={15} onClick={(e) => onExport('json', e)} />
        <IconButton icon={TrashIcon} label="Удалить" tone="danger" size={32} iconSize={15} onClick={onDelete} />
      </div>
    </div>
  )
}

export default Dashboard
