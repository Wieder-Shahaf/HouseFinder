import { useLocation, useNavigate } from 'react-router-dom'
import { Map, Heart } from 'lucide-react'

const tabs = [
  { path: '/', label: 'מפה', icon: Map },
  { path: '/favorites', label: 'שמורים', icon: Heart },
]

export default function BottomNav() {
  const { pathname } = useLocation()
  const navigate = useNavigate()

  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-50 bg-white border-t border-slate-200 h-14 flex items-center justify-around"
      style={{ paddingBottom: 'env(safe-area-inset-bottom, 0px)' }}
    >
      {tabs.map(tab => {
        const isActive = pathname === tab.path
        const Icon = tab.icon
        return (
          <button
            key={tab.path}
            onClick={() => navigate(tab.path)}
            className={`flex flex-col items-center justify-center min-h-[44px] min-w-[44px] px-4 ${
              isActive ? 'text-blue-600' : 'text-slate-500'
            }`}
          >
            <Icon size={22} />
            <span className="text-xs mt-0.5">{tab.label}</span>
          </button>
        )
      })}
    </nav>
  )
}
