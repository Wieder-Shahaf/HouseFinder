import L from 'leaflet'

export function createListingIcon(listing) {
  if (listing.is_favorited) {
    const html = `<div style="color:#EF4444;font-size:24px;filter:drop-shadow(0 1px 2px rgba(0,0,0,0.3))">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" fill="#EF4444" stroke="#EF4444" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3.332.88-4.5 2.17C10.832 3.88 9.26 3 7.5 3A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/>
      </svg>
    </div>`
    return L.divIcon({
      html,
      className: '',
      iconSize: [24, 24],
      iconAnchor: [12, 12],
    })
  }

  if (listing.is_seen) {
    const html = `<div style="width:16px;height:16px;background:#94A3B8;border-radius:50%;border:2px solid white;opacity:0.5;box-shadow:0 1px 3px rgba(0,0,0,0.2)"></div>`
    return L.divIcon({
      html,
      className: '',
      iconSize: [20, 20],
      iconAnchor: [10, 10],
    })
  }

  // Default: unseen (new)
  const html = `<div style="width:16px;height:16px;background:#2563EB;border-radius:50%;border:2px solid white;box-shadow:0 1px 3px rgba(0,0,0,0.3)"></div>`
  return L.divIcon({
    html,
    className: '',
    iconSize: [20, 20],
    iconAnchor: [10, 10],
  })
}
