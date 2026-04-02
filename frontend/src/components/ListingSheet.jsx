import { useEffect, useMemo, useState } from 'react'
import { ExternalLink } from 'lucide-react'
import { useMarkSeen, useMarkFavorited } from '../hooks/useListingMutations'
import SourceBadge from './SourceBadge'

function resolveListingImages(listing) {
  if (!listing) return []

  const collected = []
  const pushIfValid = value => {
    if (!value || typeof value !== 'string') return
    if (!collected.includes(value)) collected.push(value)
  }

  pushIfValid(listing.image_url)
  pushIfValid(listing.thumbnail_url)
  pushIfValid(listing.thumbnail)

  const extractImageValue = item => {
    if (!item) return null
    if (typeof item === 'string') return item
    return item.url || item.src || null
  }

  if (Array.isArray(listing.image_urls)) {
    listing.image_urls.forEach(item => pushIfValid(extractImageValue(item)))
  }

  if (Array.isArray(listing.images)) {
    listing.images.forEach(item => pushIfValid(extractImageValue(item)))
  }

  return collected
}

export default function ListingSheet({ listing, onClose }) {
  const markSeen = useMarkSeen()
  const markFavorited = useMarkFavorited()
  const images = useMemo(() => resolveListingImages(listing), [listing])
  const [activeImageIndex, setActiveImageIndex] = useState(0)
  const [touchStartX, setTouchStartX] = useState(null)
  const [imageFitByUrl, setImageFitByUrl] = useState({})

  const hasImages = images.length > 0
  const activeImageUrl = hasImages ? images[activeImageIndex] : null
  const activeImageFit = activeImageUrl ? imageFitByUrl[activeImageUrl] : null

  useEffect(() => {
    if (!images.length) {
      setActiveImageIndex(0)
      return
    }
    if (activeImageIndex > images.length - 1) {
      setActiveImageIndex(0)
    }
  }, [images, activeImageIndex])

  const goToImage = nextIndex => {
    if (!hasImages) return
    const normalized = (nextIndex + images.length) % images.length
    setActiveImageIndex(normalized)
  }

  const onTouchStart = event => {
    if (!hasImages || images.length < 2) return
    setTouchStartX(event.touches[0].clientX)
  }

  const onTouchEnd = event => {
    if (!hasImages || images.length < 2 || touchStartX == null) return
    const deltaX = event.changedTouches[0].clientX - touchStartX
    setTouchStartX(null)

    if (Math.abs(deltaX) < 24) return
    if (deltaX < 0) {
      goToImage(activeImageIndex + 1)
    } else {
      goToImage(activeImageIndex - 1)
    }
  }

  const onImageLoad = event => {
    const target = event.currentTarget
    const src = target.currentSrc || target.src
    const ratio = target.naturalWidth / target.naturalHeight
    const fitMode = ratio < 0.9 ? 'contain' : 'cover'

    setImageFitByUrl(prev => {
      if (prev[src] === fitMode) return prev
      return { ...prev, [src]: fitMode }
    })
  }

  if (!listing) return null

  return (
    <div
      data-testid="listing-popup-card"
      className="w-[min(82vw,320px)] max-w-[320px] max-h-[420px] bg-white rounded-2xl overflow-hidden shadow-xl"
    >
      <div className="flex flex-col">
        {hasImages && (
          <div
            className="relative"
            onTouchStart={onTouchStart}
            onTouchEnd={onTouchEnd}
            data-testid="listing-image-carousel"
          >
            <img
              src={activeImageUrl}
              alt={listing.title || 'תמונת מודעה'}
              onLoad={onImageLoad}
              data-testid="listing-carousel-image"
              className={`w-full h-28 ${activeImageFit === 'contain' ? 'object-contain bg-slate-100' : 'object-cover'}`}
              loading="lazy"
            />

            {images.length > 1 && (
              <div className="absolute bottom-2 left-0 right-0 flex items-center justify-center gap-1.5">
                {images.map((image, index) => (
                  <button
                    type="button"
                    key={image + index}
                    aria-label={`מעבר לתמונה ${index + 1}`}
                    onClick={() => goToImage(index)}
                    className={`h-2 rounded-full transition-all ${
                      index === activeImageIndex
                        ? 'w-4 bg-white'
                        : 'w-2 bg-white/70'
                    }`}
                  />
                ))}
              </div>
            )}
          </div>
        )}

        {/* Scroll only when content actually exceeds max height */}
        <div
          data-testid="listing-popup-scroll"
          className="px-4 pt-3 overflow-y-auto overflow-x-hidden break-words"
          style={{ maxHeight: hasImages ? '260px' : '300px' }}
        >
          <h2 className="text-[15px] font-semibold mb-1.5 leading-snug break-words">{listing.title || 'מודעה'}</h2>

          <p className="text-lg font-semibold text-blue-600 mb-2">
            {listing.price ? `₪${listing.price.toLocaleString()}` : 'מחיר לא צוין'}
          </p>

          <div className="grid grid-cols-2 gap-x-2 gap-y-1 mb-2 text-xs text-slate-700">
            {listing.rooms && <span>חדרים: {listing.rooms}</span>}
            {listing.size_sqm && <span>גודל: {listing.size_sqm} מ&quot;ר</span>}
          </div>

          {listing.address && (
            <p className="text-xs text-slate-600 mb-1.5 break-words">{listing.address}</p>
          )}

          {listing.contact_info && (
            <p className="text-xs text-slate-700 mb-1.5 break-words">
              <span className="font-semibold">איש קשר: </span>{listing.contact_info}
            </p>
          )}

          <div className="flex items-center gap-2 mb-2 text-xs text-slate-500">
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
              className="flex items-center gap-2 text-xs text-blue-600 hover:text-blue-700 mb-2 min-h-[36px] break-words"
            >
              <ExternalLink size={15} />
              <span>פתח מודעה מקורית</span>
            </a>
          )}
        </div>

        <div className="border-t border-slate-100 px-4 py-2.5 bg-white">
          <div className="flex gap-3">
            <button
              onClick={() => { markSeen.mutate(listing.id); onClose?.() }}
              disabled={listing.is_seen}
              className="flex-1 min-h-[40px] rounded-xl border border-slate-300 text-slate-700 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-semibold"
            >
              ראיתי
            </button>
            <button
              onClick={() => { markFavorited.mutate(listing.id) }}
              disabled={listing.is_favorited}
              className="flex-1 min-h-[40px] rounded-xl bg-red-50 border border-red-200 text-red-600 hover:bg-red-100 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-semibold"
            >
              שמור
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
