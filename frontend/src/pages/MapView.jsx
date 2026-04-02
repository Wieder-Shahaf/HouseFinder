import { useState } from 'react'
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet'
import { SlidersHorizontal } from 'lucide-react'
import { useListings } from '../hooks/useListings'
import { createListingIcon } from '../components/ListingPin'
import ListingSheet from '../components/ListingSheet'
import FilterSheet from '../components/FilterSheet'

const HAIFA_CENTER = [32.7940, 34.9896]
const DEFAULT_ZOOM = 13

export default function MapView() {
  const [showFilters, setShowFilters] = useState(false)
  const [filters, setFilters] = useState({})

  // Build API params from filters state
  const apiParams = {}
  if (filters.price_max && filters.price_max < 4500) apiParams.price_max = filters.price_max
  if (filters.rooms?.length === 1) {
    const r = filters.rooms[0]
    if (r === 3.5) {
      apiParams.rooms_min = 3.5
    } else {
      apiParams.rooms_min = r
      apiParams.rooms_max = r
    }
  } else if (filters.rooms?.length > 1) {
    apiParams.rooms_min = Math.min(...filters.rooms)
    if (!filters.rooms.includes(3.5)) apiParams.rooms_max = Math.max(...filters.rooms)
  }
  if (filters.neighborhoods?.length === 1) apiParams.neighborhood = filters.neighborhoods[0]
  if (filters.newOnly) apiParams.since_hours = 24

  const { data, isLoading, isError } = useListings(apiParams)
  const listings = data ?? []
  const listingsWithCoords = listings.filter(l => l.lat != null && l.lng != null)
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
            eventHandlers={{
              click: () => {
                setShowFilters(false)
              },
            }}
          >
            <Popup closeButton={false} autoClose={true} closeOnClick={true}>
              <ListingSheet listing={listing} />
            </Popup>
          </Marker>
        ))}
      </MapContainer>

      {listings.length === 0 && (
        <div
          className="absolute inset-0 flex flex-col items-center justify-center gap-2 p-8 text-center bg-white/80 z-20"
          style={{ height: 'calc(100dvh - 56px)' }}
        >
          <h2 className="text-xl font-semibold text-slate-700">אין מודעות זמינות</h2>
          <p className="text-base text-slate-500">נסה לשנות את הסינון או לרענן</p>
        </div>
      )}

      {/* Filter button - top-right corner */}
      <button
        onClick={() => setShowFilters(true)}
        aria-label="סנן מודעות"
        className="absolute top-4 right-4 z-30 bg-white rounded-full p-3 shadow-md min-h-[44px] min-w-[44px] flex items-center justify-center"
      >
        <SlidersHorizontal size={20} className="text-slate-700" />
      </button>

      <FilterSheet
        isOpen={showFilters}
        onClose={() => setShowFilters(false)}
        filters={filters}
        onFilterChange={setFilters}
      />
    </div>
  )
}
