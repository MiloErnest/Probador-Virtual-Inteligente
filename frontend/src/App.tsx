import { Navigate, Route, Routes } from 'react-router-dom'

import MainLayout from '@/layouts/MainLayout'
import CatalogPage from '@/pages/CatalogPage'
import DesignAIPage from '@/pages/DesignAIPage'
import HomePage from '@/pages/HomePage'
import MyTryOnsPage from '@/pages/MyTryOnsPage'
import ProfilePage from '@/pages/ProfilePage'
import TryOnPage from '@/pages/TryOnPage'

export default function App() {
  return (
    <Routes>
      <Route element={<MainLayout />}>
        <Route index element={<HomePage />} />
        <Route path="catalogo" element={<CatalogPage />} />
        <Route path="probador" element={<TryOnPage />} />
        <Route path="mis-pruebas" element={<MyTryOnsPage />} />
        <Route path="disenar" element={<DesignAIPage />} />
        <Route path="perfil" element={<ProfilePage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
