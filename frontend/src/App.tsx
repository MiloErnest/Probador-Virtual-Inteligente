import { Navigate, Route, Routes } from 'react-router-dom'

import { AuthProvider } from '@/auth/AuthContext'
import RequireAuth from '@/auth/RequireAuth'
import MainLayout from '@/layouts/MainLayout'
import CatalogPage from '@/pages/CatalogPage'
import DesignAIPage from '@/pages/DesignAIPage'
import HomePage from '@/pages/HomePage'
import LoginPage from '@/pages/LoginPage'
import MyTryOnsPage from '@/pages/MyTryOnsPage'
import ProfilePage from '@/pages/ProfilePage'
import RegisterPage from '@/pages/RegisterPage'
import TryOnPage from '@/pages/TryOnPage'

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route element={<MainLayout />}>
          {/* Publicas: el catalogo es el escaparate y se navega sin cuenta. */}
          <Route index element={<HomePage />} />
          <Route path="catalogo" element={<CatalogPage />} />
          <Route path="disenar" element={<DesignAIPage />} />
          <Route path="entrar" element={<LoginPage />} />
          <Route path="registro" element={<RegisterPage />} />

          {/* Requieren sesion. El backend las protege igualmente; esto solo
              evita enseñar una pantalla que iba a fallar. */}
          <Route element={<RequireAuth />}>
            <Route path="probador" element={<TryOnPage />} />
            <Route path="mis-pruebas" element={<MyTryOnsPage />} />
            <Route path="perfil" element={<ProfilePage />} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </AuthProvider>
  )
}
