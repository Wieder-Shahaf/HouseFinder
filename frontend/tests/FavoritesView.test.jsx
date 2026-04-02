import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import FavoritesView from '../src/pages/FavoritesView'

// Mock the useListings hook
vi.mock('../src/hooks/useListings', () => ({
  useListings: vi.fn(),
}))

// Mock react-router-dom
vi.mock('react-router-dom', () => ({
  useLocation: vi.fn(() => ({ pathname: '/favorites' })),
  useNavigate: vi.fn(() => vi.fn()),
}))

import { useListings } from '../src/hooks/useListings'

function wrapper({ children }) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}

describe('FavoritesView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders page header', () => {
    useListings.mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
    })
    render(<FavoritesView />, { wrapper })
    expect(screen.getByText('הדירות השמורות שלי')).toBeInTheDocument()
  })

  it('renders favorite cards for listings', () => {
    useListings.mockReturnValue({
      data: [
        {
          id: 1,
          title: 'דירה בחיפה',
          price: 3500,
          rooms: 3,
          size_sqm: 80,
          address: 'רחוב הרצל 1',
          source_badge: 'yad2',
          post_date: '2026-04-01T10:00:00Z',
          url: 'https://example.com/1',
        },
        {
          id: 2,
          title: 'דירה בכרמל',
          price: 4200,
          rooms: 3.5,
          size_sqm: 90,
          address: 'שדרות הנשיא 5',
          source_badge: 'yad2',
          post_date: '2026-04-01T12:00:00Z',
          url: 'https://example.com/2',
        },
      ],
      isLoading: false,
      isError: false,
    })
    render(<FavoritesView />, { wrapper })
    // Both prices should appear
    expect(screen.getByText('₪3,500')).toBeInTheDocument()
    expect(screen.getByText('₪4,200')).toBeInTheDocument()
  })

  it('shows empty state when no favorites', () => {
    useListings.mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
    })
    render(<FavoritesView />, { wrapper })
    expect(screen.getByText('עוד לא שמרת דירות')).toBeInTheDocument()
  })

  it('passes is_favorited=true to useListings', () => {
    useListings.mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
    })
    render(<FavoritesView />, { wrapper })
    expect(useListings).toHaveBeenCalledWith({ is_favorited: true })
  })
})
