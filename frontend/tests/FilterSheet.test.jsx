import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import FilterSheet from '../src/components/FilterSheet'

describe('FilterSheet', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders nothing when isOpen is false', () => {
    const { container } = render(
      <FilterSheet
        isOpen={false}
        onClose={vi.fn()}
        filters={{}}
        onFilterChange={vi.fn()}
      />
    )
    expect(container.firstChild).toBeNull()
  })

  it('renders filter controls when open', () => {
    render(
      <FilterSheet
        isOpen={true}
        onClose={vi.fn()}
        filters={{}}
        onFilterChange={vi.fn()}
      />
    )
    // Price slider section
    expect(screen.getByText('מחיר מקסימלי')).toBeInTheDocument()
    // Room buttons
    expect(screen.getByText('2.5')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getByText('3.5+')).toBeInTheDocument()
    // Neighborhood buttons
    expect(screen.getByText('כרמל')).toBeInTheDocument()
    expect(screen.getByText('מרכז העיר')).toBeInTheDocument()
    expect(screen.getByText('נווה שאנן')).toBeInTheDocument()
    // New only toggle
    expect(screen.getByText('חדשות בלבד')).toBeInTheDocument()
  })

  it('price slider calls onFilterChange with updated price_max', () => {
    const onFilterChange = vi.fn()
    render(
      <FilterSheet
        isOpen={true}
        onClose={vi.fn()}
        filters={{ price_max: 4500 }}
        onFilterChange={onFilterChange}
      />
    )
    const slider = screen.getByRole('slider')
    fireEvent.change(slider, { target: { value: '3000' } })
    expect(onFilterChange).toHaveBeenCalledWith(
      expect.objectContaining({ price_max: 3000 })
    )
  })

  it('room toggle activates and calls onFilterChange with rooms array', () => {
    const onFilterChange = vi.fn()
    render(
      <FilterSheet
        isOpen={true}
        onClose={vi.fn()}
        filters={{}}
        onFilterChange={onFilterChange}
      />
    )
    const roomButton = screen.getByText('3')
    fireEvent.click(roomButton)
    expect(onFilterChange).toHaveBeenCalledWith(
      expect.objectContaining({ rooms: [3] })
    )
  })

  it('room toggle deactivates when already active', () => {
    const onFilterChange = vi.fn()
    render(
      <FilterSheet
        isOpen={true}
        onClose={vi.fn()}
        filters={{ rooms: [3] }}
        onFilterChange={onFilterChange}
      />
    )
    const roomButton = screen.getByText('3')
    fireEvent.click(roomButton)
    expect(onFilterChange).toHaveBeenCalledWith(
      expect.objectContaining({ rooms: [] })
    )
  })

  it('new only toggle calls onFilterChange with newOnly flipped', () => {
    const onFilterChange = vi.fn()
    render(
      <FilterSheet
        isOpen={true}
        onClose={vi.fn()}
        filters={{ newOnly: false }}
        onFilterChange={onFilterChange}
      />
    )
    const toggleBtn = screen.getByText('חדשות בלבד').closest('div').querySelector('button')
    fireEvent.click(toggleBtn)
    expect(onFilterChange).toHaveBeenCalledWith(
      expect.objectContaining({ newOnly: true })
    )
  })

  it('calls onClose when backdrop is clicked', () => {
    const onClose = vi.fn()
    render(
      <FilterSheet
        isOpen={true}
        onClose={onClose}
        filters={{}}
        onFilterChange={vi.fn()}
      />
    )
    const backdrop = screen.getByTestId('filter-backdrop')
    expect(backdrop).toBeInTheDocument()
    fireEvent.click(backdrop)
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})
