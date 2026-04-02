import { MapContainer, TileLayer, Marker } from 'react-leaflet'
import { useListings } from '../hooks/useListings'
import { createListingIcon } from '../components/ListingPin'

const HAIFA_CENTER = [32.7940, 34.9896]
const DEFAULT_ZOOM = 13

export default function MapView({ filterParams = {}, onPinClick }) {
  const { data, isLoading, isError } = useListings(filterParams)

  if (isLoading) {
    return (
      <div
        className="flex items-center justify-center"
        style={{ height: 'calc(100dvh - 56px)' }}
      >
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  if (isError) {
    return (
      <div
        className="flex flex-col items-center justify-center gap-2 p-8 text-center"
        style={{ height: 'calc(100dvh - 56px)' }}
      >
        <h2 className="text-xl font-semibold text-red-500">שגיאה בטעינת המודעות</h2>
        <p className="text-base text-slate-600">לא ניתן להתחבר לשרת. נסה שוב מאוחר יותר.</p>
      </div>
    )
  }

  const listings = data ?? []
  const listingsWithCoords = listings.filter(l => l.lat != null && l.lng != null)

  return (
    <div style={{ position: 'relative' }}>
      <MapContainer
        center={HAIFA_CENTER}
        zoom={DEFAULT_ZOOM}
        style={{ height: 'calc(100dvh - 56px)', width: '100%' }}
        zoomControl={true}
      >
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        />
        {listingsWithCoords.map(listing => (
          <Marker
            key={listing.id}
            position={[listing.lat, listing.lng]}
            icon={createListingIcon(listing)}
            eventHandlers={{ click: () => onPinClick?.(listing) }}
          />
        ))}
      </MapContainer>

      {listings.length === 0 && (
        <div
          className="absolute inset-0 flex flex-col items-center justify-center gap-2 p-8 text-center bg-white/80 z-[1000]"
          style={{ height: 'calc(100dvh - 56px)' }}
        >
          <h2 className="text-xl font-semibold text-slate-700">אין מודעות זמינות</h2>
          <p className="text-base text-slate-500">נסה לשנות את הסינון או לרענן</p>
        </div>
      )}
    </div>
  )
}
