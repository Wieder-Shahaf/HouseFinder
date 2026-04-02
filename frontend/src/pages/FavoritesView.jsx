import { useListings } from '../hooks/useListings'
import FavoriteCard from '../components/FavoriteCard'

export default function FavoritesView() {
  const { data: listings, isLoading, isError } = useListings({ is_favorited: true })

  return (
    <div className="min-h-screen bg-slate-50 pb-16">
      {/* Header */}
      <div className="bg-white px-4 pt-6 pb-4 shadow-sm">
        <h1 className="text-xl font-semibold">הדירות השמורות שלי</h1>
      </div>

      {/* Content */}
      <div className="px-4 pt-4">
        {isLoading && (
          <div className="flex justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
          </div>
        )}

        {isError && (
          <div className="text-center py-12">
            <h2 className="text-xl font-semibold mb-2">שגיאה בטעינת המודעות</h2>
            <p className="text-slate-500">לא ניתן להתחבר לשרת. נסה שוב מאוחר יותר.</p>
          </div>
        )}

        {!isLoading && !isError && listings?.length === 0 && (
          <div className="text-center py-12">
            <h2 className="text-xl font-semibold mb-2">עוד לא שמרת דירות</h2>
            <p className="text-slate-500">לחץ על ❤ במודעה כדי לשמור אותה</p>
          </div>
        )}

        {listings?.map(listing => (
          <FavoriteCard key={listing.id} listing={listing} />
        ))}
      </div>
    </div>
  )
}
