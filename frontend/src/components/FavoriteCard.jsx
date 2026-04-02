import SourceBadge from './SourceBadge'
import { ExternalLink } from 'lucide-react'

export default function FavoriteCard({ listing }) {
  return (
    <div className="bg-white rounded-xl shadow-sm p-4 mb-3">
      {/* Title */}
      <h3 className="text-base font-semibold mb-1">{listing.title || 'מודעה'}</h3>

      {/* Price */}
      <p className="text-xl font-semibold text-blue-600 mb-2">
        {listing.price ? `₪${listing.price.toLocaleString()}` : 'מחיר לא צוין'}
      </p>

      {/* Details: rooms + size */}
      <div className="flex gap-3 text-sm text-slate-600 mb-2">
        {listing.rooms && <span>{listing.rooms} חדרים</span>}
        {listing.size_sqm && <span>{listing.size_sqm} מ"ר</span>}
      </div>

      {/* Address */}
      {listing.address && <p className="text-sm text-slate-500 mb-2">{listing.address}</p>}

      {/* Bottom row: date + source + link */}
      <div className="flex items-center justify-between mt-2">
        <div className="flex items-center gap-2 text-sm text-slate-400">
          {listing.post_date && (
            <span>{new Date(listing.post_date).toLocaleDateString('he-IL')}</span>
          )}
          {listing.source_badge && <SourceBadge source={listing.source_badge} />}
        </div>
        {listing.url && (
          <a
            href={listing.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-blue-600 text-sm min-h-[44px]"
          >
            <ExternalLink size={16} />
            <span>פתח</span>
          </a>
        )}
      </div>
    </div>
  )
}
