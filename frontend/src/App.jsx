import { BrowserRouter, Routes, Route } from 'react-router-dom'
import MapView from './pages/MapView'

function App() {
  return (
    <BrowserRouter>
      <div className="bg-slate-50 min-h-screen">
        <Routes>
          <Route path="/" element={<MapView />} />
        </Routes>
      </div>
    </BrowserRouter>
  )
}

export default App
