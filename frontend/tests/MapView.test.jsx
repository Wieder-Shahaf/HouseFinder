import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import MapView from '../src/pages/MapView'

// Mock react-leaflet
vi.mock('react-leaflet', () => ({
  MapContainer: ({ children, ...props }) => (
    <div data-testid="map-container" {...props}>
      {children}
    </div>
  ),
  TileLayer: () => <div data-testid="tile-layer" />,
  Marker: ({ position, children }) => (
    <div
      data-testid="map-marker"
      data-position={JSON.stringify(position)}
    >
      {children}
    </div>
  ),
  Popup: ({ children }) => <div data-testid="map-popup">{children}</div>,
  useMapEvents: () => ({}),
  useMap: () => ({}),
}))

// Mock the useListings hook
vi.mock('../src/hooks/useListings', () => ({
  useListings: vi.fn(),
}))

// Mock createListingIcon to avoid Leaflet dependency
vi.mock('../src/components/ListingPin', () => ({
  createListingIcon: vi.fn(() => null),
}))

import { useListings } from '../src/hooks/useListings'

function wrapper({ children }) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}

describe('MapView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders map container', () => {
    useListings.mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
    })
    render(<MapView />, { wrapper })
    expect(screen.getByTestId('map-container')).toBeInTheDocument()
  })

  it('renders markers for listings with coords', () => {
    useListings.mockReturnValue({
      data: [
        { id: 1, lat: 32.79, lng: 34.99, is_seen: false, is_favorited: false },
        { id: 2, lat: 32.80, lng: 34.98, is_seen: false, is_favorited: false },
      ],
      isLoading: false,
      isError: false,
    })
    render(<MapView />, { wrapper })
    const markers = screen.getAllByTestId('map-marker')
    expect(markers).toHaveLength(2)
  })

  it('skips listings without coordinates', () => {
    useListings.mockReturnValue({
      data: [
        { id: 1, lat: null, lng: null, is_seen: false, is_favorited: false },
        { id: 2, lat: 32.79, lng: 34.99, is_seen: false, is_favorited: false },
      ],
      isLoading: false,
      isError: false,
    })
    render(<MapView />, { wrapper })
    const markers = screen.getAllByTestId('map-marker')
    // Only the listing with coords should render a marker
    expect(markers).toHaveLength(1)
  })

  it('shows loading state', () => {
    useListings.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    })
    render(<MapView />, { wrapper })
    // Spinner element uses animate-spin class
    const spinner = document.querySelector('.animate-spin')
    expect(spinner).toBeInTheDocument()
  })

  it('shows error state', () => {
    useListings.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    })
    render(<MapView />, { wrapper })
    expect(screen.getByText('שגיאה בטעינת המודעות')).toBeInTheDocument()
  })
})
