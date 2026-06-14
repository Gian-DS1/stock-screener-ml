import { Star } from 'lucide-react'
import clsx from 'clsx'
import { useFavoriteMutation, useFavorites } from '../lib/api'

/** Estrella para fijar/quitar una empresa de la lista de seguimiento. */
export default function FavoriteStar({
  ticker,
  company,
  sector,
  size = 16,
}: {
  ticker: string
  company?: string | null
  sector?: string | null
  size?: number
}) {
  const { data } = useFavorites()
  const { add, remove } = useFavoriteMutation()
  const isFav = data?.set.has(ticker) ?? false

  return (
    <button
      type="button"
      aria-label={isFav ? `Quitar ${ticker} de favoritas` : `Seguir ${ticker}`}
      title={isFav ? 'En tu lista de seguimiento' : 'Seguir esta empresa'}
      onClick={(e) => {
        e.stopPropagation()
        if (isFav) remove.mutate(ticker)
        else add.mutate({ ticker, company, sector })
      }}
      className={clsx(
        'inline-flex shrink-0 transition-colors',
        isFav ? 'text-warn' : 'text-faint hover:text-warn',
      )}
    >
      <Star size={size} fill={isFav ? 'currentColor' : 'none'} strokeWidth={1.75} />
    </button>
  )
}
