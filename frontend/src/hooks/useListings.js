import { useQuery } from '@tanstack/react-query'

export function useListings(filterParams = {}) {
  return useQuery({
    queryKey: ['listings', filterParams],
    queryFn: () =>
      fetch('/api/listings?' + new URLSearchParams(filterParams)).then(r => {
        if (!r.ok) throw new Error('Failed to fetch listings')
        return r.json()
      }),
    staleTime: 300000,
    refetchOnWindowFocus: true,
    refetchInterval: 300000,
  })
}
