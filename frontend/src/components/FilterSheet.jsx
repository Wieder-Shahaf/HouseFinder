import { X } from 'lucide-react'

export default function FilterSheet({ isOpen, onClose, filters, onFilterChange }) {
  if (!isOpen) return null

  return (
    <>
      {/* Backdrop */}
      <div onClick={onClose} className="fixed inset-0 z-40" />

      {/* Filter sheet */}
      <div className="fixed bottom-0 left-0 right-0 z-50 bg-white rounded-t-2xl shadow-lg pt-6 pb-8 px-4">

        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-semibold">סינון</h2>
          <button
            onClick={onClose}
            className="min-h-[44px] min-w-[44px] flex items-center justify-center"
          >
            <X size={20} />
          </button>
        </div>

        {/* Price slider: מחיר מקסימלי */}
        <div className="mb-6">
          <label className="block text-base font-semibold mb-2">מחיר מקסימלי</label>
          <input
            type="range"
            min="2000"
            max="4500"
            step="100"
            value={filters.price_max || 4500}
            onChange={(e) => onFilterChange({ ...filters, price_max: Number(e.target.value) })}
            className="w-full"
          />
          <div className="text-sm text-slate-500 mt-1">
            ₪{(filters.price_max || 4500).toLocaleString()}
          </div>
        </div>

        {/* Room toggles: חדרים */}
        <div className="mb-6">
          <label className="block text-base font-semibold mb-2">חדרים</label>
          <div className="flex gap-2">
            {[2.5, 3, '3.5+'].map(room => {
              const roomVal = room === '3.5+' ? 3.5 : room
              const isActive = filters.rooms?.includes(roomVal)
              return (
                <button
                  key={room}
                  onClick={() => {
                    const current = filters.rooms || []
                    const updated = isActive
                      ? current.filter(r => r !== roomVal)
                      : [...current, roomVal]
                    onFilterChange({ ...filters, rooms: updated })
                  }}
                  className={`min-h-[44px] px-4 rounded-lg border text-base font-semibold
                    ${isActive
                      ? 'bg-blue-600 text-white border-blue-600'
                      : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-50'}`}
                >
                  {room === '3.5+' ? '3.5+' : room}
                </button>
              )
            })}
          </div>
        </div>

        {/* Neighborhood toggles: שכונה */}
        <div className="mb-6">
          <label className="block text-base font-semibold mb-2">שכונה</label>
          <div className="flex gap-2 flex-wrap">
            {['כרמל', 'מרכז העיר', 'נווה שאנן'].map(hood => {
              const isActive = filters.neighborhoods?.includes(hood)
              return (
                <button
                  key={hood}
                  onClick={() => {
                    const current = filters.neighborhoods || []
                    const updated = isActive
                      ? current.filter(n => n !== hood)
                      : [...current, hood]
                    onFilterChange({ ...filters, neighborhoods: updated })
                  }}
                  className={`min-h-[44px] px-4 rounded-lg border text-base font-semibold
                    ${isActive
                      ? 'bg-blue-600 text-white border-blue-600'
                      : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-50'}`}
                >
                  {hood}
                </button>
              )
            })}
          </div>
        </div>

        {/* New only toggle: חדשות בלבד */}
        <div className="flex items-center justify-between">
          <label className="text-base font-semibold">חדשות בלבד</label>
          <button
            onClick={() => onFilterChange({ ...filters, newOnly: !filters.newOnly })}
            className={`w-12 h-7 rounded-full transition-colors relative
              ${filters.newOnly ? 'bg-blue-600' : 'bg-slate-300'}`}
          >
            <div
              className={`w-5 h-5 bg-white rounded-full absolute top-1 transition-all
                ${filters.newOnly ? 'left-1' : 'right-1'}`}
            />
          </button>
        </div>
      </div>
    </>
  )
}
