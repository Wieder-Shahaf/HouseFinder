import { useMutation, useQueryClient } from '@tanstack/react-query'

export function useMarkSeen() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (listingId) =>
      fetch('/api/listings/' + listingId + '/seen', { method: 'PUT' }).then(r => r.json()),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['listings'] })
    },
  })
}

export function useMarkFavorited() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (listingId) =>
      fetch('/api/listings/' + listingId + '/favorited', { method: 'PUT' }).then(r => r.json()),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['listings'] })
    },
  })
}
