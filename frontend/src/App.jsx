import { BrowserRouter, Routes, Route } from 'react-router-dom'
import MapView from './pages/MapView'
import FavoritesView from './pages/FavoritesView'
import BottomNav from './components/BottomNav'

function App() {
  return (
    <BrowserRouter>
      <div dir="rtl" className="bg-slate-50 min-h-screen">
        <Routes>
          <Route path="/" element={<MapView />} />
          <Route path="/favorites" element={<FavoritesView />} />
        </Routes>
        <BottomNav />
      </div>
    </BrowserRouter>
  )
}

export default App
