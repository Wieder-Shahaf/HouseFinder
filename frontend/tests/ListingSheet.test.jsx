import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import ListingSheet from '../src/components/ListingSheet'

// Mock the mutation hooks
const mockMarkSeenMutate = vi.fn()
const mockMarkFavoritedMutate = vi.fn()

vi.mock('../src/hooks/useListingMutations', () => ({
  useMarkSeen: () => ({ mutate: mockMarkSeenMutate }),
  useMarkFavorited: () => ({ mutate: mockMarkFavoritedMutate }),
}))

function wrapper({ children }) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}

const sampleListing = {
  id: 42,
  title: 'דירה יפה בכרמל',
  price: 3500,
  rooms: 3,
  size_sqm: 75,
  address: 'רחוב הנשיא 10, חיפה',
  contact_info: 'ישראל ישראלי',
  post_date: '2026-04-01T10:00:00Z',
  source_badge: 'יד2',
  url: 'https://www.yad2.co.il/item/123',
  is_seen: false,
  is_favorited: false,
}

describe('ListingSheet', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders nothing when listing is null', () => {
    const { container } = render(
      <ListingSheet listing={null} onClose={vi.fn()} />,
      { wrapper }
    )
    expect(container.firstChild).toBeNull()
  })

  it('renders listing details', () => {
    render(
      <ListingSheet listing={sampleListing} onClose={vi.fn()} />,
      { wrapper }
    )
    // Price
    expect(screen.getByText('₪3,500')).toBeInTheDocument()
    // Rooms
    expect(screen.getByText('חדרים: 3')).toBeInTheDocument()
    // Address
    expect(screen.getByText('רחוב הנשיא 10, חיפה')).toBeInTheDocument()
    // Source badge
    expect(screen.getByText('יד2')).toBeInTheDocument()
    // Original post link
    expect(screen.getByText('פתח מודעה מקורית')).toBeInTheDocument()
  })

  it('renders fixed-size popup card with scrollable content', () => {
    render(
      <ListingSheet listing={sampleListing} onClose={vi.fn()} />,
      { wrapper }
    )
    const popupCard = screen.getByTestId('listing-popup-card')
    const scrollArea = screen.getByTestId('listing-popup-scroll')
    expect(popupCard).toBeInTheDocument()
    expect(scrollArea).toBeInTheDocument()
  })

  it('renders listing image when image url exists', () => {
    render(
      <ListingSheet
        listing={{ ...sampleListing, image_url: 'https://example.com/apartment.jpg' }}
        onClose={vi.fn()}
      />,
      { wrapper }
    )
    const img = screen.getByRole('img', { name: sampleListing.title })
    expect(img).toBeInTheDocument()
  })

  it('uses contain mode for portrait images after load', () => {
    render(
      <ListingSheet
        listing={{ ...sampleListing, image_url: 'https://example.com/portrait.jpg' }}
        onClose={vi.fn()}
      />,
      { wrapper }
    )

    const img = screen.getByTestId('listing-carousel-image')
    Object.defineProperty(img, 'naturalWidth', { configurable: true, value: 600 })
    Object.defineProperty(img, 'naturalHeight', { configurable: true, value: 1200 })
    fireEvent.load(img)

    expect(img.className).toContain('object-contain')
  })

  it('renders carousel dots and switches images on dot click', () => {
    render(
      <ListingSheet
        listing={{
          ...sampleListing,
          images: [
            'https://example.com/apartment-1.jpg',
            'https://example.com/apartment-2.jpg',
          ],
        }}
        onClose={vi.fn()}
      />,
      { wrapper }
    )

    const firstDot = screen.getByLabelText('מעבר לתמונה 1')
    const secondDot = screen.getByLabelText('מעבר לתמונה 2')
    expect(firstDot).toBeInTheDocument()
    expect(secondDot).toBeInTheDocument()

    const img = screen.getByRole('img', { name: sampleListing.title })
    expect(img).toHaveAttribute('src', 'https://example.com/apartment-1.jpg')

    fireEvent.click(secondDot)
    expect(img).toHaveAttribute('src', 'https://example.com/apartment-2.jpg')
  })

  it('seen button calls markSeen mutation with listing id', () => {
    const onClose = vi.fn()
    render(
      <ListingSheet listing={sampleListing} onClose={onClose} />,
      { wrapper }
    )
    const seenButton = screen.getByText('ראיתי')
    fireEvent.click(seenButton)
    expect(mockMarkSeenMutate).toHaveBeenCalledWith(42)
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('favorite button calls markFavorited mutation with listing id', () => {
    render(
      <ListingSheet listing={sampleListing} onClose={vi.fn()} />,
      { wrapper }
    )
    const favButton = screen.getByText('שמור')
    fireEvent.click(favButton)
    expect(mockMarkFavoritedMutate).toHaveBeenCalledWith(42)
  })
})
