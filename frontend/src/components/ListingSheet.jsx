import { ExternalLink } from 'lucide-react'
import { useMarkSeen, useMarkFavorited } from '../hooks/useListingMutations'
import SourceBadge from './SourceBadge'

export default function ListingSheet({ listing, onClose }) {
  const markSeen = useMarkSeen()
  const markFavorited = useMarkFavorited()

  if (!listing) return null

  return (
    <>
      {/* Backdrop overlay - click to dismiss per D-03 */}
      <div onClick={onClose} className="fixed inset-0 z-40" />

      {/* Sheet container */}
      <div
        className="fixed bottom-0 left-0 right-0 z-50 bg-white rounded-t-2xl shadow-lg transition-transform duration-300 ease-out"
        style={{ height: '60vh' }}
      >
        {/* Drag handle visual (non-interactive per UI-SPEC) */}
        <div className="flex justify-center pt-3 pb-2">
          <div className="w-10 h-1 rounded-full bg-slate-300" />
        </div>

        {/* Content with padding */}
        <div className="px-4 pb-4 overflow-y-auto" style={{ maxHeight: 'calc(60vh - 48px)' }}>

          {/* Title row */}
          <h2 className="text-xl font-semibold mb-2">{listing.title || 'מודעה'}</h2>

          {/* Price */}
          <p className="text-2xl font-semibold text-blue-600 mb-3">
            {listing.price ? `₪${listing.price.toLocaleString()}` : 'מחיר לא צוין'}
          </p>

          {/* Details grid: rooms, size */}
          <div className="flex gap-4 mb-3 text-base text-slate-700">
            {listing.rooms && <span>{listing.rooms} חדרים</span>}
            {listing.size_sqm && <span>{listing.size_sqm} מ&quot;ר</span>}
          </div>

          {/* Address */}
          {listing.address && (
            <p className="text-base text-slate-600 mb-2">{listing.address}</p>
          )}

          {/* Contact info */}
          {listing.contact_info && (
            <p className="text-base text-slate-700 mb-2">
              <span className="font-semibold">איש קשר: </span>{listing.contact_info}
            </p>
          )}

          {/* Post date + source badge row */}
          <div className="flex items-center gap-3 mb-4 text-sm text-slate-500">
            {listing.post_date && (
              <span>{new Date(listing.post_date).toLocaleDateString('he-IL')}</span>
            )}
            {listing.source_badge && <SourceBadge source={listing.source_badge} />}
          </div>

          {/* Link to original post */}
          {listing.url && (
            <a
              href={listing.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 text-blue-600 hover:text-blue-700 mb-4 min-h-[44px]"
            >
              <ExternalLink size={18} />
              <span>פתח מודעה מקורית</span>
            </a>
          )}

          {/* Action buttons: seen + favorite */}
          <div className="flex gap-3 mt-2">
            <button
              onClick={() => { markSeen.mutate(listing.id); onClose() }}
              disabled={listing.is_seen}
              className="flex-1 min-h-[44px] rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed text-base font-semibold"
            >
              ראיתי
            </button>
            <button
              onClick={() => { markFavorited.mutate(listing.id) }}
              disabled={listing.is_favorited}
              className="flex-1 min-h-[44px] rounded-lg bg-red-50 border border-red-200 text-red-600 hover:bg-red-100 disabled:opacity-50 disabled:cursor-not-allowed text-base font-semibold"
            >
              שמור
            </button>
          </div>
        </div>
      </div>
    </>
  )
}
