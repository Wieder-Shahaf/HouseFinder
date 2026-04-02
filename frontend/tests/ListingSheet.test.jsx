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
    expect(screen.getByText('3 חדרים')).toBeInTheDocument()
    // Address
    expect(screen.getByText('רחוב הנשיא 10, חיפה')).toBeInTheDocument()
    // Source badge
    expect(screen.getByText('יד2')).toBeInTheDocument()
    // Original post link
    expect(screen.getByText('פתח מודעה מקורית')).toBeInTheDocument()
  })

  it('calls onClose when backdrop clicked', () => {
    const onClose = vi.fn()
    render(
      <ListingSheet listing={sampleListing} onClose={onClose} />,
      { wrapper }
    )
    // The backdrop is the fixed inset-0 z-40 div (first child of fragment)
    const backdrop = document.querySelector('.fixed.inset-0.z-40')
    expect(backdrop).toBeInTheDocument()
    fireEvent.click(backdrop)
    expect(onClose).toHaveBeenCalledTimes(1)
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
