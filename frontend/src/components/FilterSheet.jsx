import { X } from 'lucide-react'

export default function FilterSheet({ isOpen, onClose, filters, onFilterChange }) {
  if (!isOpen) return null

  return (
    <>
      {/* Backdrop */}
      <div
        data-testid="filter-backdrop"
        onClick={onClose}
        className="fixed inset-0 z-[1500] bg-black/25"
      />

      {/* Filter drawer */}
      <section
        aria-label="סינון מודעות"
        className="fixed inset-y-0 right-0 z-[1600] bg-white shadow-2xl border-l border-slate-200"
        style={{
          width: 'min(92vw, 380px)',
          maxWidth: '25vw',
          minWidth: '320px',
          paddingTop: 'max(0.75rem, env(safe-area-inset-top, 0px))',
          paddingBottom: 'env(safe-area-inset-bottom, 0px)',
        }}
      >
        <div className="h-full flex flex-col">
          {/* Header */}
          <div className="sticky top-0 z-10 bg-white border-b border-slate-100 px-4 py-3">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">סינון</h2>
              <button
                onClick={onClose}
                aria-label="סגור סינון"
                className="min-h-[44px] min-w-[44px] flex items-center justify-center text-slate-500"
              >
                <X size={20} />
              </button>
            </div>
          </div>

          <div className="px-4 py-4 overflow-y-auto overscroll-contain flex-1 space-y-4">
            {/* Price slider */}
            <div className="rounded-xl border border-slate-200 p-3">
              <div className="flex items-center justify-between mb-2">
                <label className="text-sm font-semibold">מחיר מקסימלי</label>
                <span className="text-xs font-semibold text-blue-700 bg-blue-50 rounded-full px-2.5 py-1">
                  ₪{(filters.price_max || 4500).toLocaleString()}
                </span>
              </div>
              <input
                type="range"
                min="2000"
                max="4500"
                step="100"
                value={filters.price_max || 4500}
                onChange={(e) => onFilterChange({ ...filters, price_max: Number(e.target.value) })}
                className="w-full"
              />
              <div className="flex items-center justify-between text-xs text-slate-500 mt-1">
                <span>₪2,000</span>
                <span>₪4,500</span>
              </div>
            </div>

            {/* Rooms */}
            <div className="rounded-xl border border-slate-200 p-3">
              <label className="block text-sm font-semibold mb-2">חדרים</label>
              <div className="grid grid-cols-3 gap-2">
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
                      className={`min-h-[44px] px-2 rounded-lg border text-sm font-semibold
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

            {/* Neighborhoods */}
            <div className="rounded-xl border border-slate-200 p-3">
              <label className="block text-sm font-semibold mb-2">שכונה</label>
              <div className="grid grid-cols-1 gap-2">
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
                      className={`min-h-[44px] px-3 rounded-lg border text-sm font-semibold text-right
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

            {/* New-only */}
            <div className="flex items-center justify-between rounded-xl border border-slate-200 px-3 py-3">
              <label className="text-sm font-semibold">חדשות בלבד</label>
              <button
                role="switch"
                aria-checked={Boolean(filters.newOnly)}
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

          {/* Sticky actions */}
          <div className="sticky bottom-0 z-10 bg-white border-t border-slate-100 px-4 py-3">
            <div className="flex gap-2">
              <button
                onClick={() => onFilterChange({})}
                className="flex-1 min-h-[44px] rounded-lg border border-slate-300 text-slate-700 text-sm font-semibold"
              >
                נקה
              </button>
              <button
                onClick={onClose}
                className="flex-1 min-h-[44px] rounded-lg bg-blue-600 text-white text-sm font-semibold"
              >
                החל
              </button>
            </div>
          </div>
        </div>
      </section>
    </>
  )
}
